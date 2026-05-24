"""
app/models/schemas.py - Pydantic request/response schemas for all API endpoints.

All FastAPI endpoints return typed Pydantic models, never raw dicts.
Schemas are grouped by domain (Circuit, Driver, Race, etc.).
"""

from datetime import date, datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


# ── Shared / primitives ──────────────────────────────────────────────────────

class OKResponse(BaseModel):
    status: str = "ok"


# ── Circuit ──────────────────────────────────────────────────────────────────

class CircuitSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    country: str | None
    city: str | None
    track_length_km: float | None
    lap_record_s: float | None


# ── Driver ───────────────────────────────────────────────────────────────────

class DriverSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    full_name: str | None
    nationality: str | None
    dob: date | None


class DriverWithTeamSchema(DriverSchema):
    team: str | None = None
    car_number: int | None = None


class CareerStatsSchema(BaseModel):
    races: int
    wins: int
    podiums: int
    poles: int
    points_total: float
    seasons: list[int]


class DriverProfileSchema(BaseModel):
    driver: DriverWithTeamSchema
    career_stats: CareerStatsSchema


class StyleFeaturesSchema(BaseModel):
    driver_code: str
    cluster_id: int
    cluster_description: str
    pca_x: float
    pca_y: float
    features: dict[str, float]


class SectorDeltaSchema(BaseModel):
    driver_code: str
    sector1_delta_s: float | None
    sector2_delta_s: float | None
    sector3_delta_s: float | None
    lap_time_delta_s: float | None


# ── Constructor ──────────────────────────────────────────────────────────────

class ConstructorSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


# ── Round / Race ─────────────────────────────────────────────────────────────

class RoundSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season_year: int
    round_number: int
    name: str | None
    race_date: date | None
    circuit: CircuitSchema | None


class LapSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    driver_code: str
    lap_number: int | None
    lap_time_s: float | None
    sector1_s: float | None
    sector2_s: float | None
    sector3_s: float | None
    compound: str | None
    tyre_life: int | None
    stint: int | None
    is_valid: bool
    position: int | None


class PaginatedLapsSchema(BaseModel):
    items: list[LapSchema]
    total: int
    page: int
    page_size: int


class TireStintSchema(BaseModel):
    """Single stint entry for tire strategy visualization."""
    driver_code: str
    stint: int
    compound: str
    start_lap: int
    end_lap: int
    lap_count: int


class DegradationPointSchema(BaseModel):
    tire_age: int
    predicted_lap_time_s: float
    actual_lap_time_s: float | None = None


class RaceAnalysisSchema(BaseModel):
    round: RoundSchema
    winner_code: str | None
    total_laps: int
    tire_stints: list[TireStintSchema]
    degradation_curves: dict[str, list[DegradationPointSchema]]  # driver_code -> curve


class RaceResultSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    driver_code: str
    finish_position: int | None
    points: float | None
    status: str | None
    fastest_lap: bool


# ── Qualifying ───────────────────────────────────────────────────────────────

class QualifyingSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    driver_code: str
    q1_s: float | None
    q2_s: float | None
    q3_s: float | None
    grid_position: int | None


# ── Predictions ──────────────────────────────────────────────────────────────

class DriverChampionshipPredSchema(BaseModel):
    driver_code: str
    full_name: str | None
    team: str | None
    current_points: float
    championship_probability: float
    podium_probability: float
    expected_final_points: float


class ChampionshipPredictionSchema(BaseModel):
    year: int
    drivers: list[DriverChampionshipPredSchema]
    simulations_run: int
    cached: bool = False


class RaceOutcomeDriverSchema(BaseModel):
    driver_code: str
    win_probability: float
    points_distribution: list[float]


class RaceOutcomeSchema(BaseModel):
    round_id: int
    predictions: list[RaceOutcomeDriverSchema]


class PitProbabilitySchema(BaseModel):
    lap: int
    pit_probability: float


class PitWindowSchema(BaseModel):
    recommended_lap: int
    probabilities: list[PitProbabilitySchema]
    reasoning: str


# ── Live timing ──────────────────────────────────────────────────────────────

class LiveDriverSchema(BaseModel):
    code: str
    position: int
    gap_to_leader: float
    compound: str | None
    tyre_life: int
    predicted_stint_end: int | None
    last_lap_s: float | None
    sector1_s: float | None
    sector2_s: float | None
    sector3_s: float | None
    drs: bool
    pitting: bool


class LiveUpdateSchema(BaseModel):
    type: str = "position_update"
    timestamp: str
    session_type: str
    lap: int
    drivers: list[LiveDriverSchema]


class NextRaceSchema(BaseModel):
    name: str
    location: str | None = None
    country: str | None = None
    date: str | None = None
    time: str | None = None
    session_type: str | None = None


class LiveStatusSchema(BaseModel):
    active: bool
    session_type: str | None
    current_lap: int
    race_name: str | None = None
    location: str | None = None
    country: str | None = None
    next_race: NextRaceSchema | None = None


# ── Chat / RAG ───────────────────────────────────────────────────────────────

class ChatQueryRequest(BaseModel):
    question: str


class ChatAnswerSchema(BaseModel):
    answer: str
    sql: str
    row_count: int
    data: list[dict[str, Any]]


class ChatSuggestionsSchema(BaseModel):
    suggestions: list[str]


# ── Users / Auth ─────────────────────────────────────────────────────────────

class UserSyncRequest(BaseModel):
    """Called by frontend after Google sign-in to create/update Firestore profile."""
    display_name: str | None = None


class UserProfileSchema(BaseModel):
    uid: str
    display_name: str | None
    email: str | None
    followed_drivers: list[str]
    followed_constructors: list[str]
    notification_prefs: dict[str, bool]
    season_pred_profile: str
    telegram_chat_id: str | None
    has_web_push: bool


class UserPreferencesRequest(BaseModel):
    followed_drivers: list[str] | None = None
    followed_constructors: list[str] | None = None
    notification_prefs: dict[str, bool] | None = None
    season_pred_profile: str | None = None
    telegram_chat_id: str | None = None


class WebPushSubscriptionRequest(BaseModel):
    """The PushSubscription object serialized from the browser."""
    endpoint: str
    keys: dict[str, str]
    expiration_time: int | None = None
