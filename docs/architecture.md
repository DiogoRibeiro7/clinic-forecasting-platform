# Architecture

The PoC follows a simple production-oriented architecture.

```text
Data sources
  ├── clinic usage history
  ├── marketing campaigns
  ├── clinic metadata
  └── calendar data
        ↓
Feature pipeline
        ↓
Forecasting models
  ├── baselines
  ├── SARIMAX
  ├── Prophet optional
  ├── global ML model
  ├── LSTM optional
  └── TimeGPT optional
        ↓
Evaluation layer
        ↓
Staffing decision layer
        ↓
Reports / API / dashboards
```

The notebooks show the analytical PoC. The package under `src/clinic_forecast` contains reusable code that can be tested and moved into production pipelines.
