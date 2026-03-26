# F1 Lap Time Degradation Analyzer

A Streamlit web app that uses the FastF1 API to pull real Formula 1 race data, trains an XGBoost model to predict lap time degradation across tire stints, and visualizes the results interactively.

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deployment

### Streamlit Community Cloud (recommended)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo and select `app.py` as the entry point
4. Deploy — it will auto-install from `requirements.txt`

### Render

1. Push this repo to GitHub
2. Create a new **Web Service** on [render.com](https://render.com)
3. Connect your repo
4. Set:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `streamlit run app.py --server.port $PORT --server.headless true --server.address 0.0.0.0`
5. Deploy

## Project Structure

```
f1_degradation_app/
├── app.py                  # Streamlit entry point
├── data/
│   └── loader.py           # FastF1 data fetching + caching
├── features/
│   └── engineer.py         # Feature engineering pipeline
├── model/
│   ├── train.py            # Model training + evaluation
│   └── predict.py          # Inference helpers
├── assets/
│   ├── fonts/              # Formula1 font files
│   └── f1_logo.png         # F1 logo
├── .streamlit/
│   └── config.toml         # Theme + server config
├── cache/                  # FastF1 cache (gitignored)
├── Procfile                # Render deployment
├── requirements.txt
└── README.md
```

## Tech Stack

| Layer | Technology |
|---|---|
| Data | FastF1, pandas, numpy |
| ML | XGBoost (scikit-learn fallback) |
| Visualization | Plotly |
| Frontend | Streamlit |
