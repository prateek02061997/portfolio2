# AI-Powered Retail Demand Forecasting System

## Goal
Build a forecasting model that predicts weekly demand to reduce inventory wastage by an estimated 15%.

## What I Did
- Gathered requirements from retail stakeholders around stock-outs and wastage.
- Built a Python-based forecasting workflow using Prophet.
- Communicated findings with business-friendly visuals and summary metrics.

## Data
Sample data is included in data/sample_demand.csv. Replace it with real sales data for production use.

## How To Run
1. Create a Python environment.
2. Install dependencies from requirements.txt.
3. Run the script:
   python src/forecast.py

## Outputs
- Forecast chart with historical vs predicted demand.
- Weekly forecast table for the next 8 weeks.

## Next Steps
- Add holiday and promotion effects.
- Compare Prophet against XGBoost or ARIMA.
- Deploy as a scheduled pipeline.
