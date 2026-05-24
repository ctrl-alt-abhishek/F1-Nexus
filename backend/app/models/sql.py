"""
app/models/sql.py - SQLAlchemy ORM models for all PostgreSQL tables.

Design rules:
- Race/telemetry data lives here. User preferences live in Firestore, never here.
- Laps is the core analytical table and will be the largest (~millions of rows).
- All foreign keys are indexed. Additional composite indexes on laps for the
  most common query patterns.
"""

from datetime import datetime, date
from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text, UniqueConstraint, Index, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Circuit(Base):
    __tablename__ = "circuits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str | None] = mapped_column(String(60))
    city: Mapped[str | None] = mapped_column(String(60))
    track_length_km: Mapped[float | None] = mapped_column(Float)
    lap_record_s: Mapped[float | None] = mapped_column(Float)

    rounds: Mapped[list["Round"]] = relationship("Round", back_populates="circuit")


class Season(Base):
    __tablename__ = "seasons"

    year: Mapped[int] = mapped_column(Integer, primary_key=True)

    rounds: Mapped[list["Round"]] = relationship("Round", back_populates="season")
    standings: Mapped[list["ChampionshipStanding"]] = relationship(
        "ChampionshipStanding", back_populates="season"
    )


class Round(Base):
    __tablename__ = "rounds"
    __table_args__ = (
        UniqueConstraint("season_year", "round_number", name="uq_round_season_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season_year: Mapped[int] = mapped_column(Integer, ForeignKey("seasons.year"), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    circuit_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("circuits.id"))
    race_date: Mapped[date | None] = mapped_column(Date)
    name: Mapped[str | None] = mapped_column(String(150))

    season: Mapped["Season"] = relationship("Season", back_populates="rounds")
    circuit: Mapped["Circuit"] = relationship("Circuit", back_populates="rounds")
    laps: Mapped[list["Lap"]] = relationship("Lap", back_populates="round")
    qualifying: Mapped[list["Qualifying"]] = relationship("Qualifying", back_populates="round")
    race_results: Mapped[list["RaceResult"]] = relationship("RaceResult", back_populates="round")


class Driver(Base):
    __tablename__ = "drivers"

    # 3-letter driver code is the natural primary key: VER, LEC, NOR, etc.
    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    full_name: Mapped[str | None] = mapped_column(String(100))
    nationality: Mapped[str | None] = mapped_column(String(60))
    dob: Mapped[date | None] = mapped_column(Date)

    laps: Mapped[list["Lap"]] = relationship("Lap", back_populates="driver")
    qualifying: Mapped[list["Qualifying"]] = relationship("Qualifying", back_populates="driver")
    race_results: Mapped[list["RaceResult"]] = relationship("RaceResult", back_populates="driver")
    season_entries: Mapped[list["DriverSeason"]] = relationship("DriverSeason", back_populates="driver")
    standings: Mapped[list["ChampionshipStanding"]] = relationship(
        "ChampionshipStanding", back_populates="driver"
    )


class Constructor(Base):
    __tablename__ = "constructors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    season_entries: Mapped[list["DriverSeason"]] = relationship(
        "DriverSeason", back_populates="constructor"
    )


class DriverSeason(Base):
    """Maps a driver to their constructor for a given season, plus car number."""
    __tablename__ = "driver_season"

    driver_code: Mapped[str] = mapped_column(String(3), ForeignKey("drivers.code"), primary_key=True)
    season_year: Mapped[int] = mapped_column(Integer, ForeignKey("seasons.year"), primary_key=True)
    constructor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("constructors.id"))
    car_number: Mapped[int | None] = mapped_column(Integer)

    driver: Mapped["Driver"] = relationship("Driver", back_populates="season_entries")
    season: Mapped["Season"] = relationship("Season")
    constructor: Mapped["Constructor"] = relationship("Constructor", back_populates="season_entries")


class Lap(Base):
    """
    Core analytical table. Every clean lap from every race session.
    Expected to grow to several million rows across 2022-2024.

    is_valid=False laps are retained for completeness but excluded from ML
    training and most queries.
    """
    __tablename__ = "laps"
    __table_args__ = (
        Index("ix_laps_round_driver", "round_id", "driver_code"),
        Index("ix_laps_driver_compound", "driver_code", "compound"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    round_id: Mapped[int] = mapped_column(Integer, ForeignKey("rounds.id"), nullable=False)
    driver_code: Mapped[str] = mapped_column(String(3), ForeignKey("drivers.code"), nullable=False)
    lap_number: Mapped[int | None] = mapped_column(Integer)
    lap_time_s: Mapped[float | None] = mapped_column(Float)  # NULL for laps without a valid time
    sector1_s: Mapped[float | None] = mapped_column(Float)
    sector2_s: Mapped[float | None] = mapped_column(Float)
    sector3_s: Mapped[float | None] = mapped_column(Float)
    compound: Mapped[str | None] = mapped_column(String(20))  # SOFT, MEDIUM, HARD, INTERMEDIATE, WET
    tyre_life: Mapped[int | None] = mapped_column(Integer)
    stint: Mapped[int | None] = mapped_column(Integer)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    track_status: Mapped[str | None] = mapped_column(String(5))  # '1'=green, '4'=SC, '5'=VSC
    position: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    round: Mapped["Round"] = relationship("Round", back_populates="laps")
    driver: Mapped["Driver"] = relationship("Driver", back_populates="laps")


class Qualifying(Base):
    __tablename__ = "qualifying"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    round_id: Mapped[int] = mapped_column(Integer, ForeignKey("rounds.id"), nullable=False)
    driver_code: Mapped[str] = mapped_column(String(3), ForeignKey("drivers.code"), nullable=False)
    q1_s: Mapped[float | None] = mapped_column(Float)
    q2_s: Mapped[float | None] = mapped_column(Float)
    q3_s: Mapped[float | None] = mapped_column(Float)
    grid_position: Mapped[int | None] = mapped_column(Integer)

    round: Mapped["Round"] = relationship("Round", back_populates="qualifying")
    driver: Mapped["Driver"] = relationship("Driver", back_populates="qualifying")


class RaceResult(Base):
    __tablename__ = "race_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    round_id: Mapped[int] = mapped_column(Integer, ForeignKey("rounds.id"), nullable=False)
    driver_code: Mapped[str] = mapped_column(String(3), ForeignKey("drivers.code"), nullable=False)
    finish_position: Mapped[int | None] = mapped_column(Integer)
    points: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str | None] = mapped_column(String(50))  # "Finished", "+1 Lap", "DNF", etc.
    fastest_lap: Mapped[bool] = mapped_column(Boolean, default=False)

    round: Mapped["Round"] = relationship("Round", back_populates="race_results")
    driver: Mapped["Driver"] = relationship("Driver", back_populates="race_results")


class ChampionshipStanding(Base):
    """
    Snapshot of the championship standings after each round.
    Populated by seed_data.py and updated after each race.
    Allows fast queries like "VER's points after round 10" without aggregating all laps.
    """
    __tablename__ = "championship_standings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    season_year: Mapped[int] = mapped_column(Integer, ForeignKey("seasons.year"), nullable=False)
    after_round: Mapped[int] = mapped_column(Integer, nullable=False)
    driver_code: Mapped[str] = mapped_column(String(3), ForeignKey("drivers.code"), nullable=False)
    points: Mapped[float | None] = mapped_column(Float)
    wins: Mapped[int | None] = mapped_column(Integer)
    position: Mapped[int | None] = mapped_column(Integer)

    season: Mapped["Season"] = relationship("Season", back_populates="standings")
    driver: Mapped["Driver"] = relationship("Driver", back_populates="standings")


class MLModel(Base):
    """
    Registry of trained model artifacts. Upserted by train_all.py after each run.
    One row per model name — updated in place on retrain.
    """
    __tablename__ = "ml_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)  # 'degradation', 'strategy', etc.
    version: Mapped[str | None] = mapped_column(String(20))  # datestamp e.g. '20240424_1430'
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    artifact_path: Mapped[str | None] = mapped_column(String(300))  # path to .joblib file
    metrics: Mapped[dict | None] = mapped_column(JSON)  # {rmse, r2, f1, auc, ...}
    feature_names: Mapped[list | None] = mapped_column(JSON)  # list of feature column names
    hyperparams: Mapped[dict | None] = mapped_column(JSON)  # XGB/model hyperparameters
