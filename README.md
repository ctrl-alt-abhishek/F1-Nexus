# 🏎️ F1 Nexus: Live Telemetry, Tyre Degradation & Strategy Predictor

[![Next.js](https://img.shields.io/badge/Next.js-14.2-black?logo=next.js&logoColor=white)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?logo=typescript&logoColor=white)](https://typescriptlang.org)
[![XGBoost](https://img.shields.io/badge/XGBoost-2.0+-orange?logo=xgboost)](https://xgboost.readthedocs.io)
[![FastF1](https://img.shields.io/badge/FastF1-3.4+-E10600)](https://docs.fastf1.dev)

F1 Nexus is a premium, real-time Formula 1 telemetry visualizer and strategy forecaster. It utilizes machine learning models trained on millions of laps to predict tyre degradation and recommend optimal pit windows during a live Grand Prix weekend.

---

## 🌟 Key Modules & Features

### 1. **Live Race Tower**
- **Real-Time Telemetry**: Broadcasts live sector times, gaps, tyre compound, and tyre age directly from F1's live timing server.
- **ML Stint End Predictor (`Est Stop`)**: Runs our custom XGBoost degradation model on incoming telemetry to recommend the exact lap a driver should pit.
- **Graceful Off-Hours Fallback**: During off-hours, the live tower automatically transitions to a high-fidelity replay simulation (using the 2024 Canadian GP data) after a 15-second timeout.
- **Dynamic Header & Metadata**: Automatically adapts to show live session name, location, and lap number when active.

### 2. **Upcoming Race Countdown**
- **IST Localized Scheduling**: Automatically parses upcoming UTC sessions and converts them to Indian Standard Time (IST) (e.g., `May 25, 2026, 01:30 AM IST`), dynamically handling timezone dates.
- **Telemetry Status Indicator**: Visual status panel detailing connection state to the Live Timing API.

### 3. **Interactive Dashboard**
- **At-A-Glance Overview**: Live status monitor, Next Race tracker, and recent races telemetry cards.
- **Championship Predictor**: Dynamic Monte Carlo simulation results mapping expected driver final points and title probabilities.

### 4. **Championship Forecast (Monte Carlo)**
- Runs **10,000 seasonal simulations** in the backend using historical stats, constructor power rankings, and driver variance to calculate championship probability, podium probability, and expected final standing points.

### 5. **Nexus AI (RAG Chat)**
- Natural language interface allowing users to ask questions like *"Compare Verstappen and Leclerc's medium tyre degradation in Montreal"* or *"What was Hamilton's sector 2 delta on lap 32?"*.
- Converts prompt queries into SQL queries on-the-fly to query our telemetry database directly.

---

## 🛠️ Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | Next.js 14 (App Router), React, TypeScript, Tailwind CSS, Lucide icons, websockets |
| **Backend** | FastAPI, Python 3.10+, SQLAlchemy, Uvicorn |
| **Database** | Neon Serverless PostgreSQL |
| **ML Engine** | XGBoost Regression, Scikit-learn, Pandas, NumPy |
| **Data Source** | FastF1 API (SignalR timing client integration) |
| **Auth & Profiles** | Firebase Auth, Google Sign-In, Cloud Firestore |

---

## 📂 Project Structure

```
f1_degradation_app/
├── backend/
│   ├── app/
│   │   ├── ml/                 # XGBoost training & Monte Carlo scripts
│   │   ├── models/             # SQLAlchemy schemas
│   │   ├── routers/            # FastAPI WebSocket & REST endpoints
│   │   └── services/           # Live timing worker (MemorySignalRClient)
│   ├── .env                    # Backend environment config
│   └── pyproject.toml          # Poetry package config
├── frontend/
│   ├── src/
│   │   ├── app/                # Next.js pages (/dashboard, /live, /predictions)
│   │   ├── components/         # Premium glassmorphism UI components
│   │   └── lib/                # API helpers and Shared WebSocket client
│   ├── .env.local              # Frontend environment config
│   └── package.json            # Node dependencies
└── README.md
```

---

## 🚀 Getting Started

### 1. Backend Setup

1. Navigate to the backend folder:
   ```bash
   cd backend
   ```
2. Install dependencies:
   ```bash
   poetry install
   ```
3. Configure your environment variables in `.env` (copy from `.env.example`).
4. Start the FastAPI server:
   ```bash
   .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
   ```

### 2. Frontend Setup

1. Navigate to the frontend folder:
   ```bash
   cd ../frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Configure API and WebSocket URLs in `.env.local`:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
   NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1/live/ws
   ```
4. Start the Next.js development server:
   ```bash
   npm run dev
   ```

Open [http://localhost:3000](http://localhost:3000) in your browser to view the application.

---

*Built with passion for F1 racing and data science.*
