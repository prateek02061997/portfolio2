import pathlib

import matplotlib.pyplot as plt
import pandas as pd
from prophet import Prophet

DATA_PATH = pathlib.Path(__file__).resolve().parents[1] / "data" / "sample_demand.csv"
OUTPUT_DIR = pathlib.Path(__file__).resolve().parents[1] / "outputs"


def load_data() -> pd.DataFrame:
    data = pd.read_csv(DATA_PATH)
    data["ds"] = pd.to_datetime(data["ds"])
    return data


def build_forecast(data: pd.DataFrame) -> pd.DataFrame:
    model = Prophet()
    model.fit(data)
    future = model.make_future_dataframe(periods=8, freq="W")
    forecast = model.predict(future)
    return forecast


def save_chart(model: Prophet, forecast: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig = model.plot(forecast)
    fig.suptitle("Weekly Demand Forecast")
    fig_path = OUTPUT_DIR / "weekly_forecast.png"
    fig.savefig(fig_path, dpi=150, bbox_inches="tight")


def save_table(forecast: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    table = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].tail(8)
    table_path = OUTPUT_DIR / "next_8_weeks.csv"
    table.to_csv(table_path, index=False)


def main() -> None:
    data = load_data()
    model = Prophet()
    model.fit(data)
    forecast = model.predict(model.make_future_dataframe(periods=8, freq="W"))
    save_chart(model, forecast)
    save_table(forecast)


if __name__ == "__main__":
    main()
