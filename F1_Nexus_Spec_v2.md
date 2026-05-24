# F1 Nexus — Full Project Specification (v2 — fully free stack)

> **For Claude Opus (coding agent):** This document is the single source of truth for the F1 Nexus project. Build every module described here completely — no stubs, no TODOs, no placeholder implementations. When in doubt about a design decision, choose the simpler approach and document your reasoning in a comment.

> **Cost constraint:** Every service used must have a permanently free tier. No credit cards, no trials, no services that expire. The upgrade path to paid tiers is documented in section 14 — design code so those upgrades require only environment variable changes, not architectural rewrites.

---

## 0. Project Summary

F1 Nexus is a full-stack Formula 1 intelligence platform. It ingests historical and live race telemetry via the FastF1 API, runs multiple ML models for prediction and analysis, and exposes everything through a Next.js web app with Firebase-based user accounts.

Users can follow specific drivers and constructors, get personalised race predictions, watch a live race tower during race weekends, and query the entire F1 dataset in natural language via an AI chat interface powered by a free LLM provider.

**What this is not:** a scraper of the official F1 website, a real-time betting tool, or a mobile app. It is a web platform and portfolio project.

---

## 1. Tech Stack

| Layer | Technology | Free tier | Notes |
|---|---|---|---|
| Frontend | Next.js 14 (App Router) | Vercel free | React server + client components |
| Styling | Tailwind CSS | Free | Dark theme by default, F1-inspired |
| Auth | Firebase Authentication | Free (10k users/mo) | Google OAuth + email/password |
| User data | Firestore | Free (1GB, 50k reads/day) | Preferences, watchlists, notification settings |
| Backend | FastAPI (Python 3.11+) | Render free tier | REST + WebSocket endpoints |
| ML | scikit-learn, XGBoost, statsmodels | Free | Per-module requirements listed below |
| Race data | FastF1 ≥ 3.3.0 | Free, open source | Historical + live timing |
| Database | PostgreSQL via Neon.tech | Free (0.5GB, no expiry) | All race/lap/telemetry data |
| ORM | SQLAlchemy 2.0 + Alembic | Free | Migrations required |
| Cache | Python in-memory dict | Free | Replaces Redis — fine for single instance |
| AI chat | Groq API (default) | Free (14,400 req/day) | Provider-agnostic wrapper, swappable |
| Notifications | Web Push API + python-telegram-bot | Free | Browser push + Telegram |
| Deployment | Render (backend) + Vercel (frontend) | Both free | See cold start mitigation in section 10 |
| Package mgmt | Poetry (backend), pnpm (frontend) | Free | |

---

## 2. Repository Structure

Generate this structure exactly. Every file listed must be created with a working implementation.

```
f1-nexus/
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/               # migration files go here
│   ├── app/
│   │   ├── main.py                 # FastAPI app entry point
│   │   ├── config.py               # env var loading via pydantic-settings
│   │   ├── database.py             # SQLAlchemy engine + session
│   │   ├── firebase.py             # Firebase Admin SDK init + token verification
│   │   ├── models/
│   │   │   ├── sql.py              # SQLAlchemy ORM models
│   │   │   └── schemas.py          # Pydantic request/response schemas
│   │   ├── routers/
│   │   │   ├── auth.py             # /auth/* endpoints
│   │   │   ├── races.py            # /races/* endpoints
│   │   │   ├── drivers.py          # /drivers/* endpoints
│   │   │   ├── predictions.py      # /predictions/* endpoints
│   │   │   ├── live.py             # /live/* WebSocket endpoint
│   │   │   ├── chat.py             # /chat/* AI chat endpoint
│   │   │   └── users.py            # /users/* user preferences endpoints
│   │   ├── services/
│   │   │   ├── fastf1_loader.py    # FastF1 data fetching + caching
│   │   │   ├── live_timing.py      # FastF1 live timing worker (in-memory state)
│   │   │   └── notifications.py    # Web Push + Telegram notification sender
│   │   └── ml/
│   │       ├── degradation/
│   │       │   ├── features.py
│   │       │   ├── train.py
│   │       │   └── predict.py
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
│   │       │   ├── monte_carlo.py
│   │       │   └── circuit_model.py
│   │       └── chat_rag/
│   │           ├── llm_client.py   # Provider-agnostic LLM wrapper (Groq/Gemini/Anthropic)
│   │           ├── retriever.py    # SQL query generator from natural language
│   │           └── responder.py    # LLM call with retrieved context
│   └── scripts/
│       ├── seed_data.py            # Initial historical data load (2022–2024)
│       └── train_all.py            # Train + save all ML models
├── frontend/
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── next.config.ts
│   ├── public/
│   │   └── sw.js                   # Service worker for Web Push notifications
│   ├── app/
│   │   ├── layout.tsx              # Root layout with Firebase provider
│   │   ├── page.tsx                # Landing / redirect to dashboard
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── signup/page.tsx
│   │   ├── dashboard/
│   │   │   └── page.tsx
│   │   ├── live/
│   │   │   └── page.tsx            # Live race tower (WebSocket)
│   │   ├── races/
│   │   │   ├── page.tsx
│   │   │   └── [year]/[round]/page.tsx
│   │   ├── drivers/
│   │   │   ├── page.tsx
│   │   │   └── [code]/page.tsx
│   │   ├── constructors/
│   │   │   └── page.tsx
│   │   ├── predictions/
│   │   │   └── page.tsx
│   │   ├── chat/
│   │   │   └── page.tsx
│   │   └── settings/
│   │       └── page.tsx
│   ├── components/
│   │   ├── ui/                     # Button, Card, Badge, Spinner, etc.
│   │   ├── auth/                   # AuthGuard, LoginForm, SignupForm
│   │   ├── live/                   # RaceTower, DriverRow, GapIndicator, TireIcon
│   │   ├── charts/                 # DegradationChart, LapTimeChart, SectorChart
│   │   ├── predictions/            # ChampionshipBar, DriverOddsCard
│   │   └── chat/                   # ChatWindow, MessageBubble, QuerySuggestions
│   ├── lib/
│   │   ├── firebase.ts             # Firebase client init
│   │   ├── auth.ts                 # useAuth hook, getToken helper
│   │   ├── api.ts                  # Typed fetch wrapper for FastAPI backend
│   │   ├── websocket.ts            # WebSocket client with reconnect logic
│   │   └── webpush.ts              # Web Push subscription + service worker registration
│   └── types/
│       └── f1.ts                   # Shared TypeScript types
├── .github/
│   └── workflows/
│       └── keep-alive.yml          # Cron job to prevent Render cold starts
├── .env.example
└── README.md
```

---

## 3. Environment Variables

Create `.env.example` with all of these. The actual `.env` is never committed.

```bash
# ── Backend ────────────────────────────────────────────────────────────────

# Neon.tech PostgreSQL connection string (get from Neon dashboard)
DATABASE_URL=postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/f1nexus?sslmode=require

# Firebase Admin SDK (download service account JSON from Firebase console)
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-xxxxx@your-project.iam.gserviceaccount.com

# LLM provider — set ONE of these. Default provider is controlled by LLM_PROVIDER.
LLM_PROVIDER=groq                        # options: groq | gemini | anthropic
GROQ_API_KEY=gsk_...                     # free at console.groq.com
GEMINI_API_KEY=AIza...                   # free at aistudio.google.com (fallback)
ANTHROPIC_API_KEY=sk-ant-...             # paid — leave blank unless upgrading

# LLM model names — defaults shown, override if needed
GROQ_MODEL=llama-3.1-70b-versatile
GEMINI_MODEL=gemini-1.5-flash
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# Telegram bot (free — create via @BotFather on Telegram)
TELEGRAM_BOT_TOKEN=...

# Web Push VAPID keys (generate once with: python -m py_vapid --applicationServerKey)
VAPID_PRIVATE_KEY=...
VAPID_PUBLIC_KEY=...
VAPID_CLAIMS_EMAIL=your@email.com

# FastF1 cache directory (local path)
FASTF1_CACHE_DIR=./cache

# ── Frontend (NEXT_PUBLIC_ prefix exposes to browser) ──────────────────────
NEXT_PUBLIC_FIREBASE_API_KEY=...
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=...
NEXT_PUBLIC_FIREBASE_PROJECT_ID=...
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=...
NEXT_PUBLIC_FIREBASE_APP_ID=...
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000
NEXT_PUBLIC_VAPID_PUBLIC_KEY=...         # same as VAPID_PUBLIC_KEY above
```

---

## 4. Database Schema (PostgreSQL / Neon.tech)

Implement all models in `app/models/sql.py` using SQLAlchemy 2.0 declarative syntax.

### 4.1 Core tables

```sql
-- Circuits
circuits (
  id              SERIAL PRIMARY KEY,
  name            VARCHAR(100) NOT NULL,
  country         VARCHAR(60),
  city            VARCHAR(60),
  track_length_km FLOAT,
  lap_record_s    FLOAT
)

-- Seasons
seasons (
  year INTEGER PRIMARY KEY
)

-- Rounds (race weekends)
rounds (
  id            SERIAL PRIMARY KEY,
  season_year   INTEGER REFERENCES seasons(year),
  round_number  INTEGER NOT NULL,
  circuit_id    INTEGER REFERENCES circuits(id),
  race_date     DATE,
  name          VARCHAR(150),
  UNIQUE(season_year, round_number)
)

-- Drivers
drivers (
  code        CHAR(3) PRIMARY KEY,
  full_name   VARCHAR(100),
  nationality VARCHAR(60),
  dob         DATE
)

-- Constructors
constructors (
  id   SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL UNIQUE
)

-- Driver-constructor-season mapping
driver_season (
  driver_code    VARCHAR(3) REFERENCES drivers(code),
  season_year    INTEGER REFERENCES seasons(year),
  constructor_id INTEGER REFERENCES constructors(id),
  car_number     INTEGER,
  PRIMARY KEY (driver_code, season_year)
)

-- Laps (core analytical table)
laps (
  id           BIGSERIAL PRIMARY KEY,
  round_id     INTEGER REFERENCES rounds(id),
  driver_code  CHAR(3) REFERENCES drivers(code),
  lap_number   INTEGER,
  lap_time_s   FLOAT,
  sector1_s    FLOAT,
  sector2_s    FLOAT,
  sector3_s    FLOAT,
  compound     VARCHAR(10),
  tyre_life    INTEGER,
  stint        INTEGER,
  is_valid     BOOLEAN DEFAULT TRUE,
  track_status VARCHAR(5),
  position     INTEGER,
  created_at   TIMESTAMPTZ DEFAULT NOW()
)
CREATE INDEX ON laps (round_id, driver_code);
CREATE INDEX ON laps (driver_code, compound);

-- Qualifying results
qualifying (
  id             SERIAL PRIMARY KEY,
  round_id       INTEGER REFERENCES rounds(id),
  driver_code    CHAR(3) REFERENCES drivers(code),
  q1_s           FLOAT,
  q2_s           FLOAT,
  q3_s           FLOAT,
  grid_position  INTEGER
)

-- Race results
race_results (
  id              SERIAL PRIMARY KEY,
  round_id        INTEGER REFERENCES rounds(id),
  driver_code     CHAR(3) REFERENCES drivers(code),
  finish_position INTEGER,
  points          FLOAT,
  status          VARCHAR(50),
  fastest_lap     BOOLEAN DEFAULT FALSE
)

-- Championship standings (computed + cached after each round)
championship_standings (
  id          SERIAL PRIMARY KEY,
  season_year INTEGER REFERENCES seasons(year),
  after_round INTEGER,
  driver_code CHAR(3) REFERENCES drivers(code),
  points      FLOAT,
  wins        INTEGER,
  position    INTEGER
)

-- ML model registry
ml_models (
  id            SERIAL PRIMARY KEY,
  model_type    VARCHAR(50),
  version       VARCHAR(20),
  trained_at    TIMESTAMPTZ,
  rmse          FLOAT,
  mae           FLOAT,
  artifact_path VARCHAR(200)
)
```

### 4.2 Firestore collections (user data only)

```
/users/{uid}
  display_name:          string
  email:                 string
  followed_drivers:      string[]      // e.g. ["VER", "NOR"]
  followed_constructors: string[]
  notification_prefs:    map
    pit_alerts:          boolean
    safety_car:          boolean
    fastest_lap:         boolean
    race_start:          boolean
  season_pred_profile:   string        // "conservative" | "balanced" | "aggressive"
  web_push_subscription: map | null    // Web Push subscription object
  telegram_chat_id:      string | null
  created_at:            timestamp

/live_sessions/{sessionKey}
  // Written by the backend live worker, read by all clients
  status:       string     // "active" | "inactive"
  session_type: string     // "Race" | "Qualifying" | "Practice"
  last_updated: timestamp
  drivers:      map        // driver_code -> position data
```

---

## 5. Backend — Module Specifications

### 5.1 `app/config.py`

Use `pydantic-settings` to load all env vars. Expose a singleton `settings` object. All env vars from section 3 must map to typed fields. Include:

```python
class Settings(BaseSettings):
    DATABASE_URL: str
    FIREBASE_PROJECT_ID: str
    FIREBASE_PRIVATE_KEY: str
    FIREBASE_CLIENT_EMAIL: str
    LLM_PROVIDER: str = "groq"          # default provider
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-70b-versatile"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    TELEGRAM_BOT_TOKEN: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_PUBLIC_KEY: str = ""
    VAPID_CLAIMS_EMAIL: str = ""
    FASTF1_CACHE_DIR: str = "./cache"
```

### 5.2 `app/firebase.py`

- Initialize Firebase Admin SDK once using `firebase_admin.initialize_app()` with credentials from `settings`.
- Expose `verify_token(token: str) -> dict` that calls `auth.verify_id_token(token)` and returns decoded claims.
- Expose `get_firestore_client()` returning the Firestore client.
- Expose FastAPI dependency `get_current_user(authorization: str = Header(...))` that extracts Bearer token, verifies it, and returns `{"uid": ..., "email": ...}`. Raise `HTTPException(401)` on failure.

### 5.3 `app/services/fastf1_loader.py`

```python
def init_cache() -> None:
    """Call fastf1.Cache.enable_cache(settings.FASTF1_CACHE_DIR). Must be called at startup."""

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

    Convert LapTime to seconds (float) in new column 'lap_time_s'.
    Return cleaned DataFrame.
    """

def seed_round_to_db(year: int, round_number: int, db: Session) -> None:
    """
    Load a race session, clean laps, and upsert all data into PostgreSQL.
    Creates/updates: rounds, drivers, laps, qualifying, race_results records.
    Use INSERT ... ON CONFLICT DO UPDATE for idempotency.
    """
```

### 5.4 `app/ml/chat_rag/llm_client.py` — Provider-agnostic LLM wrapper

This is the single file that isolates all LLM provider differences. All other modules import only from here — never directly from groq, anthropic, or google.generativeai.

```python
"""
Provider-agnostic LLM client. Controlled by settings.LLM_PROVIDER.

To swap provider: change LLM_PROVIDER env var. No code changes needed.
  groq      → uses GROQ_API_KEY + GROQ_MODEL
  gemini    → uses GEMINI_API_KEY + GEMINI_MODEL
  anthropic → uses ANTHROPIC_API_KEY + ANTHROPIC_MODEL (paid)
"""

def chat_completion(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 1000,
    temperature: float = 0.1
) -> str:
    """
    Send a chat completion request to the configured LLM provider.
    Returns the response text as a plain string.

    Implementation:
    - If LLM_PROVIDER == "groq":
        from groq import Groq
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": user_message}],
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content

    - If LLM_PROVIDER == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL,
                    system_instruction=system_prompt)
        response = model.generate_content(user_message)
        return response.text

    - If LLM_PROVIDER == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        return response.content[0].text

    Raise ValueError if LLM_PROVIDER is not one of the above three.
    Raise RuntimeError if the corresponding API key is empty.
    """
```

### 5.5 `app/ml/degradation/`

**`features.py`**

```python
def build_features(laps_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Features (X columns):
      - tire_age:        TyreLife (int)
      - compound_enc:    LabelEncoded Compound (SOFT=0, MEDIUM=1, HARD=2, INTER=3, WET=4)
      - lap_number:      LapNumber (int)
      - fuel_proxy:      1.0 - (LapNumber / total_laps_in_race)
      - driver_enc:      LabelEncoded Driver code
      - stint:           Stint number (int)
      - track_temp_proxy: lap_number / 10

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
    """
```

### 5.6 `app/ml/strategy/`

Frame pit stop strategy as binary classification per lap:
- Label: `1` if driver pitted on this lap (next lap's TyreLife resets to 1), `0` otherwise.
- Highly imbalanced (~1 pit per 20 laps). Use `scale_pos_weight` in XGBoost.

**`features.py`**

```python
def build_strategy_features(laps_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Features:
      - tire_age, compound_enc, lap_number, fuel_proxy (same as degradation)
      - gap_ahead_s:       approx gap to car ahead (0 if unavailable)
      - predicted_deg:     degradation model's predicted lap time for next 3 laps
      - laps_remaining:    total_laps - lap_number
      - current_position:  Position (int)

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
      'reasoning': str
    }
    """
```

### 5.7 `app/ml/overtake/`

**Classification:** Will a following car complete an overtake on a given lap?

**Features:**
- `speed_delta_drs_entry`: speed difference at DRS detection point (requires telemetry)
- `gap_s`: time gap between cars
- `drs_enabled`: boolean
- `tire_age_diff`: following car tire age minus lead car tire age
- `compound_delta`: compound hardness difference
- `circuit_overtake_index`: pre-computed per-circuit historical overtake frequency (hardcode as a dict)

**Target:** `overtake_completed` (0 or 1)

Build a separate offline pipeline (`scripts/build_overtake_dataset.py`) that pre-processes telemetry and saves a clean CSV. The model trains from that CSV — never from live FastF1 calls during serving.

### 5.8 `app/ml/driver_style/`

**`features.py`**

```python
def extract_style_features(session: fastf1.core.Session, driver_code: str) -> dict:
    """
    For each corner on the circuit, extract:
      - min_speed_corner
      - braking_point_dist
      - throttle_application distance from apex
      - max_lateral_g

    Aggregate to circuit-level stats:
      - avg/std of each above

    Return as flat dict of floats.
    """
```

**`cluster.py`**

```python
def cluster_drivers(style_matrix: pd.DataFrame, n_clusters: int = 5) -> dict:
    """
    - Standardize with StandardScaler
    - KMeans (k=5)
    - PCA to 2D for visualisation
    - Return: {
        'labels': dict[driver_code -> cluster_id],
        'pca_coords': dict[driver_code -> [x, y]],
        'cluster_descriptions': dict[cluster_id -> str]
      }
    """
```

**`fingerprint.py`**

```python
def identify_driver(model, style_features: dict) -> list[dict]:
    """
    Given style features from an anonymous lap, return top 3 most likely drivers.
    Uses a trained RandomForestClassifier.
    Returns: [{'driver_code': str, 'confidence': float}, ...]
    """
```

### 5.9 `app/ml/season_prediction/`

**`circuit_model.py`**

```python
def build_circuit_performance_matrix(db: Session) -> pd.DataFrame:
    """
    For each (driver, circuit) pair across 2022-2024:
      - avg_qualifying_gap_to_pole
      - avg_race_points
      - finish_rate
      - avg_position

    Returns DataFrame with MultiIndex (driver_code, circuit_id).
    """

def predict_race_outcome(
    circuit_id: int,
    drivers: list[str],
    current_form: dict,
    circuit_matrix: pd.DataFrame
) -> dict:
    """
    Returns dict of driver_code -> {
      'win_probability': float,
      'points_distribution': list[float]
    }
    """
```

**`monte_carlo.py`**

```python
def simulate_championship(
    current_standings: dict,
    remaining_rounds: list,
    circuit_matrix: pd.DataFrame,
    n_simulations: int = 10_000
) -> dict:
    """
    Run n_simulations of the remaining season.
    Returns: {
      driver_code: {
        'championship_probability': float,
        'podium_probability': float,
        'expected_final_points': float,
        'points_distribution': list[float]
      }
    }
    """
```

### 5.10 `app/services/live_timing.py`

**Important:** This module uses an in-memory Python dict for state instead of Redis. This is intentional and correct for a single-instance deployment. See section 14 for the Redis upgrade path.

```python
class LiveTimingWorker:
    """
    Background worker that connects to FastF1 live timing during a race weekend.

    State is stored in self._state (plain dict) — no Redis dependency.
    self._state = {
        'active': bool,
        'session_type': str,
        'current_lap': int,
        'last_updated': float,  # unix timestamp
        'drivers': {}           # driver_code -> position dict
    }

    On startup: check if a session is currently active.
    If active: connect to fastf1.livetiming.LiveTimingClient.

    Every update received:
    1. Parse positions, gaps, tire data, sector times
    2. Run degradation model to predict each driver's remaining stint length
    3. Update self._state in place (thread-safe with asyncio.Lock)
    4. Push to all connected WebSocket clients via broadcast()
    5. Write snapshot to Firestore /live_sessions/{session_key}

    Trigger notifications:
    - Pit stop detected (TyreLife resets): notify users following that driver
    - Safety car deployed (TrackStatus changes): notify all users with safety_car pref
    - Fastest lap set: notify users following that driver
    - Race start: notify all users with race_start pref

    Reconnection: exponential backoff up to 60s on connection drop.
    """

    def __init__(self):
        self._state: dict = {'active': False, 'drivers': {}}
        self._lock = asyncio.Lock()
        self._clients: set = set()   # connected WebSocket clients

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def broadcast(self, data: dict) -> None: ...

    async def get_current_state(self) -> dict:
        """Return a copy of self._state. Never return the live dict directly."""
        async with self._lock:
            return dict(self._state)
```

WebSocket message format:
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

### 5.11 `app/ml/chat_rag/retriever.py`

```python
SQL_SYSTEM_PROMPT = """
You are a SQL expert. Convert the user's natural language question about F1 data
into a PostgreSQL query against the f1nexus database schema below.

Schema summary:
- laps(round_id, driver_code, lap_number, lap_time_s, sector1_s, sector2_s, sector3_s,
       compound, tyre_life, stint, is_valid, position)
- rounds(id, season_year, round_number, circuit_id, race_date, name)
- circuits(id, name, country, city)
- drivers(code, full_name, nationality)
- race_results(round_id, driver_code, finish_position, points, status)
- championship_standings(season_year, after_round, driver_code, points, position)
- constructors(id, name)
- driver_season(driver_code, season_year, constructor_id, car_number)

Rules:
- Always filter is_valid = TRUE on laps unless asked otherwise
- Return ONLY the SQL query — no explanation, no markdown fences
- Limit results to 100 rows unless the user asks for more
- Never use DELETE, UPDATE, INSERT, DROP, or any DDL
"""

def generate_sql(user_question: str) -> str:
    """
    Call llm_client.chat_completion() with SQL_SYSTEM_PROMPT.
    Returns raw SQL string.
    """

def execute_safe_query(sql: str, db: Session) -> list[dict]:
    """
    Validate sql starts with SELECT (raise ValueError otherwise).
    Execute via sqlalchemy.text(). Return results as list of dicts.
    Catch all exceptions — return {'error': str(e)} rather than raising.
    Never format user input into the SQL string.
    """
```

### 5.12 `app/ml/chat_rag/responder.py`

```python
ANSWER_SYSTEM_PROMPT = """
You are an F1 data analyst. Answer the user's question using the provided
query results. Be concise. Format numbers clearly (e.g. '1:23.456' for lap times).
If results are empty, say so directly. Never invent data not in the results.
"""

def answer_question(user_question: str, db: Session) -> dict:
    """
    Full RAG pipeline:
    1. Call generate_sql(user_question)
    2. Call execute_safe_query(sql, db)
    3. Format results as compact JSON string (cap at 2000 chars)
    4. Call llm_client.chat_completion() with ANSWER_SYSTEM_PROMPT and
       f"Question: {user_question}\n\nData: {results_json}"
    5. Return: {
         'answer': str,
         'sql': str,
         'row_count': int,
         'data': list[dict]
       }
    """
```

### 5.13 Router Specifications

**`routers/auth.py`**
- `POST /auth/sync` — Protected. Creates/updates Firestore user profile from token claims.

**`routers/races.py`**
- `GET /races/{year}` — All rounds for a season with circuit info.
- `GET /races/{year}/{round}` — Round details, lap summary, tire strategy data, top 5 degradation curves.
- `GET /races/{year}/{round}/laps` — Paginated lap data. Query params: `driver_code`, `compound`, `page`, `page_size`.

**`routers/drivers.py`**
- `GET /drivers` — All drivers with current team.
- `GET /drivers/{code}` — Driver profile + career stats.
- `GET /drivers/{code}/style` — Style features + cluster assignment.
- `GET /drivers/{code}/compare/{other_code}` — Sector delta comparison (query param: `round_id`).

**`routers/predictions.py`**
- `GET /predictions/championship/{year}` — Full Monte Carlo results. Cache in `_prediction_cache` dict on the router module for 1 hour (no Redis needed).
- `GET /predictions/race/{round_id}` — Race outcome predictions for an upcoming round.
- `GET /predictions/pit-window` — Query params: `round_id`, `driver_code`, `current_lap`. Returns pit recommendation.

**`routers/live.py`**
- `WebSocket /live/ws` — Connect, receive JSON pushes every ~2s during live sessions.
- `GET /live/status` — Returns `{ active: bool, session_type: str, current_lap: int }`.

**`routers/chat.py`**
- `POST /chat/query` — Protected. Body: `{ question: str }`. Returns RAG answer dict.
- `GET /chat/suggestions` — Returns 6 example questions based on user's followed drivers.

**`routers/users.py`**
- `GET /users/me` — Protected. Returns Firestore user preferences.
- `PUT /users/me/preferences` — Protected. Updates followed_drivers, followed_constructors, notification_prefs in Firestore.
- `POST /users/me/push-subscription` — Protected. Saves Web Push subscription object to Firestore.

---

## 6. Frontend — Page and Component Specifications

### 6.1 Auth System (`lib/firebase.ts`, `lib/auth.ts`)

- Initialize Firebase client SDK from `NEXT_PUBLIC_FIREBASE_*` env vars.
- Expose `useAuth()` hook returning `{ user, loading, signIn, signOut }`.
- `signIn()` triggers Google OAuth popup via `signInWithPopup`.
- After sign-in, call `POST /auth/sync` with Firebase JWT.
- `AuthGuard` wraps protected pages — redirects to `/login` if unauthenticated.
- All API calls in `lib/api.ts` attach `Authorization: Bearer {idToken}`, auto-refreshed via `user.getIdToken()`.

### 6.2 Dashboard Page (`app/dashboard/page.tsx`)

Sections in order:
1. **Next race card** — countdown timer, circuit name, round number.
2. **Followed drivers** — card per driver: championship position, points, last race result, sparkline of points over season.
3. **Championship prediction strip** — horizontal probability bar for top 5 drivers, from `/predictions/championship/{year}`.
4. **Recent activity feed** — last 3 race results with link to full analysis.

### 6.3 Live Race Page (`app/live/page.tsx`)

- On mount, connect to `WS /live/ws` via `lib/websocket.ts`.
- Race tower table updating in real time:

  | Pos | Driver | Gap | Lap | Tire | Age | Stint End (pred) | Last Lap |

- Tire compound colours: SOFT=red, MEDIUM=yellow, HARD=white, INTER=green, WET=blue.
- Show "No live session" banner when `/live/status` returns `active: false`.
- WebSocket reconnection: attempt every 5s, max 10 retries, show connection status indicator.

### 6.4 Race Analysis Page (`app/races/[year]/[round]/page.tsx`)

1. Race header — circuit, date, weather summary, winner.
2. Lap time chart — Recharts line chart. X=lap number, Y=lap time (seconds). Filterable by driver.
3. Tire strategy chart — horizontal bars per driver showing stint lengths and compounds.
4. Degradation model output — predicted vs actual lap times per stint for top 3 drivers.
5. Sector analysis — heatmap: drivers vs sectors, colored by delta to fastest.

### 6.5 Driver Profile Page (`app/drivers/[code]/page.tsx`)

1. Driver header — name, team, nationality, car number.
2. Career stats — races, wins, podiums, poles.
3. Season performance chart — points per race with trend line.
4. Style profile — radar chart of 6 style dimensions vs. all-driver average.
5. Head-to-head comparison — select any other driver, show sector delta heatmap for a chosen race.
6. Follow button — adds/removes from Firestore followed_drivers via `PUT /users/me/preferences`.

### 6.6 Predictions Page (`app/predictions/page.tsx`)

1. Championship probability bars — horizontal stacked bar per driver.
2. Points trajectory — line chart: expected points with mean + 90% confidence interval.
3. Your drivers section — personalised view for followed drivers with probability curves.
4. Risk profile selector — Conservative / Balanced / Aggressive. Saves to Firestore.

### 6.7 Chat Page (`app/chat/page.tsx`)

- Full-page chat interface. User messages right, AI left.
- Each AI message: answer text + collapsible "View SQL" + collapsible "View data" table.
- Pre-populated suggestion chips from `GET /chat/suggestions`.
- Example suggestions: "Who had the best S2 time at Monaco 2023?", "Compare VER and NOR tyre degradation at Silverstone 2024", "Which circuit had the most safety cars in 2023?", "What was LEC's average qualifying gap to pole in 2024?"

### 6.8 Settings Page (`app/settings/page.tsx`)

- Driver multiselect — follow/unfollow with live Firestore sync.
- Constructor multiselect.
- Notification toggles: pit stops, safety car, fastest lap, race start.
- Web Push toggle — "Enable browser notifications" button that calls `lib/webpush.ts` to request permission and POST subscription to `/users/me/push-subscription`.
- Telegram bot connection — display bot username + `/start` command, field to enter chat ID.
- Prediction risk profile selector.

---

## 7. Notifications

### 7.1 Web Push (replaces FCM — fully free, no Firebase dependency)

**Frontend (`lib/webpush.ts`):**

```typescript
// Register service worker from /public/sw.js
// Request notification permission
// Call pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: VAPID_PUBLIC_KEY })
// POST the PushSubscription object to POST /users/me/push-subscription
// Store subscription in Firestore via the backend
```

**`/public/sw.js` (service worker):**

```javascript
// Minimal service worker — handles 'push' events only
self.addEventListener('push', event => {
  const data = event.data.json();
  self.registration.showNotification(data.title, {
    body: data.body,
    icon: '/f1-icon.png',
    data: data.url || '/'
  });
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  clients.openWindow(event.notification.data);
});
```

**Backend (`services/notifications.py`):**

```python
from pywebpush import webpush, WebPushException

async def send_web_push(subscription: dict, title: str, body: str) -> None:
    """
    subscription: the PushSubscription object stored in Firestore.
    Uses VAPID keys from settings.
    Payload: JSON with title, body, url fields.
    Catch WebPushException — if status 410 (Gone), delete subscription from Firestore.
    """

async def send_telegram(chat_id: str, message: str) -> None:
    """Send via python-telegram-bot async API."""

async def notify_user(uid: str, title: str, body: str, url: str = "/") -> None:
    """
    Fetch user doc from Firestore.
    Send Web Push if web_push_subscription is set.
    Send Telegram if telegram_chat_id is set.
    Both can be active simultaneously.
    """
```

**Required package:** `pywebpush` (free, open source).

### 7.2 Notification Triggers (from `live_timing.py`)

| Event | Condition | Message |
|---|---|---|
| Pit stop | TyreLife resets to ≤ 2 for followed driver | "{driver} has pitted! Now on {compound} tyres." |
| Safety car | TrackStatus changes to '4' or '5' | "Safety car deployed on lap {lap}." |
| Fastest lap | New fastest lap set by followed driver | "{driver} sets fastest lap: {time}s" |
| Race start | First lap data received in session | "{race_name} is underway!" |

---

## 8. Data Seeding Script (`scripts/seed_data.py`)

```python
"""
Run once locally to populate Neon.tech PostgreSQL with 2022, 2023, 2024 data.

For each year, for each round:
1. Call seed_round_to_db(year, round_number, db)
2. Log: "Seeding {year} Round {round} — {circuit_name}"
3. Sleep 2s between rounds to respect FastF1 rate limits
4. On failure: log error and continue — do not abort entire seed

After seeding: run scripts/train_all.py to train and save ML models.

Expected runtime: 45–90 minutes.
Estimated storage: ~2GB FastF1 local cache + ~400MB on Neon free tier.
Note: Neon free tier cap is 0.5GB. To stay within limit, seed 2024 only first,
then add 2023 and 2022 if space allows. The app works with any subset of seasons.
"""
```

---

## 9. Model Training Script (`scripts/train_all.py`)

Train in this order (degradation before strategy):

1. **Degradation model** — all available race data. Save `models/degradation_v1.joblib`. Log RMSE.
2. **Strategy model** — same dataset, uses degradation features. Save `models/strategy_v1.joblib`.
3. **Overtake model** — from `data/overtake_dataset.csv`. Save `models/overtake_v1.joblib`.
4. **Driver fingerprint model** — per-circuit style features. Save `models/fingerprint_v1.joblib`.
5. **Circuit performance matrix** — compute and save `data/circuit_performance.parquet`.

Log all metrics to `ml_models` table in PostgreSQL.

---

## 10. Deployment

### 10.1 Backend (Render free tier)

- Service type: Web Service, runtime: Python 3.
- Build command: `pip install poetry && poetry install --no-dev`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Set all backend env vars in Render's environment settings panel.
- FastF1 cache: add a Render Disk (1GB free) mounted at `/app/cache`. Without persistent disk, the cache resets on every deploy, forcing re-downloads.
- PostgreSQL: use Neon.tech (external). Set `DATABASE_URL` to the Neon connection string.
- The live timing worker starts as a background task in `app/main.py` lifespan handler.

### 10.2 Frontend (Vercel free tier)

- Connect GitHub repo, set root directory to `frontend/`.
- Set all `NEXT_PUBLIC_*` env vars in Vercel project settings.
- `NEXT_PUBLIC_API_BASE_URL` = your Render backend URL (e.g. `https://f1-nexus.onrender.com`).
- `NEXT_PUBLIC_WS_BASE_URL` = `wss://f1-nexus.onrender.com`.

### 10.3 Cold start mitigation (`.github/workflows/keep-alive.yml`)

Render free tier spins down after 15 minutes of inactivity, causing 30–60s cold starts. This GitHub Actions workflow pings the backend every 13 minutes (stays within GitHub's 2,000 free minutes/month limit).

```yaml
name: Keep Render alive

on:
  schedule:
    - cron: '*/13 * * * *'

jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - name: Ping backend health endpoint
        run: curl -s -o /dev/null -w "%{http_code}" https://your-app.onrender.com/health
```

Add a `GET /health` endpoint to `app/main.py` that returns `{"status": "ok"}` — no auth, no DB query.

### 10.4 `app/main.py` startup sequence

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_cache()              # FastF1 cache
    init_db()                 # Create tables if not exist (Alembic handles migrations)
    init_firebase()           # Firebase Admin SDK
    await live_worker.start() # Background live timing worker (in-memory state)
    yield
    # Shutdown
    await live_worker.stop()

app = FastAPI(lifespan=lifespan)
# Add CORS middleware: allow NEXT_PUBLIC_API_BASE_URL origin
# Include all routers with /api/v1 prefix
# GET /health — no auth, returns {"status": "ok"}
```

---

## 11. Build Order for the Coding Agent

Implement modules in this exact sequence:

1. `config.py`, `database.py`, `models/sql.py` — foundation, no dependencies
2. `firebase.py` — auth layer
3. `services/fastf1_loader.py` + `scripts/seed_data.py` — get data into DB
4. `ml/degradation/` — first and most important ML module
5. `ml/strategy/` — depends on degradation model
6. `ml/driver_style/` + `ml/overtake/` — independent
7. `ml/season_prediction/` — depends on seeded DB
8. `ml/chat_rag/llm_client.py` — LLM wrapper, no other ML dependencies
9. `ml/chat_rag/retriever.py` + `ml/chat_rag/responder.py` — depends on llm_client + DB
10. All routers (`races`, `drivers`, `predictions`, `users`, `auth`, `chat`) — depend on ML + DB
11. `services/live_timing.py` + `routers/live.py` — WebSocket layer
12. `services/notifications.py` — Web Push + Telegram
13. Frontend: `lib/` utilities → auth pages → dashboard → races → drivers → predictions → live → chat → settings
14. `.github/workflows/keep-alive.yml` — last step, needs Render URL

---

## 12. Key Implementation Rules

1. **FastF1 cache always on.** Call `fastf1.Cache.enable_cache()` before any session load.

2. **LapTime is a timedelta.** Always convert with `.dt.total_seconds()` before any numerical operation.

3. **No sync I/O in async endpoints.** Wrap SQLAlchemy calls and FastF1 loads in `asyncio.to_thread()`. FastAPI is async — blocking calls freeze the server.

4. **Firebase token on every protected endpoint.** Use `get_current_user` dependency on every route returning user-specific data.

5. **Firestore for user data, PostgreSQL for race data.** Never cross this boundary.

6. **SQL injection prevention.** In `chat_rag/retriever.py`, always use `sqlalchemy.text()`. Never format user input into SQL strings.

7. **All LLM calls go through `llm_client.py`.** Never import groq, anthropic, or google.generativeai directly in any other file.

8. **No Redis anywhere.** State that would normally go in Redis goes in Python dicts with `asyncio.Lock` protection. The in-memory approach is intentional and correct for single-instance free-tier deployment.

9. **Race data is read-only from the frontend.** All writes through FastAPI.

10. **Model files are not committed to git.** Add `models/*.joblib` and `data/*.parquet` to `.gitignore`.

11. **All API responses use Pydantic schemas.** No raw dict returns from endpoints.

12. **Live timing is optional.** Every component consuming live data must have a graceful "no live session" state. The app must be fully functional during off-weekends.

13. **Neon.tech storage limit.** The Neon free tier is 0.5GB. Seed 2024 data first. If storage allows, add 2023. Log DB size after seeding with `SELECT pg_database_size('f1nexus')`.

---

## 13. What Success Looks Like

- [ ] User signs in with Google, profile created in Firestore
- [ ] User follows VER and NOR, preferences saved
- [ ] Dashboard shows followed driver cards and championship prediction strip
- [ ] `/races/2024/5` loads Chinese GP with lap time chart and tire strategy chart
- [ ] Degradation model predictions for 2024 Chinese GP have RMSE < 3.0 seconds
- [ ] Driver style page for VER shows radar chart and cluster assignment
- [ ] Championship prediction shows Monte Carlo results with probability bars
- [ ] Chat query "Who had the fastest lap at Monaco 2023?" returns correct SQL + answer via Groq
- [ ] Switching `LLM_PROVIDER=gemini` in env vars makes chat work with no code changes
- [ ] Live page shows "No live session" gracefully during off-weekend
- [ ] On a race weekend, WebSocket delivers position updates within 5 seconds
- [ ] Web Push notification fires when a followed driver pits
- [ ] Keep-alive cron prevents cold starts during active use periods
- [ ] `GET /health` returns 200 in under 100ms

---

## 14. Upgrade Path (when you have money)

Every upgrade below requires only environment variable changes or adding a new service — zero architectural rewrites.

| Current (free) | Paid upgrade | What changes |
|---|---|---|
| Render free (cold starts) | Render Starter $7/mo | Remove keep-alive cron, server stays warm |
| Groq free LLM | Anthropic Claude | Set `LLM_PROVIDER=anthropic`, add `ANTHROPIC_API_KEY` |
| In-memory dict state | Upstash Redis free → paid | Add `REDIS_URL` env var, swap `LiveTimingWorker._state` dict for Redis client — one class change |
| Neon free (0.5GB) | Neon Pro $19/mo | Change `DATABASE_URL` only |
| Web Push | Keep Web Push | Web Push is production-grade — no need to switch to FCM |

---

*End of specification. Build everything listed. Ask no clarifying questions — make reasonable decisions and document them in code comments.*
