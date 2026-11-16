"""Delay-prediction baselines trained on the synthetic trip dataset.

The dataset is a generated CSV of ``DEFAULT_ROW_COUNT`` trips with twelve
operational features. Models are compared on a chronological holdout and the
best by MAE is kept. The fitted artifact is cached so import stays fast.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from threadpoolctl import threadpool_limits

from app.core.data import EDGES
from app.prediction.dataset import (
    FEATURE_COLUMNS,
    RANDOM_SEED,
    generate_delay_dataset,
)

CATEGORY_CODES = {
    "Superfast": 0,
    "Express": 1,
    "Passenger": 2,
    "Local": 3,
    "Freight": 4,
    "Special": 5,
}
DEFAULT_CATEGORY_CODE = 1
DEFAULT_CONGESTION = 0.25
DEFAULT_WEATHER = 0.2
MAX_PREVIOUS_DELAY = 90.0
MIN_DISTANCE_KM = 80.0
MAX_DISTANCE_KM = 1900.0
TRAIN_SHARE = 0.8
ARTIFACT_VERSION = 3

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATASET_PATH = PROJECT_ROOT / "data" / "synthetic" / "train_delays.csv"
ARTIFACT_PATH = PROJECT_ROOT / "backend" / "data" / "delay_model.joblib"

_SEGMENTS = {
    frozenset((start, end)): (float(km), int(tracks))
    for start, end, km, tracks in EDGES
}


def route_profile(route: list[str] | None) -> tuple[float, float]:
    """Return (total_distance_km, share_of_single_track_legs) for a route."""
    stops = list(route or [])
    total_km = 0.0
    single_track_legs = 0
    known_legs = 0
    for start, end in zip(stops, stops[1:]):
        segment = _SEGMENTS.get(frozenset((start, end)))
        if segment is None:
            continue
        km, tracks = segment
        total_km += km
        known_legs += 1
        if tracks == 1:
            single_track_legs += 1
    share = single_track_legs / known_legs if known_legs else 0.0
    return total_km, share


def _parse_departure(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime(2026, 11, 9, 8, 0)


def load_dataset() -> tuple[np.ndarray, np.ndarray, str]:
    """Load the CSV dataset when available, otherwise generate it in memory."""
    if DATASET_PATH.exists():
        matrix = np.loadtxt(DATASET_PATH, delimiter=",", skiprows=1, ndmin=2)
        if matrix.shape[1] == len(FEATURE_COLUMNS) + 1 and matrix.shape[0] >= 1000:
            return (
                matrix[:, :-1],
                matrix[:, -1],
                f"Synthetic CSV dataset ({matrix.shape[0]:,} rows)",
            )
    features, target = generate_delay_dataset()
    return features, target, f"Generated synthetic dataset ({features.shape[0]:,} rows)"


def _build_models() -> dict[str, object]:
    return {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(
            # Keep the API usable in restricted/local environments that cannot
            # create worker processes (and avoid oversubscribing shared hosts).
            n_estimators=80, max_depth=14, random_state=RANDOM_SEED, n_jobs=1
        ),
        "Gradient Boosting": HistGradientBoostingRegressor(
            max_iter=250, learning_rate=0.12, random_state=RANDOM_SEED
        ),
    }


class DelayModel:
    """Reproducible regression baselines over the synthetic trip dataset."""

    def __init__(self, use_cache: bool = True) -> None:
        self.dataset_label = ""
        self.metrics: dict[str, dict[str, float]] = {}
        self.best_name = ""
        self.model = None
        self.feature_importance: list[tuple[str, float]] = []
        if use_cache and self._load_artifact():
            return
        self._train()
        if use_cache:
            self._save_artifact()

    def _train(self, feedback: list[dict] | None = None) -> None:
        features, target, label = load_dataset()
        self.dataset_label = label
        split = int(len(features) * TRAIN_SHARE)
        x_train, x_test = features[:split], features[split:]
        y_train, y_test = target[:split], target[split:]

        models = _build_models()
        for name, candidate in models.items():
            # sklearn's histogram booster uses OpenMP threads even when the
            # Random Forest itself is configured for one worker.
            with threadpool_limits(limits=1):
                candidate.fit(x_train, y_train)
            predicted = candidate.predict(x_test)
            self.metrics[name] = {
                "mae": round(float(mean_absolute_error(y_test, predicted)), 2),
                "rmse": round(float(np.sqrt(mean_squared_error(y_test, predicted))), 2),
                "r2": round(float(r2_score(y_test, predicted)), 3),
            }
        self.best_name = min(self.metrics, key=lambda name: self.metrics[name]["mae"])
        self.model = models[self.best_name]
        # Score candidates on a chronological synthetic holdout, then refit the
        # winner on all generated rows plus verified outcomes supplied by operators.
        x_fit, y_fit = features, target
        if feedback:
            feedback_x = np.asarray([row["features"] for row in feedback], dtype=float)
            feedback_y = np.asarray([row["actual_delay_min"] for row in feedback], dtype=float)
            if feedback_x.ndim == 2 and feedback_x.shape[1] == len(FEATURE_COLUMNS):
                x_fit = np.vstack((features, feedback_x))
                y_fit = np.concatenate((target, feedback_y))
                self.dataset_label = f"{label} + {len(feedback):,} verified outcomes"
        with threadpool_limits(limits=1):
            self.model.fit(x_fit, y_fit)

        forest = models["Random Forest"]
        importances = getattr(forest, "feature_importances_", None)
        if importances is not None:
            ranked = sorted(
                zip(FEATURE_COLUMNS, importances), key=lambda pair: pair[1], reverse=True
            )
            self.feature_importance = [(n, round(float(v), 4)) for n, v in ranked]

    def _load_artifact(self) -> bool:
        if not ARTIFACT_PATH.exists():
            return False
        try:
            payload = joblib.load(ARTIFACT_PATH)
        except (OSError, EOFError, ValueError, AttributeError):
            return False
        if payload.get("version") != ARTIFACT_VERSION:
            return False
        if payload.get("features") != FEATURE_COLUMNS:
            return False
        self.model = payload["model"]
        self.metrics = payload["metrics"]
        self.best_name = payload["best_name"]
        self.dataset_label = payload["dataset_label"]
        self.feature_importance = payload.get("feature_importance", [])
        return True

    def _save_artifact(self) -> None:
        ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "version": ARTIFACT_VERSION,
                "features": FEATURE_COLUMNS,
                "model": self.model,
                "metrics": self.metrics,
                "best_name": self.best_name,
                "dataset_label": self.dataset_label,
                "feature_importance": self.feature_importance,
            },
            ARTIFACT_PATH,
            compress=3,
        )

    def learn_from_feedback(self, feedback: list[dict]) -> None:
        """Refit from generated baseline data and persisted, verified outcomes."""
        self._train(feedback)
        self._save_artifact()

    def build_features(self, train: dict, congestion: float | None = None) -> np.ndarray:
        """Map an application train record onto the model's feature vector."""
        departure = _parse_departure(train.get("scheduled_departure", ""))
        distance_km, single_track_share = route_profile(train.get("route"))
        level = DEFAULT_CONGESTION if congestion is None else float(congestion)
        level = min(max(level, 0.0), 1.0)
        route_stops = train.get("route") or []

        values = {
            "category_code": CATEGORY_CODES.get(
                train.get("category"), DEFAULT_CATEGORY_CODE
            ),
            "departure_hour": departure.hour,
            "day_of_week": departure.weekday(),
            "route_distance_km": min(
                max(distance_km, MIN_DISTANCE_KM), MAX_DISTANCE_KM
            ),
            "num_stops": max(0, len(route_stops) - 2),
            "priority": int(train.get("priority", 3)),
            "section_congestion": level,
            "trains_on_section": int(round(level * 26)),
            "single_track_share": single_track_share,
            "weather_severity": float(train.get("weather_severity", DEFAULT_WEATHER)),
            "previous_delay_min": min(
                float(train.get("delay_min", 0)), MAX_PREVIOUS_DELAY
            ),
            "maintenance_window": int(train.get("maintenance_window", 0)),
        }
        return np.array([[values[name] for name in FEATURE_COLUMNS]], dtype=float)

    def predict(self, train: dict, congestion: float = DEFAULT_CONGESTION) -> float:
        features = self.build_features(train, congestion)
        return max(0.0, round(float(self.model.predict(features)[0]), 1))


MODEL = DelayModel()
