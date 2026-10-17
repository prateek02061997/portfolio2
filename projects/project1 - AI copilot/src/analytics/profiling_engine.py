"""Automatic data profiling and dataset health scoring."""

from __future__ import annotations

from dataclasses import dataclass
from re import sub
from typing import Literal

import pandas as pd
from pandas.api import types as pd_types


IssueSeverity = Literal["Low", "Medium", "High"]

NUMERIC_PARSE_THRESHOLD = 0.8
MIXED_FORMAT_THRESHOLD = 0.2
OUTLIER_MIN_VALUES = 4


@dataclass(frozen=True)
class ProfileIssue:
    """One detected data quality issue."""

    category: str
    message: str
    severity: IssueSeverity
    affected_rows: int
    field: str | None = None


@dataclass(frozen=True)
class ProfileReport:
    """Data profiling report for one dataset."""

    rows: int
    columns: int
    health_score: int
    missing_values: int
    duplicate_records: int
    issues: list[ProfileIssue]
    recommendations: list[str]


def generate_profile_report(dataframe: pd.DataFrame) -> ProfileReport:
    """Profile a DataFrame for common data quality issues."""
    issues: list[ProfileIssue] = []

    issues.extend(_detect_missing_values(dataframe))
    duplicate_records = int(dataframe.duplicated().sum())
    if duplicate_records:
        issues.append(
            ProfileIssue(
                category="Duplicate records",
                message=f"Duplicate records found: {duplicate_records:,}",
                severity="High",
                affected_rows=duplicate_records,
            )
        )

    for column in dataframe.columns:
        series = dataframe[column]
        field_name = str(column)
        issues.extend(_detect_type_and_format_issues(field_name, series))
        issues.extend(_detect_outliers(field_name, series))
        issues.extend(_detect_inconsistent_categories(field_name, series, len(dataframe)))

    missing_values = int(dataframe.isna().sum().sum())
    health_score = _calculate_health_score(dataframe, issues)
    recommendations = _build_recommendations(issues)

    return ProfileReport(
        rows=len(dataframe),
        columns=len(dataframe.columns),
        health_score=health_score,
        missing_values=missing_values,
        duplicate_records=duplicate_records,
        issues=issues,
        recommendations=recommendations,
    )


def _detect_missing_values(dataframe: pd.DataFrame) -> list[ProfileIssue]:
    issues: list[ProfileIssue] = []
    for column in dataframe.columns:
        missing_count = int(dataframe[column].isna().sum())
        if not missing_count:
            continue

        missing_ratio = missing_count / max(len(dataframe), 1)
        severity: IssueSeverity = "High" if missing_ratio >= 0.2 else "Medium"
        issues.append(
            ProfileIssue(
                category="Missing values",
                field=str(column),
                message=f"Missing values in {column}: {missing_count:,}",
                severity=severity,
                affected_rows=missing_count,
            )
        )
    return issues


def _detect_type_and_format_issues(field_name: str, series: pd.Series) -> list[ProfileIssue]:
    if not (pd_types.is_object_dtype(series) or pd_types.is_string_dtype(series)):
        return []

    non_null = series.dropna().astype(str).str.strip()
    if non_null.empty:
        return []

    issues: list[ProfileIssue] = []
    numeric_ratio = pd.to_numeric(non_null, errors="coerce").notna().mean()
    datetime_ratio = pd.to_datetime(non_null, errors="coerce", format="mixed").notna().mean()

    if numeric_ratio >= NUMERIC_PARSE_THRESHOLD:
        issues.append(
            ProfileIssue(
                category="Wrong data type",
                field=field_name,
                message=f"{field_name} appears numeric but is stored as text.",
                severity="Medium",
                affected_rows=len(non_null),
            )
        )
    elif MIXED_FORMAT_THRESHOLD <= numeric_ratio < NUMERIC_PARSE_THRESHOLD:
        issues.append(
            ProfileIssue(
                category="Invalid formats",
                field=field_name,
                message=f"{field_name} contains mixed numeric and non-numeric values.",
                severity="Medium",
                affected_rows=int(len(non_null) - pd.to_numeric(non_null, errors="coerce").notna().sum()),
            )
        )

    if _looks_like_date_field(field_name) and MIXED_FORMAT_THRESHOLD <= datetime_ratio < NUMERIC_PARSE_THRESHOLD:
        issues.append(
            ProfileIssue(
                category="Invalid formats",
                field=field_name,
                message=f"{field_name} contains invalid or inconsistent date values.",
                severity="Medium",
                affected_rows=int(len(non_null) - pd.to_datetime(non_null, errors="coerce", format="mixed").notna().sum()),
            )
        )

    return issues


def _detect_outliers(field_name: str, series: pd.Series) -> list[ProfileIssue]:
    if not pd_types.is_numeric_dtype(series):
        return []

    values = series.dropna()
    if len(values) < OUTLIER_MIN_VALUES:
        return []

    first_quartile = values.quantile(0.25)
    third_quartile = values.quantile(0.75)
    interquartile_range = third_quartile - first_quartile
    if interquartile_range == 0:
        return []

    lower_bound = first_quartile - (1.5 * interquartile_range)
    upper_bound = third_quartile + (1.5 * interquartile_range)
    outlier_count = int(((values < lower_bound) | (values > upper_bound)).sum())
    if not outlier_count:
        return []

    return [
        ProfileIssue(
            category="Outliers",
            field=field_name,
            message=f"Outliers detected in {field_name}: {outlier_count:,}",
            severity="Medium",
            affected_rows=outlier_count,
        )
    ]


def _detect_inconsistent_categories(field_name: str, series: pd.Series, row_count: int) -> list[ProfileIssue]:
    if not (pd_types.is_object_dtype(series) or pd_types.is_string_dtype(series)):
        return []

    values = series.dropna().astype(str).str.strip()
    if values.empty:
        return []

    unique_count = values.nunique()
    max_category_count = min(100, max(20, int(row_count * 0.2)))
    if unique_count > max_category_count:
        return []

    normalized = values.map(_normalize_category)
    inconsistent_groups = 0
    for normalized_value in normalized.unique():
        originals = values[normalized == normalized_value].unique()
        if len(originals) > 1:
            inconsistent_groups += 1

    if not inconsistent_groups:
        return []

    return [
        ProfileIssue(
            category="Inconsistent categories",
            field=field_name,
            message=f"{field_name} has inconsistent category labels in {inconsistent_groups:,} group(s).",
            severity="Low",
            affected_rows=inconsistent_groups,
        )
    ]


def _calculate_health_score(dataframe: pd.DataFrame, issues: list[ProfileIssue]) -> int:
    possible_cells = max(len(dataframe) * max(len(dataframe.columns), 1), 1)
    severity_weights = {"Low": 1, "Medium": 3, "High": 5}
    penalty = sum(severity_weights[issue.severity] * max(issue.affected_rows, 1) for issue in issues)
    penalty_ratio = min(penalty / possible_cells, 1)
    return max(0, min(100, round(100 - (penalty_ratio * 100))))


def _build_recommendations(issues: list[ProfileIssue]) -> list[str]:
    if not issues:
        return ["Dataset is ready for initial analysis."]

    categories = {issue.category for issue in issues}
    recommendations: list[str] = []
    if "Missing values" in categories:
        recommendations.append("Review missing values before analysis and decide whether to fill, remove, or flag them.")
    if "Duplicate records" in categories:
        recommendations.append("Remove duplicate records before calculating KPIs.")
    if "Wrong data type" in categories or "Invalid formats" in categories:
        recommendations.append("Standardise data types and invalid formats before loading into analytics tables.")
    if "Outliers" in categories:
        recommendations.append("Validate outliers with business rules before excluding them.")
    if "Inconsistent categories" in categories:
        recommendations.append("Standardise category labels so filters and group-by analysis are reliable.")
    return recommendations


def _looks_like_date_field(field_name: str) -> bool:
    lower_name = field_name.lower()
    return "date" in lower_name or "time" in lower_name


def _normalize_category(value: str) -> str:
    return sub(r"\s+", " ", value.strip().casefold())