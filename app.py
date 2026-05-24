"""
app.py - Streamlit entry point for the F1 Lap Time Degradation Analyzer.
"""

import sys
import os
import base64

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from data.loader import get_session, get_race_laps, get_race_info
from features.engineer import build_features, COMPOUND_MAP
from model.train import train_model
from model.predict import predict_stint, build_degradation_curve


def _font_face(name, filename, weight="normal", style="normal"):
    font_path = os.path.join(os.path.dirname(__file__), "assets", "fonts", filename)
    with open(font_path, "rb") as f:
        font_b64 = base64.b64encode(f.read()).decode()
    return f"""
    @font-face {{
        font-family: '{name}';
        src: url(data:font/truetype;base64,{font_b64}) format('truetype');
        font-weight: {weight};
        font-style: {style};
    }}"""


def _logo_html():
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "f1_logo.png")
    with open(logo_path, "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode()
    return f'<img src="data:image/png;base64,{logo_b64}" style="height:48px;">'


st.set_page_config(
    page_title="F1 Lap Time Degradation Analyzer",
    page_icon="🏎️",
    layout="wide",
)

_font_css = "".join([
    _font_face("Formula1", "Formula1-Regular-1.ttf", "400", "normal"),
    _font_face("Formula1", "Formula1-Bold-4.ttf", "700", "normal"),
    _font_face("Formula1", "Formula1-Italic.ttf", "400", "italic"),
    _font_face("Formula1", "Formula1-Wide.ttf", "800", "normal"),
])

st.markdown(f"""
<style>
{_font_css}

html, body, [class*="st-"] {{
    font-family: 'Formula1', sans-serif !important;
    font-weight: 400;
}}

.stApp {{
    background-color: #000000;
}}

h1, h2, h3, h4, h5, h6,
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {{
    font-family: 'Formula1', sans-serif !important;
    font-weight: 700 !important;
    color: #FFFFFF !important;
    letter-spacing: 0.5px;
}}

.stCaption, .stMarkdown small, .stTooltipIcon,
div[data-testid="stCaptionContainer"] p {{
    font-family: 'Formula1', sans-serif !important;
    font-style: italic !important;
    color: #A0A0A0 !important;
}}

section[data-testid="stSidebar"] {{
    background-color: #0A0A0A !important;
    border-right: 2px solid #E10600;
}}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {{
    color: #E10600 !important;
}}

.stButton > button {{
    background-color: #E10600 !important;
    color: #FFFFFF !important;
    font-family: 'Formula1', sans-serif !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 4px !important;
    padding: 0.6rem 1.2rem !important;
    letter-spacing: 0.5px;
    transition: all 0.2s ease;
}}
.stButton > button:hover {{
    background-color: #FF1801 !important;
    box-shadow: 0 0 20px rgba(225, 6, 0, 0.4);
    transform: translateY(-1px);
}}

div[data-testid="stMetric"] {{
    background: linear-gradient(135deg, #0A0A0A 0%, #111111 100%);
    border: 1px solid #222;
    border-left: 3px solid #E10600;
    border-radius: 6px;
    padding: 16px 20px;
}}
div[data-testid="stMetric"] label {{
    font-family: 'Formula1', sans-serif !important;
    font-weight: 700 !important;
    color: #A0A0A0 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 1px;
}}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
    font-family: 'Formula1', sans-serif !important;
    font-weight: 700 !important;
    color: #FFFFFF !important;
    overflow: visible !important;
    white-space: normal !important;
    word-wrap: break-word !important;
    text-overflow: unset !important;
    font-size: 1.2rem !important;
    line-height: 1.3;
}}

div[data-baseweb="select"] {{
    font-family: 'Formula1', sans-serif !important;
}}

hr {{
    border: none;
    height: 1px;
    background: linear-gradient(90deg, #E10600, #333, transparent);
}}

.f1-header {{
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px 0 16px 0;
    border-bottom: 3px solid #E10600;
    margin-bottom: 24px;
}}
.f1-header h1 {{
    margin: 0 !important;
    font-size: 1.8rem !important;
    font-weight: 700 !important;
    color: #FFFFFF !important;
    line-height: 1.2;
}}
.f1-header .subtitle {{
    font-size: 0.85rem;
    color: #A0A0A0;
    font-style: italic;
    margin-top: 2px;
}}

.race-banner {{
    background: linear-gradient(135deg, #0A0A0A 0%, #111111 100%);
    border: 1px solid #222;
    border-top: 3px solid #E10600;
    border-radius: 8px;
    padding: 20px 24px;
    margin: 16px 0;
}}
.race-banner h2 {{
    margin: 0 0 4px 0 !important;
    font-size: 1.5rem !important;
}}
.race-banner .date {{
    color: #A0A0A0;
    font-style: italic;
    font-size: 0.85rem;
}}

.section-header {{
    font-family: 'Formula1', sans-serif;
    font-weight: 700;
    font-size: 1.15rem;
    color: #FFFFFF;
    border-left: 3px solid #E10600;
    padding-left: 12px;
    margin: 24px 0 8px 0;
}}

header[data-testid="stHeader"] {{
    background: #000000 !important;
}}

@media (max-width: 768px) {{
    .f1-header {{
        flex-direction: column;
        align-items: flex-start;
        gap: 8px;
    }}
    .f1-header h1 {{
        font-size: 1.2rem !important;
    }}
    .f1-header .subtitle {{
        font-size: 0.75rem;
    }}
    .race-banner {{
        padding: 14px 16px;
    }}
    .race-banner h2 {{
        font-size: 1.1rem !important;
    }}
    .section-header {{
        font-size: 1rem;
    }}
    div[data-testid="stMetric"] {{
        padding: 10px 14px;
    }}
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
        font-size: 0.95rem !important;
    }}
    div[data-testid="stHorizontalBlock"] {{
        flex-direction: column !important;
    }}
}}
</style>
""", unsafe_allow_html=True)


st.markdown(f"""
<div class="f1-header">
    {_logo_html()}
    <div>
        <h1>LAP TIME DEGRADATION ANALYZER</h1>
        <div class="subtitle">Tire performance prediction using real race data and machine learning</div>
    </div>
</div>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def load_session_cached(year: int, round_number: int):
    return get_session(year, round_number)


@st.cache_data(show_spinner=False)
def load_data(year: int, round_number: int):
    session = load_session_cached(year, round_number)
    laps = get_race_laps(session)
    return laps


F1_CHART_TEMPLATE = go.layout.Template(
    layout=go.Layout(
        paper_bgcolor="#000000",
        plot_bgcolor="#0A0A0A",
        font=dict(family="Formula1, sans-serif", color="#FFFFFF", size=12),
        xaxis=dict(
            gridcolor="#333333", zerolinecolor="#333333",
            title_font=dict(size=13, color="#A0A0A0"),
            tickfont=dict(size=11, color="#888"),
        ),
        yaxis=dict(
            gridcolor="#333333", zerolinecolor="#333333",
            title_font=dict(size=13, color="#A0A0A0"),
            tickfont=dict(size=11, color="#888"),
        ),
        legend=dict(
            bgcolor="rgba(10,10,10,0.9)",
            bordercolor="#222",
            borderwidth=1,
            font=dict(size=10, color="#CCC"),
        ),
        colorway=["#E10600", "#FFFFFF", "#FFC300", "#00D2BE",
                   "#FF8700", "#0090FF", "#006F62", "#B6BABD"],
    )
)


with st.sidebar:
    st.markdown("### CONTROLS")
    st.caption("Select a race weekend, then load and analyze the data.")

    season = st.selectbox(
        "Season",
        options=[2025, 2024, 2023, 2022],
        index=0,
        help="The year the race took place.",
    )
    round_num = st.selectbox(
        "Round",
        options=list(range(1, 23)),
        index=4,
        help="Each season has approximately 22 races numbered in calendar order.",
    )

    if "laps_df" in st.session_state and st.session_state.get("loaded_key") == (
        season,
        round_num,
    ):
        available_drivers = sorted(
            st.session_state["laps_df"]["Driver"].unique().tolist()
        )
    else:
        available_drivers = []

    drivers = st.multiselect(
        "Drivers",
        options=available_drivers,
        default=available_drivers[:3] if available_drivers else [],
        help="Driver codes (e.g. VER = Verstappen). Load data first to populate.",
    )

    load_btn = st.button("LOAD & TRAIN", type="primary", use_container_width=True)

if load_btn:
    with st.spinner("Loading race data and training model..."):
        laps_df = load_data(season, round_num)
        st.session_state["laps_df"] = laps_df
        st.session_state["loaded_key"] = (season, round_num)

        session_obj = load_session_cached(season, round_num)
        race_info = get_race_info(session_obj)
        st.session_state["race_info"] = race_info

        if drivers:
            laps_df = laps_df[laps_df["Driver"].isin(drivers)].reset_index(drop=True)

        if laps_df.empty:
            st.error("No valid laps found after filtering. Try different settings.")
            st.stop()

        X, y = build_features(laps_df)
        st.write(f"Feature matrix: **{X.shape[0]}** laps, **{X.shape[1]}** features")

        results = train_model(X, y)

        st.session_state["results"] = results
        st.session_state["X"] = X
        st.session_state["y"] = y
        st.session_state["filtered_laps"] = laps_df

    if not drivers:
        st.rerun()

if "results" in st.session_state:
    results = st.session_state["results"]
    model = results["model"]
    rmse = results["rmse"]
    mae = results["mae"]
    importance = results["feature_importance"]
    X = st.session_state["X"]
    y = st.session_state["y"]
    laps_df = st.session_state["filtered_laps"]

    if "race_info" in st.session_state:
        info = st.session_state["race_info"]
        st.markdown(f"""
        <div class="race-banner">
            <h2>{info['race_name']}</h2>
            <div class="date">{info['date']}</div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("WINNER", info["winner"])
        c2.metric("POLE POSITION", info["pole_sitter"])
        c3.metric("FASTEST LAP", info["fastest_lap"])

    st.markdown("---")
    st.markdown('<div class="section-header">MODEL ACCURACY</div>', unsafe_allow_html=True)
    st.caption(
        "How close the model's predictions are to the actual lap times. "
        "Both values are in seconds - lower is better."
    )
    col1, col2 = st.columns(2)
    col1.metric(
        "RMSE",
        f"{rmse:.3f} s",
        help="Root Mean Squared Error - average prediction error, penalizing larger mistakes more.",
    )
    col2.metric(
        "MAE",
        f"{mae:.3f} s",
        help="Mean Absolute Error - average prediction error in seconds.",
    )

    st.markdown('<div class="section-header">PREDICTED vs ACTUAL LAP TIMES</div>', unsafe_allow_html=True)
    st.caption(
        "Dots are real lap times from the race. Lines are model predictions. "
        "Each color represents a different driver; gaps indicate a pit stop."
    )

    predictions = predict_stint(model, X)
    chart_df = laps_df[["Driver", "LapNumber", "Stint", "LapTimeSeconds"]].copy()
    chart_df["PredictedLapTime"] = predictions.values

    fig_pred = go.Figure()
    color_palette = ["#E10600", "#00D2BE", "#FFC300", "#0090FF",
                     "#FF8700", "#FFFFFF", "#006F62", "#B6BABD",
                     "#FF87BC", "#64C4FF"]
    driver_list = sorted(chart_df["Driver"].unique())

    for i, driver in enumerate(driver_list):
        driver_data = chart_df[chart_df["Driver"] == driver]
        color = color_palette[i % len(color_palette)]

        for stint in sorted(driver_data["Stint"].unique()):
            stint_data = driver_data[driver_data["Stint"] == stint].sort_values(
                "LapNumber"
            )
            stint_label = f"{driver} S{int(stint)}"

            fig_pred.add_trace(
                go.Scatter(
                    x=stint_data["LapNumber"],
                    y=stint_data["LapTimeSeconds"],
                    mode="markers",
                    name=f"{stint_label} Actual",
                    marker=dict(color=color, size=5, opacity=0.6),
                    legendgroup=stint_label,
                )
            )

            fig_pred.add_trace(
                go.Scatter(
                    x=stint_data["LapNumber"],
                    y=stint_data["PredictedLapTime"],
                    mode="lines",
                    name=f"{stint_label} Predicted",
                    line=dict(color=color, width=2),
                    legendgroup=stint_label,
                )
            )

    fig_pred.update_layout(
        template=F1_CHART_TEMPLATE,
        xaxis_title="Lap Number",
        yaxis_title="Lap Time (s)",
        height=500,
    )
    st.plotly_chart(fig_pred, use_container_width=True)

    st.markdown('<div class="section-header">TIRE DEGRADATION CURVES</div>', unsafe_allow_html=True)
    st.caption(
        "Predicted lap time vs tire age. An upward slope means slower laps as tires wear. "
        "Soft tires degrade fastest; Hard tires last longest but start slower."
    )

    compounds_in_race = laps_df["Compound"].unique()
    total_laps = int(laps_df["LapNumber"].max())
    median_driver = int(X["driver_enc"].median())

    fig_deg = go.Figure()
    deg_colors = {
        "SOFT": "#E10600", "MEDIUM": "#FFC300", "HARD": "#DDDDDD",
        "INTERMEDIATE": "#39B54A", "WET": "#0090FF",
    }

    for compound_str in compounds_in_race:
        comp_enc = COMPOUND_MAP.get(compound_str, 1)
        max_age = int(
            laps_df[laps_df["Compound"] == compound_str]["TyreLife"].max()
        )
        max_age = min(max_age, 40)

        curve = build_degradation_curve(
            model=model,
            compound=comp_enc,
            max_tire_age=max_age,
            driver_enc=median_driver,
            stint_number=1,
            lap_start=1,
            total_laps=total_laps,
        )

        fig_deg.add_trace(
            go.Scatter(
                x=curve["tire_age"],
                y=curve["predicted_time"],
                mode="lines+markers",
                name=compound_str,
                line=dict(
                    color=deg_colors.get(compound_str, "#AAAAAA"), width=3
                ),
                marker=dict(size=4),
            )
        )

    fig_deg.update_layout(
        template=F1_CHART_TEMPLATE,
        xaxis_title="Tire Age (laps)",
        yaxis_title="Predicted Lap Time (s)",
        height=450,
    )
    st.plotly_chart(fig_deg, use_container_width=True)

    st.markdown('<div class="section-header">FEATURE IMPORTANCE</div>', unsafe_allow_html=True)
    st.caption(
        "Which input variables the model relies on most. "
        "A longer bar means greater influence on the predicted lap time."
    )

    FEATURE_LABELS = {
        "tire_age": "Tire Age",
        "compound_enc": "Tire Compound",
        "lap_number": "Lap Number",
        "fuel_load_proxy": "Fuel Load",
        "driver_enc": "Driver",
        "stint_number": "Stint",
    }

    top_features = importance.head(6).sort_values(ascending=True)
    top_features.index = [FEATURE_LABELS.get(f, f) for f in top_features.index]

    fig_imp = go.Figure(
        go.Bar(
            x=top_features.values,
            y=top_features.index,
            orientation="h",
            marker_color=["#E10600"] * len(top_features),
        )
    )
    fig_imp.update_layout(
        template=F1_CHART_TEMPLATE,
        xaxis_title="Importance",
        yaxis_title="",
        height=350,
    )
    st.plotly_chart(fig_imp, use_container_width=True)

else:
    st.markdown(
        "Use the sidebar to select a season and round, then click **LOAD & TRAIN** to begin.",
    )
