# F1 Nexus — Full Project Specification

> **For Claude Opus (coding agent):** This document is the single source of truth for the F1 Nexus project. Build every module described here completely — no stubs, no TODOs, no placeholder implementations. When in doubt about a design decision, choose the simpler approach and document your reasoning in a comment.

---

## 0. Project Summary

F1 Nexus is a full-stack Formula 1 intelligence platform. It ingests historical and live race telemetry via the FastF1 API, runs multiple ML models for prediction and analysis, and exposes everything through a Next.js web app with Firebase-based user accounts.

Users can follow specific drivers and constructors, get personalised race predictions, watch a live race tower during race weekends, and query the entire F1 dataset in natural language via an AI chat interface.

**What this is not:** a scraper of the official F1 website, a real-time betting tool, or a mobile app. It is a web platform and portfolio project.

---

## 1. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Next.js 14 (App Router) | React server + client components |
| Styling | Tailwind CSS | Dark theme by default, F1-inspired |
| Auth | Firebase Authentication | Google OAuth + email/password |
| User data | Firestore | Preferences, watchlists, notification settings |
| Backend | FastAPI (Python 3.11+) | REST + WebSocket endpoints |
| ML | scikit-learn, XGBoost, statsmodels | Per-module requirements listed below |
| Race data | FastF1 ≥ 3.3.0 | Historical + live timing |
| Database | PostgreSQL 15 | All race/lap/telemetry data |
| ORM | SQLAlchemy 2.0 + Alembic | Migrations required |
| Cache | Redis | Session cache, live timing buffer |
| AI chat | Anthropic Claude API (claude-sonnet-4-20250514) | RAG over PostgreSQL |
| Notifications | Firebase Cloud Messaging + python-telegram-bot | Push + Telegram |
| Deployment | Railway (backend) + Vercel (frontend) | Both free tier compatible |
| Package mgmt | Poetry (backend), pnpm (frontend) | |

---

## 2. Repository Structure

Generate this structure exactly. Every file listed must be created with a working implementation.

```
f1-nexus/
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/          # migration files go here
│   ├── app/
│   │   ├── main.py            # FastAPI app entry point
│   │   ├── config.py          # env var loading via pydantic-settings
│   │   ├── database.py        # SQLAlchemy engine + session
│   │   ├── firebase.py        # Firebase Admin SDK init + token verification
│   │   ├── models/
│   │   │   ├── sql.py         # SQLAlchemy ORM models
│   │   │   └── schemas.py     # Pydantic request/response schemas
│   │   ├── routers/
│   │   │   ├── auth.py        # /auth/* endpoints
│   │   │   ├── races.py       # /races/* endpoints
│   │   │   ├── drivers.py     # /drivers/* endpoints
│   │   │   ├── predictions.py # /predictions/* endpoints
│   │   │   ├── live.py        # /live/* WebSocket endpoint
│   │   │   ├── chat.py        # /chat/* AI chat endpoint
│   │   │   └── users.py       # /users/* user preferences endpoints
│   │   ├── services/
│   │   │   ├── fastf1_loader.py      # FastF1 data fetching + caching
│   │   │   ├── live_timing.py        # FastF1 live timing worker
│   │   │   └── notifications.py      # FCM + Telegram notification sender
│   │   └── ml/
│   │       ├── degradation/
│   │       │   ├── features.py       # Feature engineering
│   │       │   ├── train.py          # Model training
│   │       │   └── predict.py        # Inference
│   │       ├── strategy/
│   │       │   ├── features.py
│   │       │   ├── train.py
│   │       │   └── predict.py
│   │       ├── overtake/
│   │       │   ├── features.py
│   │       │   ├── train.py
│   │       │   └── predict.py
│   │       ├── driver_style/
│   │       │   ├── features.py
│   │       │   ├── cluster.py
│   │       │   └── fingerprint.py
│   │       ├── season_prediction/
│   │       │   ├── monte_carlo.py    # Championship probability simulator
│   │       │   └── circuit_model.py  # Per-circuit driver performance model
│   │       └── chat_rag/
│   │           ├── retriever.py      # SQL query generator from natural language
│   │           └── responder.py      # Claude API call with retrieved context
│   └── scripts/
│       ├── seed_data.py       # Initial historical data load (2022–2024)
│       └── train_all.py       # Train + save all ML models
├── frontend/
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   ├── app/
│   │   ├── layout.tsx         # Root layout with Firebase provider
│   │   ├── page.tsx           # Landing / redirect to dashboard
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── signup/page.tsx
│   │   ├── dashboard/
│   │   │   └── page.tsx       # Personalised home — followed drivers, next race
│   │   ├── live/
│   │   │   └── page.tsx       # Live race tower (WebSocket)
│   │   ├── races/
│   │   │   ├── page.tsx       # Season race list
│   │   │   └── [year]/[round]/page.tsx   # Single race analysis
│   │   ├── drivers/
│   │   │   ├── page.tsx       # Driver grid
│   │   │   └── [code]/page.tsx           # Driver profile + telemetry
│   │   ├── constructors/
│   │   │   └── page.tsx       # Constructor standings + analysis
│   │   ├── predictions/
│   │   │   └── page.tsx       # Championship predictions + user personalisation
│   │   ├── chat/
│   │   │   └── page.tsx       # AI chat interface
│   │   └── settings/
│   │       └── page.tsx       # Followed drivers, notification prefs
│   ├── components/
│   │   ├── ui/                # Reusable primitives (Button, Card, Badge, etc.)
│   │   ├── auth/              # AuthGuard, LoginForm, SignupForm
│   │   ├── live/              # RaceTower, DriverRow, GapIndicator, TireIcon
│   │   ├── charts/            # DegradationChart, LapTimeChart, SectorChart
│   │   ├── predictions/       # ChampionshipBar, DriverOddsCard
│   │   └── chat/              # ChatWindow, MessageBubble, QuerySuggestions
│   ├── lib/
│   │   ├── firebase.ts        # Firebase client init
│   │   ├── auth.ts            # Auth helpers (useAuth hook, getToken)
│   │   ├── api.ts             # Typed fetch wrapper for FastAPI backend
│   │   └── websocket.ts       # WebSocket client with reconnect logic
│   └── types/
│       └── f1.ts              # Shared TypeScript types
├── .env.example
└── README.md
```

---

## 3. Environment Variables

Create `.env.example` with all of these. The actual `.env` is never committed.

```bash
# Backend
DATABASE_URL=postgresql://user:password@localhost:5432/f1nexus
REDIS_URL=redis://localhost:6379
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-xxxxx@your-project.iam.gserviceaccount.com
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=...
FASTF1_CACHE_DIR=./cache

# Frontend (prefix with NEXT_PUBLIC_ for browser exposure)
NEXT_PUBLIC_FIREBASE_API_KEY=...
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=...
NEXT_PUBLIC_FIREBASE_PROJECT_ID=...
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=...
NEXT_PUBLIC_FIREBASE_APP_ID=...
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000
```

---

## 4. Database Schema (PostgreSQL)

Implement all models in `app/models/sql.py` using SQLAlchemy 2.0 declarative syntax.

### 4.1 Core tables

```sql
-- Circuits
circuits (
  id          SERIAL PRIMARY KEY,
  name        VARCHAR(100) NOT NULL,
  country     VARCHAR(60),
  city        VARCHAR(60),
  track_length_km FLOAT,
  lap_record_s    FLOAT
)

-- Seasons
seasons (
  year  INTEGER PRIMARY KEY
)

-- Rounds (race weekends)
rounds (
  id          SERIAL PRIMARY KEY,
  season_year INTEGER REFERENCES seasons(year),
  round_number INTEGER NOT NULL,
  circuit_id  INTEGER REFERENCES circuits(id),
  race_date   DATE,
  name        VARCHAR(150),
  UNIQUE(season_year, round_number)
)

-- Drivers
drivers (
  code        CHAR(3) PRIMARY KEY,   -- e.g. "VER", "LEC"
  full_name   VARCHAR(100),
  nationality VARCHAR(60),
  dob         DATE
)

-- Constructors
constructors (
  id    SERIAL PRIMARY KEY,
  name  VARCHAR(100) NOT NULL UNIQUE
)

-- Driver-constructor-season mapping
driver_season (
  driver_code VARCHAR(3) REFERENCES drivers(code),
  season_year INTEGER REFERENCES seasons(year),
  constructor_id INTEGER REFERENCES constructors(id),
  car_number  INTEGER,
  PRIMARY KEY (driver_code, season_year)
)

-- Laps (core analytical table — will be large)
laps (
  id              BIGSERIAL PRIMARY KEY,
  round_id        INTEGER REFERENCES rounds(id),
  driver_code     CHAR(3) REFERENCES drivers(code),
  lap_number      INTEGER,
  lap_time_s      FLOAT,           -- NULL for laps without valid time
  sector1_s       FLOAT,
  sector2_s       FLOAT,
  sector3_s       FLOAT,
  compound        VARCHAR(10),     -- SOFT, MEDIUM, HARD, INTER, WET
  tyre_life       INTEGER,
  stint           INTEGER,
  is_valid        BOOLEAN DEFAULT TRUE,
  track_status    VARCHAR(5),      -- '1' = green flag
  position        INTEGER,
  created_at      TIMESTAMPTZ DEFAULT NOW()
)
CREATE INDEX ON laps (round_id, driver_code);
CREATE INDEX ON laps (driver_code, compound);

-- Qualifying results
qualifying (
  id          SERIAL PRIMARY KEY,
  round_id    INTEGER REFERENCES rounds(id),
  driver_code CHAR(3) REFERENCES drivers(code),
  q1_s        FLOAT,
  q2_s        FLOAT,
  q3_s        FLOAT,
  grid_position INTEGER
)

-- Race results
race_results (
  id              SERIAL PRIMARY KEY,
  round_id        INTEGER REFERENCES rounds(id),
  driver_code     CHAR(3) REFERENCES drivers(code),
  finish_position INTEGER,
  points          FLOAT,
  status          VARCHAR(50),     -- "Finished", "+1 Lap", "DNF", etc.
  fastest_lap     BOOLEAN DEFAULT FALSE
)

-- Championship standings (computed + cached after each round)
championship_standings (
  id              SERIAL PRIMARY KEY,
  season_year     INTEGER REFERENCES seasons(year),
  after_round     INTEGER,
  driver_code     CHAR(3) REFERENCES drivers(code),
  points          FLOAT,
  wins            INTEGER,
  position        INTEGER
)

-- ML model registry
ml_models (
  id          SERIAL PRIMARY KEY,
  model_type  VARCHAR(50),        -- 'degradation', 'strategy', 'overtake', etc.
  version     VARCHAR(20),
  trained_at  TIMESTAMPTZ,
  rmse        FLOAT,
  mae         FLOAT,
  artifact_path VARCHAR(200)      -- local path to joblib file
)
```

### 4.2 Firestore collections (user data only)

```
/users/{uid}
  display_name:         string
  email:                string
  followed_drivers:     string[]     // driver codes e.g. ["VER", "NOR"]
  followed_constructors: string[]    // constructor names
  notification_prefs:   map
    pit_alerts:         boolean
    safety_car:         boolean
    fastest_lap:        boolean
    race_start:         boolean
  season_pred_profile:  string       // "conservative" | "balanced" | "aggressive"
  fcm_token:            string | null
  telegram_chat_id:     string | null
  created_at:           timestamp

/live_sessions/{sessionKey}
  // Written by the backend live worker, read by all clients
  status:     string    // "active" | "inactive"
  session_type: string  // "Race" | "Qualifying" | "Practice"
  last_updated: timestamp
  drivers: map          // driver_code -> { position, gap_to_leader, lap, compound, tyre_life, ... }
```

---

## 5. Backend — Module Specifications

### 5.1 `app/config.py`

Use `pydantic-settings` to load all env vars. Expose a singleton `settings` object imported by other modules. All env vars defined in section 3 must map to fields on this settings object.

### 5.2 `app/firebase.py`

- Initialize Firebase Admin SDK once using `firebase_admin.initialize_app()` with credentials from `settings`.
- Expose `verify_token(token: str) -> dict` that calls `auth.verify_id_token(token)` and returns the decoded claims.
- Expose `get_firestore_client()` that returns the Firestore client.
- Expose `FastAPI` dependency `get_current_user(authorization: str = Header(...))` that extracts Bearer token, verifies it, and returns `{"uid": ..., "email": ...}`. Raise `HTTPException(401)` on failure.

### 5.3 `app/services/fastf1_loader.py`

```python
# Required functions (implement all):

def init_cache() -> None:
    """Call fastf1.Cache.enable_cache(settings.FASTF1_CACHE_DIR) — must be called at startup."""

def load_session(year: int, round_number: int, session_type: str = "R") -> fastf1.core.Session:
    """Load and return a FastF1 session. session_type: 'R', 'Q', 'FP1', 'FP2', 'FP3'."""

def get_clean_laps(session: fastf1.core.Session) -> pd.DataFrame:
    """
    Load laps with: session.load(laps=True, telemetry=False, weather=False, messages=False)
    
    Filter OUT:
    - Laps where LapTime is NaT
    - Laps where PitOutTime or PitInTime is not NaT (pit in/out laps)
    - Laps where TrackStatus != '1' (safety car, VSC, red flag)
    - Laps where LapTime > session median + 2 * std (outliers)
    
    Convert LapTime to seconds (float) in a new column 'lap_time_s'.
    Return the cleaned DataFrame.
    """

def seed_round_to_db(year: int, round_number: int, db: Session) -> None:
    """
    Load a race session, clean laps, and upsert all data into PostgreSQL.
    Creates/updates: rounds, drivers, laps, qualifying, race_results records.
    Use INSERT ... ON CONFLICT DO UPDATE for idempotency.
    """
```

### 5.4 `app/ml/degradation/`

**`features.py`**

```python
def build_features(laps_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Returns (X, y) where:
    
    Features (X columns):
      - tire_age:        TyreLife (int)
      - compound_enc:    LabelEncoded Compound (SOFT=0, MEDIUM=1, HARD=2, INTER=3, WET=4)
      - lap_number:      LapNumber (int)
      - fuel_proxy:      1.0 - (LapNumber / total_laps_in_race)
      - driver_enc:      LabelEncoded Driver code
      - stint:           Stint number (int)
      - track_temp_proxy: lap_number / 10  (crude proxy if weather not loaded)
    
    Target (y): lap_time_s (float, seconds)
    """
```

**`train.py`**

```python
def train_model(X: pd.DataFrame, y: pd.Series) -> dict:
    """
    - Train/test split: 80/20, random_state=42
    - Model: XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=5, random_state=42)
    - Return: {
        'model': trained model,
        'rmse': float,
        'mae': float,
        'r2': float,
        'feature_importance': pd.Series (sorted descending)
      }
    """

def save_model(model, path: str) -> None:
    """Serialize with joblib."""

def load_model(path: str):
    """Deserialize with joblib."""
```

**`predict.py`**

```python
def predict_stint(model, features_df: pd.DataFrame) -> np.ndarray:
    """Return array of predicted lap times."""

def build_degradation_curve(
    model,
    compound: str,
    max_tire_age: int,
    driver_enc: int,
    stint: int,
    lap_start: int,
    total_laps: int
) -> pd.DataFrame:
    """
    Generates a synthetic feature matrix for tire ages 1..max_tire_age.
    Returns DataFrame with columns ['tire_age', 'predicted_lap_time_s'].
    Used for visualisation — produces the smooth degradation curve.
    """
```

### 5.5 `app/ml/strategy/`

Frame pit stop strategy as a **binary classification problem per lap**:
- Label: `1` if driver pitted on this lap (i.e., next lap's TyreLife resets to 1), `0` otherwise.
- This is a **highly imbalanced** dataset (~1 pit per 20 laps). Use `scale_pos_weight` in XGBoost or `class_weight='balanced'` to handle imbalance.

**`features.py`**

```python
def build_strategy_features(laps_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Features:
      - tire_age, compound_enc, lap_number, fuel_proxy (same as degradation)
      - gap_ahead_s:     approx gap to car ahead (if available, else 0)
      - predicted_deg:   degradation model's predicted lap time for next 3 laps
                         (requires the degradation model to be loaded first)
      - laps_remaining:  total_laps - lap_number
      - current_position: Position (int)
    
    Target: pitted_this_lap (0 or 1)
    """
```

**`predict.py`**

```python
def recommend_pit_window(
    model,
    deg_model,
    current_lap: int,
    tire_age: int,
    compound: str,
    position: int,
    gap_ahead: float,
    total_laps: int
) -> dict:
    """
    Evaluates pit probability for the next 5 laps.
    Returns: {
      'recommended_lap': int,
      'probabilities': list[{'lap': int, 'pit_probability': float}],
      'reasoning': str   # e.g. "Tire cliff expected at lap 23, undercut window vs P3"
    }
    """
```

### 5.6 `app/ml/overtake/`

**Classification:** Will a following car complete an overtake on a given lap?

**Features:**
- `speed_delta_drs_entry`: speed difference at DRS detection point (requires telemetry — load with `telemetry=True` for this module only)
- `gap_s`: time gap between cars
- `drs_enabled`: boolean
- `tire_age_diff`: following car's tire age minus lead car's tire age
- `compound_delta`: compound hardness difference
- `circuit_overtake_index`: pre-computed per-circuit historical overtake frequency (hardcode as a dict)

**Target:** `overtake_completed` (0 or 1)

Note: telemetry loading is slow. Build a separate offline pipeline (`scripts/build_overtake_dataset.py`) that pre-processes telemetry and saves a clean CSV. The model trains from that CSV, not from live FastF1 calls.

### 5.7 `app/ml/driver_style/`

**`features.py`**

Extract per-driver, per-circuit style features from telemetry:

```python
def extract_style_features(session: fastf1.core.Session, driver_code: str) -> dict:
    """
    For each corner on the circuit:
      - min_speed_corner:      minimum speed through corner
      - braking_point_dist:    distance from corner apex where braking starts
      - throttle_application:  distance from apex where full throttle applied
      - max_lateral_g:         peak lateral G (proxy for cornering aggression)
    
    Aggregate to circuit-level stats:
      - avg_braking_point_dist, std_braking_point_dist
      - avg_throttle_dist, std_throttle_dist
      - avg_corner_speed, std_corner_speed
    
    Return as a flat dict of floats.
    """
```

**`cluster.py`**

```python
def cluster_drivers(style_matrix: pd.DataFrame, n_clusters: int = 5) -> dict:
    """
    - Standardize features with StandardScaler
    - KMeans clustering (k=5 default)
    - PCA to 2D for visualization
    - Return: {
        'labels': dict[driver_code -> cluster_id],
        'pca_coords': dict[driver_code -> [x, y]],
        'cluster_descriptions': dict[cluster_id -> str]  # human-readable label
      }
    """
```

**`fingerprint.py`**

```python
def identify_driver(model, style_features: dict) -> list[dict]:
    """
    Given a set of style features from an anonymous lap,
    return top 3 most likely drivers with confidence scores.
    Uses a trained RandomForestClassifier.
    Returns: [{'driver_code': str, 'confidence': float}, ...]
    """
```

### 5.8 `app/ml/season_prediction/`

**`circuit_model.py`**

```python
def build_circuit_performance_matrix(db: Session) -> pd.DataFrame:
    """
    For each (driver, circuit) pair across 2022-2024:
    - avg_qualifying_gap_to_pole: average qualifying gap to pole time (seconds)
    - avg_race_points: average points scored
    - finish_rate: fraction of races where driver classified as finisher
    - avg_position: average finishing position
    
    Returns matrix with MultiIndex (driver_code, circuit_id).
    """

def predict_race_outcome(
    circuit_id: int,
    drivers: list[str],
    current_form: dict,   # driver_code -> points last 3 races
    circuit_matrix: pd.DataFrame
) -> dict:
    """
    Returns dict of driver_code -> {
      'win_probability': float,
      'points_distribution': list[float]   # prob of scoring 0,1,2,4,6,8,10,12,15,18,25 pts
    }
    """
```

**`monte_carlo.py`**

```python
def simulate_championship(
    current_standings: dict,    # driver_code -> current_points
    remaining_rounds: list,     # list of circuit_ids
    circuit_matrix: pd.DataFrame,
    n_simulations: int = 10_000
) -> dict:
    """
    Run n_simulations of the remaining season.
    Each simulation samples a race result from predict_race_outcome for each remaining round.
    
    Returns: {
      driver_code: {
        'championship_probability': float,   # fraction of sims where this driver wins
        'podium_probability': float,
        'expected_final_points': float,
        'points_distribution': list[float]   # histogram of final points across sims
      }
    }
    """
```

### 5.9 `app/services/live_timing.py`

```python
class LiveTimingWorker:
    """
    Background worker that connects to FastF1 live timing during a race weekend.
    
    On startup: check if a session is currently active using fastf1.get_event_schedule()
    If active: connect to fastf1.livetiming.LiveTimingClient
    
    Every update received:
    1. Parse driver positions, gaps, tire data, sector times
    2. Run degradation model to predict each driver's remaining stint length
    3. Write structured update to Redis key 'live:current' with TTL 10s
    4. Push to all connected WebSocket clients via broadcast()
    5. Write snapshot to Firestore /live_sessions/{session_key}
    
    Trigger notifications:
    - Pit stop detected (TyreLife resets): notify users following that driver
    - Safety car deployed (TrackStatus changes): notify all users with safety_car pref
    - Fastest lap set: notify users following that driver
    
    Reconnection: exponential backoff up to 60s if connection drops.
    """
    
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def broadcast(self, data: dict) -> None: ...
    async def get_current_state(self) -> dict | None: ...
```

### 5.10 `app/ml/chat_rag/`

**`retriever.py`**

```python
SYSTEM_PROMPT = """
You are a SQL expert. Convert the user's natural language question about F1 data
into a PostgreSQL query against the f1nexus database schema below.

Schema summary:
- laps(round_id, driver_code, lap_number, lap_time_s, sector1_s, sector2_s, sector3_s, compound, tyre_life, stint, is_valid, position)
- rounds(id, season_year, round_number, circuit_id, race_date, name)
- circuits(id, name, country, city)
- drivers(code, full_name, nationality)
- race_results(round_id, driver_code, finish_position, points, status)
- championship_standings(season_year, after_round, driver_code, points, position)
- constructors(id, name)
- driver_season(driver_code, season_year, constructor_id, car_number)

Rules:
- Always filter is_valid = TRUE on laps table unless asked otherwise
- Return ONLY the SQL query, no explanation, no markdown fences
- Limit results to 100 rows unless the user asks for more
- Never use DELETE, UPDATE, INSERT, DROP, or any DDL
"""

def generate_sql(user_question: str) -> str:
    """Call Claude API with SYSTEM_PROMPT + user_question. Return raw SQL string."""

def execute_safe_query(sql: str, db: Session) -> list[dict]:
    """
    Validate that sql only contains SELECT (raise ValueError otherwise).
    Execute via SQLAlchemy text(), return results as list of dicts.
    Catch all exceptions and return error dict rather than raising.
    """
```

**`responder.py`**

```python
def answer_question(user_question: str, db: Session) -> dict:
    """
    Full RAG pipeline:
    1. Call generate_sql(user_question)
    2. Call execute_safe_query(sql, db)
    3. Format results as a compact JSON string (max 2000 chars)
    4. Call Claude API with:
       system: "You are an F1 data analyst. Answer the user's question using the 
                provided query results. Be concise. Format numbers clearly.
                If results are empty, say so directly."
       user: f"Question: {user_question}\n\nData: {results_json}"
    5. Return: {
         'answer': str,
         'sql': str,
         'row_count': int,
         'data': list[dict]   # raw results for table display
       }
    """
```

### 5.11 Router Specifications

**`routers/auth.py`**

- `POST /auth/sync` — Protected. Creates or updates user profile in Firestore from Firebase token claims. Returns user profile. Called on first login.

**`routers/races.py`**

- `GET /races/{year}` — Returns all rounds for a season with circuit info.
- `GET /races/{year}/{round}` — Returns round details, lap summary stats, tire strategy chart data, top 5 driver degradation curves.
- `GET /races/{year}/{round}/laps` — Returns paginated lap data. Query params: `driver_code`, `compound`, `page`, `page_size`.

**`routers/drivers.py`**

- `GET /drivers` — Returns all drivers with their current team.
- `GET /drivers/{code}` — Driver profile + career stats.
- `GET /drivers/{code}/style` — Driver style features + cluster assignment.
- `GET /drivers/{code}/compare/{other_code}` — Head-to-head sector comparison for a given round (query param `round_id`).

**`routers/predictions.py`**

- `GET /predictions/championship/{year}` — Full championship simulation results. Cached in Redis for 1 hour.
- `GET /predictions/race/{round_id}` — Race outcome predictions for an upcoming round.
- `GET /predictions/pit-window` — Query params: `round_id`, `driver_code`, `current_lap`. Returns pit recommendation.

**`routers/live.py`**

- `WebSocket /live/ws` — Client connects, receives JSON pushes every ~2s during live sessions. Message format:
  ```json
  {
    "type": "position_update",
    "timestamp": "ISO8601",
    "session_type": "Race",
    "lap": 32,
    "drivers": [
      {
        "code": "VER", "position": 1, "gap_to_leader": 0.0,
        "compound": "MEDIUM", "tyre_life": 18,
        "predicted_stint_end": 12,
        "last_lap_s": 90.234,
        "sector1_s": 29.1, "sector2_s": 32.4, "sector3_s": 28.7,
        "drs": true, "pitting": false
      }
    ]
  }
  ```
- `GET /live/status` — Returns `{ active: bool, session_type: str, current_lap: int }`.

**`routers/chat.py`**

- `POST /chat/query` — Protected. Body: `{ question: str }`. Returns RAG answer dict from section 5.10.
- `GET /chat/suggestions` — Returns 6 example questions tailored to the user's followed drivers.

**`routers/users.py`**

- `GET /users/me` — Protected. Returns user preferences from Firestore.
- `PUT /users/me/preferences` — Protected. Updates followed_drivers, followed_constructors, notification_prefs in Firestore.
- `POST /users/me/fcm-token` — Protected. Saves FCM token for push notifications.

---

## 6. Frontend — Page and Component Specifications

### 6.1 Auth System (`lib/firebase.ts`, `lib/auth.ts`)

- Initialize Firebase client SDK from `NEXT_PUBLIC_FIREBASE_*` env vars.
- Expose `useAuth()` hook that returns `{ user, loading, signIn, signOut }`.
- `signIn()` triggers Google OAuth popup using `signInWithPopup`.
- After successful sign-in, call `POST /auth/sync` with the Firebase JWT token.
- `AuthGuard` component wraps protected pages — redirects to `/login` if not authenticated.
- All API calls from `lib/api.ts` must attach `Authorization: Bearer {idToken}` header, refreshed automatically using `user.getIdToken()`.

### 6.2 Dashboard Page (`app/dashboard/page.tsx`)

Sections in order:
1. **Next race card** — countdown timer, circuit name, round number.
2. **Followed drivers** — card per followed driver showing: current championship position, points, last race result, and a sparkline of points over the season.
3. **Championship prediction strip** — horizontal probability bar for top 5 drivers in the championship, pulled from `/predictions/championship/{current_year}`.
4. **Recent activity feed** — last 3 race results with link to full analysis.

### 6.3 Live Race Page (`app/live/page.tsx`)

- On mount, connect to `WS /live/ws` using `lib/websocket.ts`.
- Display a race tower table updating in real time:
  | Pos | Driver | Gap | Lap | Tire | Age | Stint End (pred) | Last Lap |
- Color-code tire compounds: SOFT=red, MEDIUM=yellow, HARD=white, INTER=green, WET=blue.
- Show a "No live session" banner when `GET /live/status` returns `active: false`.
- WebSocket reconnection: attempt every 5s with max 10 retries, show connection status indicator.

### 6.4 Race Analysis Page (`app/races/[year]/[round]/page.tsx`)

Sections:
1. **Race header** — circuit, date, weather summary, winner.
2. **Lap time chart** — Plotly/Recharts line chart. X=lap number, Y=lap time (seconds). One line per driver. Filterable by driver.
3. **Tire strategy chart** — horizontal bars per driver showing stint lengths and compounds. Classic "strategy" visualization as seen on F1 broadcasts.
4. **Degradation model output** — predicted vs actual lap times per stint for top 3 drivers.
5. **Sector analysis** — heatmap: drivers vs sectors, colored by time delta to fastest.

### 6.5 Driver Profile Page (`app/drivers/[code]/page.tsx`)

Sections:
1. **Driver header** — name, team, nationality, car number.
2. **Career stats** — races, wins, podiums, poles.
3. **Season performance chart** — points per race this season, with trend line.
4. **Style profile** — radar chart of 6 style dimensions (braking aggression, cornering speed, throttle application, etc.) vs. average of all drivers.
5. **Head-to-head comparison** — select any other driver, shows sector delta heatmap for a chosen race.
6. **Follow button** — adds/removes from user's followed_drivers in Firestore via `PUT /users/me/preferences`.

### 6.6 Predictions Page (`app/predictions/page.tsx`)

1. **Championship probability bars** — horizontal stacked bar showing each driver's win probability. Updates after each race.
2. **Points trajectory** — line chart showing expected points accumulation for remaining season (mean + 90% confidence interval from Monte Carlo).
3. **Your drivers section** — personalised view for followed drivers, showing their probability curves and "best case / worst case" final standings.
4. **Risk profile selector** — toggle between Conservative / Balanced / Aggressive prediction profiles. Saves to Firestore. Aggressive assumes higher variance race outcomes.

### 6.7 Chat Page (`app/chat/page.tsx`)

- Full-page chat interface, messages from user on right, AI on left.
- Each AI message shows: answer text + collapsible "View SQL" section + collapsible "View raw data" table.
- Pre-populated suggestion chips pulled from `GET /chat/suggestions` (based on followed drivers).
- Example suggestions:
  - "Who had the best S2 time at Monaco in 2023?"
  - "Compare VER and NOR tyre degradation at Silverstone 2024"
  - "Which circuit had the most safety cars in 2023?"
  - "What was LEC's average qualifying gap to pole in 2024?"

### 6.8 Settings Page (`app/settings/page.tsx`)

- Driver multiselect — follow/unfollow with live Firestore sync.
- Constructor multiselect.
- Notification toggles: pit stops, safety car, fastest lap, race start.
- Telegram bot connection: display bot username + `/start` command, field to enter Telegram chat ID.
- Prediction risk profile selector.

---

## 7. Notifications

### 7.1 Firebase Cloud Messaging

- Frontend: call `messaging.getToken()` on settings page, POST token to `/users/me/fcm-token`.
- Backend `services/notifications.py`:
  ```python
  async def send_push(uid: str, title: str, body: str, data: dict = {}) -> None:
      """Fetch user's FCM token from Firestore, send via firebase_admin.messaging."""
  ```

### 7.2 Telegram Bot

- On settings page: user enters their Telegram chat ID (obtained by messaging the bot `/start`).
- Backend stores `telegram_chat_id` in Firestore user doc.
- `services/notifications.py`:
  ```python
  async def send_telegram(chat_id: str, message: str) -> None:
      """Send via python-telegram-bot async API."""
  ```

### 7.3 Notification Triggers (from `live_timing.py`)

| Event | Condition | Message |
|---|---|---|
| Pit stop | TyreLife resets to ≤ 2 for followed driver | "{driver} has pitted! Now on {compound} tyres." |
| Safety car | TrackStatus changes to '4' or '5' | "Safety car deployed on lap {lap}." |
| Fastest lap | New overall fastest lap set by followed driver | "{driver} sets fastest lap: {time}s" |
| Race start | Session starts (first lap data received) | "{race_name} is underway!" |

---

## 8. Data Seeding Script (`scripts/seed_data.py`)

```python
"""
Run once to populate PostgreSQL with 2022, 2023, 2024 historical data.

For each year, for each round:
1. Call seed_round_to_db(year, round_number, db)
2. Log progress: "Seeding {year} Round {round} — {circuit_name}"
3. Sleep 2 seconds between rounds to respect FastF1 rate limits
4. On failure, log error and continue to next round (don't abort entire seed)

After seeding: call train_all_models() to train and save all ML models.

Expected runtime: 45–90 minutes for full 2022–2024 dataset.
Estimated disk: ~2GB FastF1 cache + ~500MB PostgreSQL
"""
```

---

## 9. Model Training Script (`scripts/train_all.py`)

Train models in this order (degradation must be trained before strategy):

1. **Degradation model** — Train on all 2022–2024 races combined. Save to `models/degradation_v1.joblib`. Log RMSE.
2. **Strategy model** — Train on same dataset, uses degradation features. Save to `models/strategy_v1.joblib`.
3. **Overtake model** — Train from `data/overtake_dataset.csv` (pre-built by `build_overtake_dataset.py`). Save to `models/overtake_v1.joblib`.
4. **Driver fingerprint model** — Train per-circuit style features. Save to `models/fingerprint_v1.joblib`.
5. **Circuit performance matrix** — Not a trained model — compute and save as `data/circuit_performance.parquet`.

Log all metrics to `ml_models` table in PostgreSQL.

---

## 10. Deployment

### 10.1 Backend (Railway)

- `Procfile`: `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Add PostgreSQL and Redis plugins from Railway dashboard.
- Set all backend env vars in Railway environment settings.
- FastF1 cache: use a Railway volume mounted at `/app/cache`.
- The live timing worker starts as a background task in `app/main.py` lifespan handler.

### 10.2 Frontend (Vercel)

- Connect GitHub repo, set root directory to `frontend/`.
- Set all `NEXT_PUBLIC_*` env vars in Vercel project settings.
- `NEXT_PUBLIC_API_BASE_URL` = Railway deployment URL.

### 10.3 `app/main.py` startup sequence

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_cache()              # FastF1 cache
    init_db()                 # Create tables if not exist
    init_firebase()           # Firebase Admin SDK
    await live_worker.start() # Background live timing worker
    yield
    # Shutdown
    await live_worker.stop()

app = FastAPI(lifespan=lifespan)
# Include all routers
# Add CORS middleware allowing frontend origin
```

---

## 11. Build Order for the Coding Agent

Implement modules in this exact sequence to avoid dependency issues:

1. `config.py`, `database.py`, `models/sql.py` — foundation, no dependencies
2. `firebase.py` — auth layer
3. `services/fastf1_loader.py` + `scripts/seed_data.py` — get data into DB
4. `ml/degradation/` — first and most important ML module
5. `ml/strategy/` — depends on degradation model
6. `ml/driver_style/` + `ml/overtake/` — independent, run in parallel
7. `ml/season_prediction/` — depends on DB being seeded
8. All routers (`races`, `drivers`, `predictions`, `users`, `auth`) — depend on ML + DB
9. `services/live_timing.py` + `routers/live.py` — WebSocket layer
10. `ml/chat_rag/` + `routers/chat.py` — AI layer, depends on DB being seeded
11. `services/notifications.py` — final backend piece
12. Frontend: `lib/` utilities → auth pages → dashboard → races → drivers → predictions → live → chat → settings

---

## 12. Key Implementation Rules

These are non-negotiable constraints the agent must follow:

1. **FastF1 cache always on.** Call `fastf1.Cache.enable_cache()` before any session load. Without this, every API call re-downloads data.

2. **LapTime is a timedelta.** Always convert with `.dt.total_seconds()` before any numerical operation.

3. **No sync I/O in async endpoints.** Wrap all SQLAlchemy calls and FastF1 loads in `asyncio.to_thread()` or use a thread pool executor. FastAPI endpoints are async; blocking calls will freeze the server.

4. **Firebase token on every protected endpoint.** Every router that returns user-specific data must use the `get_current_user` dependency. Do not build unauthenticated shortcuts.

5. **Firestore for user data, PostgreSQL for race data.** Never store lap data in Firestore. Never store user preferences in PostgreSQL. The split is intentional.

6. **SQL injection prevention.** In `chat_rag/retriever.py`, always use `sqlalchemy.text()` with no string formatting of user input. The LLM generates the SQL; the user never directly provides SQL.

7. **Race data is read-only from the frontend.** The frontend never writes to PostgreSQL. All writes go through FastAPI endpoints.

8. **Model files are not committed to git.** Add `models/*.joblib` and `data/*.parquet` to `.gitignore`. They are generated by `train_all.py`.

9. **All API responses use Pydantic schemas.** No raw dict returns from endpoints. Define a response schema for every endpoint in `models/schemas.py`.

10. **Live timing is optional.** The entire app must work perfectly during non-race weekends when no live data is available. Every component that consumes live data must have a graceful "no live session" fallback state.

---

## 13. What Success Looks Like

The build is complete when all of the following work end-to-end:

- [ ] User signs in with Google, profile is created in Firestore
- [ ] User follows VER and NOR, saves preferences
- [ ] Dashboard shows followed driver cards and championship prediction strip
- [ ] `/races/2024/5` loads Chinese GP analysis with lap time chart and tire strategy chart
- [ ] Degradation model predictions for 2024 Chinese GP have RMSE < 3.0 seconds
- [ ] Driver style page for VER shows radar chart and cluster assignment
- [ ] Championship prediction page shows Monte Carlo results with probability bars
- [ ] Chat query "Who had the fastest lap at Monaco 2023?" returns correct SQL + answer
- [ ] Live page shows "No live session" gracefully during off-weekend
- [ ] On a race weekend, WebSocket delivers position updates within 5 seconds of FastF1 receiving them
- [ ] Notification sent to followed-driver users when a pit stop is detected

---

*End of specification. Build everything listed. Ask no clarifying questions — make reasonable decisions and document them in code comments.*
