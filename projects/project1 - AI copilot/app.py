"""Streamlit entry point for AI BI Copilot."""

from __future__ import annotations

from io import BytesIO
import re

import pandas as pd
import plotly.express as px
import streamlit as st

from src.ai import AIConfigurationError, AIResponseError, NaturalLanguageSQLAgent, SQLSafetyError, BusinessAnalystAgent
from src.analytics import build_cleaning_comparison, build_dashboard_report, generate_profile_report
from src.cleaning import clean_dataframe
from src.config import build_health_report
from src.config.logging_config import configure_logging, get_logger
from src.config.settings import SettingsError, get_settings
from src.data_upload import UploadValidationError, load_uploaded_dataset
from src.database import DatabaseError, DatabaseManager
from src.powerbi import build_power_bi_export
from src.reports import build_executive_report
from src.visualization import build_chart, build_chart_suite


configure_logging()
logger = get_logger(__name__)

MAX_AUTOMATIC_ANALYSIS_ROWS = 50_000


def main() -> None:
    """Render the initial application shell."""
    st.set_page_config(
        page_title="AI BI Copilot",
        page_icon="AI",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    try:
        settings = get_settings()
    except SettingsError as exc:
        logger.exception("Application configuration failed")
        st.error(f"Configuration error: {exc}")
        st.stop()

    st.title("AI BI Copilot")
    st.caption("AI-powered business intelligence assistant")

    with st.sidebar:
        st.header("Workspace")
        st.write(f"Environment: {settings.app_env}")
        st.write(f"Database: {settings.database_url}")
        _render_health_status(settings)

    try:
        database = DatabaseManager(settings.database_url)
    except DatabaseError as exc:
        st.error(str(exc))
        return

    st.subheader("Upload Dataset")
    uploaded_file = st.file_uploader(
        "Upload CSV or Excel file",
        type=["csv", "xlsx"],
        accept_multiple_files=False,
        help=f"Maximum file size: {settings.max_upload_mb} MB",
    )

    if uploaded_file is None:
        st.info("Upload a CSV or Excel file to build the dashboard, AI analyst context, data quality report, explorer, and downloads.")
        return

    try:
        progress_bar = st.progress(0, text="Loading dataset...")
        file_bytes = uploaded_file.getvalue()
        progress_bar.progress(0.25, text="Reading uploaded file...")
        dataset = _load_uploaded_dataset_cached(
            file_bytes=file_bytes,
            file_name=uploaded_file.name,
            file_size_bytes=uploaded_file.size,
            max_upload_mb=settings.max_upload_mb,
        )
        progress_bar.progress(1.0, text="Dataset loaded.")
    except UploadValidationError as exc:
        logger.warning("Upload validation failed for %s: %s", uploaded_file.name, exc)
        st.error(str(exc))
        return

    upload_key = f"{dataset.file_name}:{uploaded_file.size}"
    _ensure_dashboard_state(upload_key)

    analysis_dataframe, analysis_is_sampled = _analysis_dataframe(dataset.dataframe)
    if analysis_is_sampled:
        st.warning(
            f"Large dataset mode is active. Automatic profiling, cleaning, charts, AI context, and reports use a "
            f"representative sample of {len(analysis_dataframe):,} rows so the app stays responsive. "
            "Full-dataset batch cleaning/export will be enabled in the next performance pass."
        )

    with st.spinner("Preparing dashboard data..."):
        profile, cleaning_result, cleaned_profile, comparison = _prepare_analysis_cached(analysis_dataframe)
    cleaning_summary = cleaning_result.summary
    dashboard_dataframe = _apply_chat_dashboard_state(cleaning_result.cleaned_dataframe)
    dashboard = build_dashboard_report(dashboard_dataframe)

    summary = dataset.summary
    st.success(f"Loaded {dataset.file_name}")

    st.subheader("Dataset Summary")
    metric_columns = st.columns(5)
    metric_columns[0].metric("Rows", f"{summary.rows:,}")
    metric_columns[1].metric("Columns", f"{summary.columns:,}")
    metric_columns[2].metric("Quality", f"{profile.health_score}%")
    metric_columns[3].metric("Missing", f"{profile.missing_values:,}")
    metric_columns[4].metric("Dataset Type", dashboard.dataset_type)

    with st.expander("Detected fields", expanded=False):
        st.dataframe(
            [
                {
                    "Field": field.name,
                    "Detected Type": field.detected_type,
                    "Missing Values": field.missing_values,
                }
                for field in summary.fields
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("AI Business Analyst Chat")
    ai_provider, ai_key, ai_model = _resolve_ai_provider(settings)
    chat_prompt = _render_ai_chat_shell(dashboard.dataset_type)
    if chat_prompt:
        st.session_state.ai_analyst_messages.append({"role": "user", "content": chat_prompt})
        with st.status("Analyzing uploaded dataset...", expanded=False):
            response, dashboard_changed = _handle_dashboard_chat_command(
                prompt=chat_prompt,
                base_dataframe=cleaning_result.cleaned_dataframe,
                current_dataframe=dashboard_dataframe,
                profile_report=profile,
                cleaning_summary=cleaning_summary,
                ai_provider=ai_provider,
                ai_key=ai_key,
                ai_model=ai_model,
            )
        st.session_state.ai_analyst_messages.append({"role": "assistant", "content": response})
        if dashboard_changed:
            st.rerun()

    active_filters = _dashboard_state_summary()
    if active_filters:
        st.info(active_filters)

    st.subheader("Dynamic Dashboard")
    st.caption(f"Showing {len(dashboard_dataframe):,} of {len(cleaning_result.cleaned_dataframe):,} cleaned analysis rows")
    _render_dashboard_kpis(dashboard.dynamic_kpis)

    requested_chart = _build_requested_chart(dashboard_dataframe)
    if requested_chart is not None:
        st.plotly_chart(requested_chart, use_container_width=True)

    dashboard_tabs = st.tabs(["Trend", "Region", "Category"])
    with dashboard_tabs[0]:
        if dashboard.figures.sales_trend:
            st.plotly_chart(dashboard.figures.sales_trend, use_container_width=True)
        else:
            st.info("A trend chart needs a date field and a numeric measure.")
    with dashboard_tabs[1]:
        if dashboard.figures.regional_analysis:
            st.plotly_chart(dashboard.figures.regional_analysis, use_container_width=True)
        else:
            st.info("A regional chart needs a location field and a numeric measure.")
    with dashboard_tabs[2]:
        if dashboard.figures.product_analysis:
            st.plotly_chart(dashboard.figures.product_analysis, use_container_width=True)
        else:
            st.info("A category chart needs a categorical field and a numeric measure.")

    st.write("Interactive Charts")
    _render_chart_suite(dashboard_dataframe, key_prefix="cleaned_upload")

    st.write("Business Summary")
    for recommendation in profile.recommendations:
        st.write(f"- {recommendation}")

    st.subheader("Data Quality")
    profile_columns = st.columns(4)
    profile_columns[0].metric("Health Score", f"{profile.health_score}%")
    profile_columns[1].metric("Missing Values", f"{profile.missing_values:,}")
    profile_columns[2].metric("Duplicate Rows", f"{profile.duplicate_records:,}")
    profile_columns[3].metric("Issues", f"{len(profile.issues):,}")

    if profile.issues:
        st.write("Profiling Issues")
        st.dataframe(
            [
                {
                    "Category": issue.category,
                    "Field": issue.field or "Dataset",
                    "Severity": issue.severity,
                    "Affected Rows": issue.affected_rows,
                    "Issue": issue.message,
                }
                for issue in profile.issues
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("No profiling issues detected.")

    st.subheader("Data Cleaning Agent")
    cleaning_columns = st.columns(4)
    cleaning_columns[0].metric("Rows Processed", f"{cleaning_summary.records_processed:,}")
    cleaning_columns[1].metric("Rows Modified", f"{cleaning_summary.rows_modified:,}")
    cleaning_columns[2].metric("Cells Modified", f"{cleaning_summary.cells_modified:,}")
    cleaning_columns[3].metric("Rows Removed", f"{cleaning_summary.records_removed:,}")
    detail_columns = st.columns(4)
    detail_columns[0].metric("Missing Values Filled", f"{cleaning_summary.missing_values_filled:,}")
    detail_columns[1].metric("Duplicates Removed", f"{cleaning_summary.duplicates_removed:,}")
    detail_columns[2].metric("Outliers Flagged", f"{cleaning_summary.outliers_flagged:,}")
    detail_columns[3].metric("Formats Standardized", f"{cleaning_summary.formats_standardized:,}")

    if cleaning_summary.actions:
        st.write("Cleaning Summary")
        st.dataframe(
            [
                {
                    "Action": action.action,
                    "Field": action.field or "Dataset",
                    "Affected Count": action.records_affected,
                    "Unit": _cleaning_action_unit(action.action),
                    "Details": action.details or "",
                }
                for action in cleaning_summary.actions
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("No cleaning changes were required.")

    _render_cleaning_comparison(comparison)

    st.subheader("Data Explorer")
    explorer_dataframe = _render_data_explorer(dashboard_dataframe, key_prefix="cleaned_upload")

    st.subheader("Reports")
    _render_power_bi_export(explorer_dataframe, dataset.file_name, key_prefix="cleaned_upload")
    _render_executive_report(
        dataframe=cleaning_result.cleaned_dataframe,
        dataset_name=dataset.file_name,
        profile_report=profile,
        key_prefix="cleaned_upload",
        cleaning_summary=cleaning_summary,
    )

    st.subheader("Analytics Database")
    if analysis_is_sampled:
        st.info("Saving is disabled in large dataset sample mode to avoid storing a sampled clean result as the full dataset.")
    if st.button("Save Cleaned Dataset", type="primary", disabled=analysis_is_sampled):
        try:
            stored_dataset = database.save_dataset(
                dataframe=cleaning_result.cleaned_dataframe,
                source_file=dataset.file_name,
                column_metadata=[
                    {
                        "column_name": field.name,
                        "detected_type": field.detected_type,
                        "missing_values": field.missing_values,
                    }
                    for field in summary.fields
                ],
                profile_health_score=profile.health_score,
                cleaning_summary={
                    "records_processed": cleaning_summary.records_processed,
                    "rows_modified": cleaning_summary.rows_modified,
                    "cells_modified": cleaning_summary.cells_modified,
                    "records_fixed": cleaning_summary.records_fixed,
                    "records_removed": cleaning_summary.records_removed,
                    "duplicates_removed": cleaning_summary.duplicates_removed,
                    "missing_values_filled": cleaning_summary.missing_values_filled,
                    "formats_standardized": cleaning_summary.formats_standardized,
                    "outliers_flagged": cleaning_summary.outliers_flagged,
                    "invalid_records_removed": cleaning_summary.invalid_records_removed,
                    "anomalies_detected": cleaning_summary.anomalies_detected,
                },
            )
        except DatabaseError as exc:
            logger.exception("Failed to save dataset")
            st.error(str(exc))
        else:
            st.success(f"Saved cleaned dataset to `{stored_dataset.table_name}`")


def _resolve_ai_provider(settings) -> tuple[str, str, str]:
    if settings.ai_provider == "gemini" or (settings.ai_provider == "auto" and settings.gemini_api_key):
        return "gemini", settings.gemini_api_key, settings.gemini_model
    if settings.ai_provider == "claude" or (settings.ai_provider == "auto" and settings.claude_api_key):
        return "claude", settings.claude_api_key, settings.claude_model
    return settings.ai_provider, "", ""


@st.cache_data(show_spinner=False)
def _load_uploaded_dataset_cached(file_bytes: bytes, file_name: str, file_size_bytes: int, max_upload_mb: int):
    return load_uploaded_dataset(
        file=BytesIO(file_bytes),
        file_name=file_name,
        file_size_bytes=file_size_bytes,
        max_upload_mb=max_upload_mb,
    )


@st.cache_data(show_spinner=False)
def _prepare_analysis_cached(dataframe: pd.DataFrame):
    profile = generate_profile_report(dataframe)
    cleaning_result = clean_dataframe(dataframe)
    cleaned_profile = generate_profile_report(cleaning_result.cleaned_dataframe)
    comparison = build_cleaning_comparison(profile, cleaned_profile, cleaning_result.summary)
    return profile, cleaning_result, cleaned_profile, comparison


def _analysis_dataframe(dataframe):
    if len(dataframe) <= MAX_AUTOMATIC_ANALYSIS_ROWS:
        return dataframe, False
    return dataframe.sample(n=MAX_AUTOMATIC_ANALYSIS_ROWS, random_state=42).reset_index(drop=True), True


def _ensure_dashboard_state(upload_key: str) -> None:
    if st.session_state.get("active_upload_key") != upload_key:
        st.session_state.active_upload_key = upload_key
        st.session_state.dashboard_filters = []
        st.session_state.show_missing_only = False
        st.session_state.drop_missing_rows = False
        st.session_state.show_outliers_only = False
        st.session_state.requested_chart = None
        st.session_state.ai_analyst_messages = []


def _apply_chat_dashboard_state(dataframe: pd.DataFrame) -> pd.DataFrame:
    filtered = dataframe
    if st.session_state.get("drop_missing_rows", False):
        filtered = filtered.dropna()
    if st.session_state.get("show_missing_only", False):
        filtered = filtered[filtered.isna().any(axis=1)]
    if st.session_state.get("show_outliers_only", False):
        outlier_mask = _outlier_mask(filtered)
        filtered = filtered[outlier_mask]
    for dashboard_filter in st.session_state.get("dashboard_filters", []):
        column = dashboard_filter["column"]
        operator = dashboard_filter["operator"]
        value = dashboard_filter["value"]
        if column not in filtered.columns:
            continue
        series = filtered[column]
        if operator == "contains":
            filtered = filtered[series.astype(str).str.contains(str(value), case=False, na=False)]
        elif operator == "in":
            selected_values = {str(item).casefold() for item in value}
            filtered = filtered[series.astype(str).str.casefold().isin(selected_values)]
        elif operator in {">", ">=", "<", "<=", "="}:
            numeric_series = pd.to_numeric(series, errors="coerce")
            numeric_value = float(value)
            if operator == ">":
                filtered = filtered[numeric_series > numeric_value]
            elif operator == ">=":
                filtered = filtered[numeric_series >= numeric_value]
            elif operator == "<":
                filtered = filtered[numeric_series < numeric_value]
            elif operator == "<=":
                filtered = filtered[numeric_series <= numeric_value]
            else:
                filtered = filtered[numeric_series == numeric_value]
    return filtered


def _render_ai_chat_shell(dataset_type: str) -> str | None:
    st.caption(
        "Use chat as the control center. Ask questions or type commands like `show Toyota only`, "
        "`filter price above 20000`, `compare petrol and diesel`, `create price vs mileage chart`, or `reset filters`."
    )
    controls = st.columns([1, 1, 4])
    if controls[0].button("Clear conversation", key="clear_ai_conversation"):
        st.session_state.ai_analyst_messages = []
        st.session_state.chat_suggestion = None
        st.rerun()
    if controls[1].button("Reset dashboard", key="chat_reset_dashboard"):
        st.session_state.dashboard_filters = []
        st.session_state.show_missing_only = False
        st.session_state.drop_missing_rows = False
        st.session_state.show_outliers_only = False
        st.session_state.requested_chart = None
        st.session_state.ai_analyst_messages.append({"role": "assistant", "content": "Dashboard reset to the uploaded dataset."})
        st.rerun()

    suggestions = _suggested_questions(dataset_type)
    suggestion_columns = st.columns(len(suggestions))
    for index, suggestion in enumerate(suggestions):
        if suggestion_columns[index].button(suggestion, key=f"suggestion_{index}"):
            st.session_state.chat_suggestion = suggestion
            st.rerun()

    for message in st.session_state.ai_analyst_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    pending_suggestion = st.session_state.pop("chat_suggestion", None)
    chat_prompt = st.chat_input("Ask or command the dashboard using the uploaded dataset")
    return pending_suggestion or chat_prompt


def _handle_dashboard_chat_command(
    prompt: str,
    base_dataframe: pd.DataFrame,
    current_dataframe: pd.DataFrame,
    profile_report,
    cleaning_summary,
    ai_provider: str,
    ai_key: str,
    ai_model: str,
) -> tuple[str, bool]:
    command_response = _apply_dashboard_command(prompt, base_dataframe, current_dataframe)
    if command_response is not None:
        return command_response, True
    if not ai_key:
        return "This information is not available in the uploaded dataset.", False
    try:
        analyst = BusinessAnalystAgent(api_key=ai_key, model=ai_model, provider=ai_provider)
        analysis = analyst.answer_question(
            question=prompt,
            dataframe=current_dataframe,
            profile_report=profile_report,
            cleaning_summary=cleaning_summary,
            business_context="Use only the currently uploaded dataset and current dashboard filter state.",
        )
    except (AIConfigurationError, AIResponseError, ValueError) as exc:
        logger.warning("AI analyst request failed: %s", exc)
        return "This information is not available in the uploaded dataset.", False
    return _format_ai_analysis(analysis.summary, analysis.key_findings, analysis.business_recommendations), False


def _apply_dashboard_command(prompt: str, base_dataframe: pd.DataFrame, current_dataframe: pd.DataFrame) -> str | None:
    normalized = prompt.casefold().strip()
    if normalized in {"reset", "reset dashboard", "clear filters", "show all"}:
        st.session_state.dashboard_filters = []
        st.session_state.show_missing_only = False
        st.session_state.drop_missing_rows = False
        st.session_state.show_outliers_only = False
        st.session_state.requested_chart = None
        return "Dashboard reset to the uploaded dataset."
    if "missing" in normalized and any(word in normalized for word in ["remove", "drop", "exclude"]):
        st.session_state.drop_missing_rows = True
        st.session_state.show_missing_only = False
        return "Applied data-quality command: rows with missing values are excluded from the dashboard view."
    if "missing" in normalized:
        st.session_state.show_missing_only = True
        return "Dashboard updated to show rows with missing values."
    if "outlier" in normalized:
        st.session_state.show_outliers_only = True
        return "Dashboard updated to show rows with potential numeric outliers."
    if "duplicate" in normalized and any(word in normalized for word in ["remove", "drop", "clean"]):
        st.session_state.dashboard_filters = []
        st.session_state.show_missing_only = False
        st.session_state.drop_missing_rows = False
        return f"Duplicate handling is already applied in the cleaned analysis dataset. Duplicates removed: {base_dataframe.duplicated().sum():,}."
    requested_chart = _parse_chart_request(normalized, base_dataframe)
    if requested_chart:
        st.session_state.requested_chart = requested_chart
        return f"Created chart request: {requested_chart['y']} vs {requested_chart['x']}. Dashboard updated."
    comparison = _parse_comparison_request(normalized, current_dataframe)
    if comparison:
        column, left_value, right_value = comparison
        st.session_state.dashboard_filters.append({"column": column, "operator": "in", "value": [left_value, right_value]})
        filtered = current_dataframe[current_dataframe[column].astype(str).str.casefold().isin([left_value, right_value])]
        counts = filtered[column].astype(str).value_counts()
        lines = [f"Comparison for {column}:"]
        lines.extend(f"- {index}: {count:,} row(s)" for index, count in counts.items())
        return "\n".join(lines)
    numeric_filter = _parse_numeric_filter(normalized, base_dataframe)
    if numeric_filter:
        st.session_state.dashboard_filters.append(numeric_filter)
        return f"Dashboard filtered: {numeric_filter['column']} {numeric_filter['operator']} {numeric_filter['value']}."
    value_filter = _parse_value_filter(normalized, base_dataframe)
    if value_filter:
        st.session_state.dashboard_filters.append(value_filter)
        return f"Dashboard filtered to rows where {value_filter['column']} contains `{value_filter['value']}`."
    top_category = _parse_top_category(normalized, current_dataframe)
    if top_category:
        column, limit = top_category
        counts = current_dataframe[column].astype(str).value_counts().head(limit)
        lines = [f"Top {limit} values in {column}:"]
        lines.extend(f"- {index}: {count:,}" for index, count in counts.items())
        return "\n".join(lines)
    return None


def _parse_numeric_filter(prompt: str, dataframe: pd.DataFrame) -> dict[str, object] | None:
    natural_match = re.search(r"(?:filter|show)?\s*([a-z0-9 _-]+?)\s+(?:above|over|greater than|more than|after)\s+([0-9]+(?:\.[0-9]+)?)", prompt)
    if natural_match:
        field_text, value = natural_match.groups()
        column = _find_prompt_column(field_text, dataframe, numeric_only=True)
        if column:
            return {"column": column, "operator": ">", "value": float(value)}
    below_match = re.search(r"(?:filter|show)?\s*([a-z0-9 _-]+?)\s+(?:below|under|less than|before)\s+([0-9]+(?:\.[0-9]+)?)", prompt)
    if below_match:
        field_text, value = below_match.groups()
        column = _find_prompt_column(field_text, dataframe, numeric_only=True)
        if column:
            return {"column": column, "operator": "<", "value": float(value)}
    match = re.search(r"([a-z0-9 _-]+?)\s*(>=|<=|>|<|=)\s*([0-9]+(?:\.[0-9]+)?)", prompt)
    if not match:
        return None
    field_text, operator, value = match.groups()
    column = _find_prompt_column(field_text, dataframe, numeric_only=True)
    if not column:
        return None
    return {"column": column, "operator": operator, "value": float(value)}


def _parse_chart_request(prompt: str, dataframe: pd.DataFrame) -> dict[str, str] | None:
    match = re.search(r"(?:create|show|make|build).*?([a-z0-9 _-]+?)\s+vs\s+([a-z0-9 _-]+)", prompt)
    if not match:
        return None
    left_text, right_text = match.groups()
    x_column = _find_prompt_column(right_text, dataframe, numeric_only=False)
    y_column = _find_prompt_column(left_text, dataframe, numeric_only=False)
    if not x_column or not y_column:
        return None
    return {"x": x_column, "y": y_column}


def _parse_comparison_request(prompt: str, dataframe: pd.DataFrame) -> tuple[str, str, str] | None:
    match = re.search(r"compare\s+(.+?)\s+(?:and|vs|versus)\s+(.+)", prompt)
    if not match:
        return None
    left_text, right_text = match.groups()
    for column in dataframe.columns:
        series = dataframe[column]
        if not (series.dtype == "object" or pd.api.types.is_string_dtype(series)):
            continue
        values = {str(value).casefold(): str(value) for value in series.dropna().astype(str).unique().tolist()[:500]}
        left_match = next((value for value in values if value in left_text), None)
        right_match = next((value for value in values if value in right_text), None)
        if left_match and right_match:
            return str(column), left_match, right_match
    return None


def _parse_value_filter(prompt: str, dataframe: pd.DataFrame) -> dict[str, object] | None:
    lowered_columns = [str(column).casefold() for column in dataframe.columns]
    for column in dataframe.columns:
        series = dataframe[column]
        if not (series.dtype == "object" or pd.api.types.is_string_dtype(series)):
            continue
        values = series.dropna().astype(str).unique().tolist()
        for value in values[:500]:
            if str(value).casefold() in prompt:
                return {"column": column, "operator": "contains", "value": str(value)}
    for index, column_name in enumerate(lowered_columns):
        if column_name in prompt:
            return None
    return None


def _parse_top_category(prompt: str, dataframe: pd.DataFrame) -> tuple[str, int] | None:
    match = re.search(r"top\s+([0-9]+)\s+([a-z0-9 _-]+)", prompt)
    if not match:
        return None
    limit_text, field_text = match.groups()
    column = _find_prompt_column(field_text, dataframe, numeric_only=False)
    if not column:
        return None
    return column, min(max(int(limit_text), 1), 25)


def _find_prompt_column(text: str, dataframe: pd.DataFrame, numeric_only: bool) -> str | None:
    normalized_text = text.casefold().strip()
    candidates = [column for column in dataframe.columns if not numeric_only or pd.api.types.is_numeric_dtype(dataframe[column])]
    for column in candidates:
        normalized_column = str(column).casefold()
        singular_column = normalized_column.rstrip("s")
        if normalized_column in normalized_text or singular_column in normalized_text:
            return column
    return None


def _dashboard_state_summary() -> str:
    filters = st.session_state.get("dashboard_filters", [])
    parts = []
    if st.session_state.get("show_missing_only", False):
        parts.append("missing-value rows")
    if st.session_state.get("drop_missing_rows", False):
        parts.append("missing rows excluded")
    if st.session_state.get("show_outliers_only", False):
        parts.append("potential outlier rows")
    parts.extend(f"{item['column']} {item['operator']} {item['value']}" for item in filters)
    if not parts:
        return ""
    return "Active dashboard filter: " + "; ".join(parts)


def _build_requested_chart(dataframe: pd.DataFrame):
    requested_chart = st.session_state.get("requested_chart")
    if not requested_chart:
        return None
    x_column = requested_chart.get("x")
    y_column = requested_chart.get("y")
    if x_column not in dataframe.columns or y_column not in dataframe.columns:
        return None
    chart_frame = dataframe[[x_column, y_column]].dropna()
    if chart_frame.empty:
        return None
    if pd.api.types.is_numeric_dtype(chart_frame[x_column]) and pd.api.types.is_numeric_dtype(chart_frame[y_column]):
        figure = px.scatter(chart_frame, x=x_column, y=y_column, title=f"{y_column} vs {x_column}")
    elif pd.api.types.is_numeric_dtype(chart_frame[y_column]):
        grouped = chart_frame.groupby(x_column, dropna=False, as_index=False)[y_column].mean().head(30)
        figure = px.bar(grouped, x=x_column, y=y_column, title=f"Average {y_column} by {x_column}")
    else:
        counts = chart_frame[x_column].astype(str).value_counts().head(30).reset_index()
        counts.columns = [x_column, "Rows"]
        figure = px.bar(counts, x=x_column, y="Rows", title=f"Rows by {x_column}")
    figure.update_layout(template="plotly_white", margin={"l": 24, "r": 24, "t": 56, "b": 24})
    return figure


def _outlier_mask(dataframe: pd.DataFrame) -> pd.Series:
    mask = pd.Series(False, index=dataframe.index)
    numeric_columns = [column for column in dataframe.columns if pd.api.types.is_numeric_dtype(dataframe[column])]
    for column in numeric_columns:
        values = dataframe[column].dropna()
        if len(values) < 4:
            continue
        first_quartile = values.quantile(0.25)
        third_quartile = values.quantile(0.75)
        interquartile_range = third_quartile - first_quartile
        if interquartile_range == 0:
            continue
        lower_bound = first_quartile - (1.5 * interquartile_range)
        upper_bound = third_quartile + (1.5 * interquartile_range)
        mask.loc[values.index] = mask.loc[values.index] | (values < lower_bound) | (values > upper_bound)
    return mask


def _suggested_questions(dataset_type: str) -> list[str]:
    if dataset_type == "Healthcare":
        return ["Show missing values", "Top 10 diagnoses", "Show outliers"]
    if dataset_type == "Sales":
        return ["Top 10 customers", "Show missing values", "Reset filters"]
    if dataset_type == "Inventory":
        return ["Top 10 suppliers", "Show outliers", "Reset filters"]
    if dataset_type == "Vehicle Listings":
        return ["Show Toyota only", "Filter year after 2020", "Create price vs mileage chart"]
    return ["Show missing values", "Show outliers", "Reset filters"]


def _cleaning_action_unit(action: str) -> str:
    normalized = action.lower()
    if "duplicate" in normalized or "record" in normalized:
        return "Rows"
    if "anomal" in normalized:
        return "Outliers"
    return "Cells"


def _render_health_status(settings) -> None:
    report = build_health_report(settings)
    st.subheader("Deployment Status")
    status_label = "Ready" if report.status == "ready" else "Needs attention"
    st.write(status_label)
    for check in report.checks:
        if check.status == "ok":
            st.success(f"{check.name}: {check.message}")
        elif check.status == "warning":
            st.warning(f"{check.name}: {check.message}")
        else:
            st.error(f"{check.name}: {check.message}")


def _render_dashboard_kpis(kpis) -> None:
    if not kpis:
        st.info("No dashboard KPIs could be generated for this dataset.")
        return
    columns = st.columns(min(len(kpis), 4))
    for index, kpi in enumerate(kpis):
        columns[index % len(columns)].metric(kpi.label, kpi.value, help=kpi.detail)


def _render_cleaning_comparison(comparison) -> None:
    st.subheader("Cleaning Comparison")
    score_columns = st.columns(3)
    score_columns[0].metric("Health Score Before", f"{comparison.health_score_before}%")
    score_columns[1].metric("Health Score After", f"{comparison.health_score_after}%", delta=f"{comparison.health_score_improvement:+d}")
    score_columns[2].metric("Quality Gap Closed", f"{comparison.percentage_improvement:.1f}%")
    st.dataframe(
        [
            {
                "Metric": item.metric,
                "Before Cleaning": item.before,
                "After Cleaning": item.after,
                "Change": item.change,
            }
            for item in comparison.metrics
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Download Cleaning Comparison Report",
        data=comparison.markdown,
        file_name="cleaning_comparison_report.md",
        mime="text/markdown",
        key="cleaning_comparison_report_download",
    )


def _render_saved_table_dashboard(database: DatabaseManager, saved_datasets) -> None:
    st.subheader("Saved Database Dashboard")
    selected = st.selectbox(
        "Saved table",
        saved_datasets,
        format_func=lambda item: f"{item.source_file} ({item.table_name})",
        key="saved_dashboard_table",
    )
    result = database.query_table(selected.table_name, limit=1000)
    dataframe = result.dataframe
    numeric_columns = [column for column in dataframe.columns if str(dataframe[column].dtype).startswith(("int", "float"))]

    summary_columns = st.columns(4)
    summary_columns[0].metric("Rows", f"{selected.row_count:,}")
    summary_columns[1].metric("Columns", f"{selected.column_count:,}")
    summary_columns[2].metric("Numeric Fields", f"{len(numeric_columns):,}")
    summary_columns[3].metric("Missing Values", f"{int(dataframe.isna().sum().sum()):,}")

    st.write("Dataset Summary")
    st.dataframe(database.get_column_metadata(selected.dataset_id), use_container_width=True, hide_index=True)

    chart = build_chart(dataframe)
    st.write("Automatic Chart")
    st.caption(chart.recommendation.reason)
    if chart.recommendation.chart_type == "table":
        st.info("This saved table is best reviewed as a table with the current fields.")
    else:
        st.plotly_chart(chart.figure, use_container_width=True)

    st.write("Automatic Chart Suite")
    _render_chart_suite(dataframe, key_prefix="saved_dashboard")

    st.write("Table Preview")
    st.dataframe(dataframe, use_container_width=True)
    _render_power_bi_export(dataframe, selected.table_name, key_prefix="saved_dashboard")
    _render_executive_report(
        dataframe=dataframe,
        dataset_name=selected.source_file,
        profile_report=generate_profile_report(dataframe),
        key_prefix="saved_dashboard",
    )


def _render_chart_suite(dataframe, key_prefix: str) -> None:
    charts = build_chart_suite(dataframe)
    if not charts:
        st.info("No interactive charts could be generated for this dataset shape.")
        return

    tabs = st.tabs([chart.title[:40] for chart in charts])
    for index, chart in enumerate(charts):
        with tabs[index]:
            st.caption(chart.reason)
            st.plotly_chart(chart.figure, use_container_width=True)
            st.download_button(
                "Download Chart HTML",
                data=chart.html,
                file_name=f"{key_prefix}_{chart.chart_type}_{index + 1}.html",
                mime="text/html",
                key=f"{key_prefix}_{chart.chart_type}_{index}_download",
            )


def _render_data_explorer(dataframe, key_prefix: str):
    filtered = dataframe
    categorical_columns = [
        column
        for column in dataframe.columns
        if dataframe[column].dtype == "object" and 1 < dataframe[column].nunique(dropna=True) <= 30
    ][:4]

    if categorical_columns:
        st.write("Filters")
        filter_columns = st.columns(len(categorical_columns))
        for index, column in enumerate(categorical_columns):
            options = sorted(dataframe[column].dropna().astype(str).unique().tolist())
            selected = filter_columns[index].multiselect(str(column), options, key=f"{key_prefix}_{column}_filter")
            if selected:
                filtered = filtered[filtered[column].astype(str).isin(selected)]
    else:
        st.info("No compact categorical filters were found for this dataset.")

    search_text = st.text_input("Search", key=f"{key_prefix}_search")
    if search_text:
        text_columns = [column for column in filtered.columns if filtered[column].dtype == "object"]
        if text_columns:
            search_mask = filtered[text_columns].astype(str).apply(
                lambda column: column.str.contains(search_text, case=False, na=False)
            ).any(axis=1)
            filtered = filtered[search_mask]

    st.caption(f"Showing {len(filtered):,} of {len(dataframe):,} cleaned rows")
    st.dataframe(filtered.head(1000), use_container_width=True)
    st.download_button(
        "Download Cleaned CSV",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name=f"{key_prefix}_cleaned_data.csv",
        mime="text/csv",
        key=f"{key_prefix}_cleaned_csv_download",
    )
    return filtered


def _render_executive_report(dataframe, dataset_name: str, profile_report, key_prefix: str, cleaning_summary=None) -> None:
    st.subheader("Executive Report")
    try:
        report = build_executive_report(
            dataframe=dataframe,
            dataset_name=dataset_name,
            profile_report=profile_report,
            cleaning_summary=cleaning_summary,
        )
    except ValueError as exc:
        st.info(str(exc))
        return

    report_columns = st.columns(2)
    report_columns[0].download_button(
        "Download HTML Report",
        data=report.html,
        file_name=report.html_file_name,
        mime="text/html",
        key=f"{key_prefix}_report_html",
    )
    report_columns[1].download_button(
        "Download Markdown Report",
        data=report.markdown,
        file_name=report.markdown_file_name,
        mime="text/markdown",
        key=f"{key_prefix}_report_markdown",
    )


def _render_power_bi_export(dataframe, table_name: str, key_prefix: str) -> None:
    st.subheader("Power BI Export")
    try:
        export = build_power_bi_export(dataframe, table_name=table_name)
    except ValueError as exc:
        st.info(str(exc))
        return

    download_columns = st.columns(3)
    download_columns[0].download_button(
        "Download CSV",
        data=export.csv_bytes,
        file_name=export.csv_file_name,
        mime="text/csv",
        key=f"{key_prefix}_powerbi_csv",
    )
    download_columns[1].download_button(
        "Download Schema JSON",
        data=export.schema_json,
        file_name=export.schema_file_name,
        mime="application/json",
        key=f"{key_prefix}_powerbi_schema",
    )
    download_columns[2].download_button(
        "Download Power Query",
        data=export.power_query_m,
        file_name=export.power_query_file_name,
        mime="text/plain",
        key=f"{key_prefix}_powerbi_m",
    )


def _format_ai_analysis(summary: str, key_findings: list[str], business_recommendations: list[str]) -> str:
    findings = "\n".join(f"{index}. {finding}" for index, finding in enumerate(key_findings, start=1))
    recommendations = "\n".join(
        f"{index}. {recommendation}" for index, recommendation in enumerate(business_recommendations, start=1)
    )
    return (
        f"**Summary**\n\n{summary}\n\n"
        f"**Key Findings**\n\n{findings}\n\n"
        f"**Business Recommendations**\n\n{recommendations}"
    )


def _format_currency(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"${value:,.0f}"


def _format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:,.1f}%"


def _format_integer(value: int | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:,}"


if __name__ == "__main__":
    main()