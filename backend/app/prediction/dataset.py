"""Synthetic delay-dataset generator.

Produces reproducible, explicitly synthetic trip records used to train the
delay-prediction baselines. No real railway data is involved.
"""
from __future__ import annotations

import numpy as np

RANDOM_SEED = 20260109
DEFAULT_ROW_COUNT = 250_000

FEATURE_COLUMNS = [
    "category_code",
    "departure_hour",
    "day_of_week",
    "route_distance_km",
    "num_stops",
    "priority",
    "section_congestion",
    "trains_on_section",
    "single_track_share",
    "weather_severity",
    "previous_delay_min",
    "maintenance_window",
]
TARGET_COLUMN = "arrival_delay_min"

# Category order matches CATEGORY_CODES in model.py.
CATEGORY_PENALTY = np.array([1.3, 0.8, 2.6, 3.2, 4.0, 1.8])
SINGLE_TRACK_CHOICES = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
SINGLE_TRACK_WEIGHTS = np.array([0.34, 0.22, 0.20, 0.14, 0.10])
MAINTENANCE_PROBABILITY = 0.12
NOISE_SIGMA = 2.6


def _feature_matrix(rows: int, rng: np.random.Generator) -> np.ndarray:
    category = rng.integers(0, 6, rows)
    hour = rng.integers(0, 24, rows)
    day_of_week = rng.integers(0, 7, rows)
    distance_km = rng.uniform(80, 1900, rows)
    num_stops = rng.integers(0, 18, rows)
    priority = rng.integers(1, 6, rows)
    congestion = np.clip(rng.beta(2.2, 3.0, rows), 0.0, 1.0)
    trains_on_section = np.clip(
        np.rint(congestion * 26 + rng.normal(0, 3, rows)), 0, 40
    ).astype(int)
    single_track = rng.choice(SINGLE_TRACK_CHOICES, rows, p=SINGLE_TRACK_WEIGHTS)
    weather = np.clip(rng.beta(1.4, 4.5, rows), 0.0, 1.0)
    previous_delay = np.clip(rng.gamma(1.7, 6.5, rows), 0.0, 90.0)
    maintenance = (rng.random(rows) < MAINTENANCE_PROBABILITY).astype(int)

    return np.column_stack(
        [
            category,
            hour,
            day_of_week,
            distance_km,
            num_stops,
            priority,
            congestion,
            trains_on_section,
            single_track,
            weather,
            previous_delay,
            maintenance,
        ]
    )


def _target_vector(features: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    category = features[:, 0].astype(int)
    hour = features[:, 1]
    day_of_week = features[:, 2]
    distance_km = features[:, 3]
    num_stops = features[:, 4]
    priority = features[:, 5]
    congestion = features[:, 6]
    trains_on_section = features[:, 7]
    single_track = features[:, 8]
    weather = features[:, 9]
    previous_delay = features[:, 10]
    maintenance = features[:, 11]

    peak_hour = ((hour >= 7) & (hour <= 11)) | ((hour >= 16) & (hour <= 20))
    weekend = day_of_week >= 5
    # Congestion hurts non-linearly once the section passes ~60% utilisation.
    crowd_penalty = np.where(
        congestion > 0.6, (congestion - 0.6) * 21.0, congestion * 4.0
    )
    end_to_end_drag = distance_km / 900.0

    delay = (
        0.4
        + CATEGORY_PENALTY[category]
        + crowd_penalty
        + trains_on_section * 0.14
        + single_track * 7.0
        + weather * 6.0
        + previous_delay * 0.30
        + maintenance * 4.0
        + np.where(peak_hour, 2.4, 0.0)
        + np.where(weekend, 0.9, 0.0)
        + num_stops * 0.15
        + end_to_end_drag
        - (priority - 3) * 1.5
        + np.sin(hour / 24.0 * 2.0 * np.pi) * 1.2
        + rng.normal(0.0, NOISE_SIGMA, features.shape[0])
    )
    return np.round(np.maximum(0.0, delay), 1)


def generate_delay_dataset(
    rows: int = DEFAULT_ROW_COUNT, seed: int = RANDOM_SEED
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(features, target)`` as float arrays of shape (rows, 12) and (rows,)."""
    if rows < 1:
        raise ValueError("rows must be a positive integer")
    rng = np.random.default_rng(seed)
    features = _feature_matrix(rows, rng)
    target = _target_vector(features, rng)
    return features.astype(float), target.astype(float)
