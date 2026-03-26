# 🏎️ F1 Lap Time Degradation Analyzer

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![XGBoost](https://img.shields.io/badge/XGBoost-2.0+-orange?logo=xgboost)](https://xgboost.readthedocs.io)
[![FastF1](https://img.shields.io/badge/FastF1-3.3+-E10600)](https://docs.fastf1.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

ML-powered F1 tire degradation analyzer — predicts lap time decay using real race data from FastF1, built with Streamlit, XGBoost, and Plotly. Styled with official F1 branding.

---

## Features

- **Real F1 Data** — Pulls official lap-by-lap timing data from any race (2022–2025) via the FastF1 API
- **ML Predictions** — Trains an XGBoost regression model to predict lap times based on tire age, compound, fuel load, and more
- **Interactive Charts** — Plotly-powered visualizations: predicted vs actual lap times, tire degradation curves, and feature importance
- **Race Info** — Displays race name, date, winner, pole sitter, and fastest lap automatically
- **F1 Design Language** — Pure black OLED-optimized theme with Formula1 typography and official branding
- **Mobile Responsive** — Works on desktop and mobile browsers

## Tech Stack

| Layer | Technology |
|---|---|
| Data Source | FastF1 API |
| ML Model | XGBoost (scikit-learn fallback) |
| Data Processing | pandas, NumPy |
| Visualization | Plotly |
| Frontend | Streamlit |

## Getting Started

### Prerequisites

- Python 3.10+

### Installation

```bash
git clone https://github.com/ctrl-alt-abhishek/F1-tyre-degradation-app
cd F1-tyre-degradation-app
pip install -r requirements.txt
```

### Usage

```bash
streamlit run app.py
```

1. Select a **Season** and **Round** from the sidebar
2. Click **LOAD & TRAIN**
3. Choose drivers from the populated list
4. Explore the charts and model metrics


## Project Structure

```
f1_degradation_app/
├── app.py                  # Streamlit UI entry point
├── data/
│   └── loader.py           # FastF1 data fetching + caching
├── features/
│   └── engineer.py         # Feature engineering pipeline
├── model/
│   ├── train.py            # Model training + evaluation
│   └── predict.py          # Inference + degradation curves
├── assets/
│   ├── fonts/              # Formula1 font files
│   └── f1_logo.png         # F1 logo
├── .streamlit/
│   └── config.toml         # Theme + server config
├── Procfile                # Render deployment
├── requirements.txt
└── README.md
```

## How It Works

1. **Data Loading** — FastF1 fetches lap-level timing data for the selected race, cached locally to avoid re-downloading
2. **Cleaning** — Filters out pit laps, safety car periods, and outliers
3. **Feature Engineering** — Builds 6 features: tire age, compound type, lap number, fuel load proxy, driver identity, stint number
4. **Training** — XGBoost regressor trained on 80/20 split to predict lap time in seconds
5. **Visualization** — Predicted vs actual comparison, degradation curves per compound, and feature importance ranking

## License

This project is for educational purposes.

---

*Built with [FastF1](https://docs.fastf1.dev) · [Streamlit](https://streamlit.io) · [XGBoost](https://xgboost.readthedocs.io) · [Plotly](https://plotly.com)*
