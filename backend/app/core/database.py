"""Small SQLite repository for durable local demo state.

This is intentionally dependency-free so the Windows demo can run without a
separate database server. It stores only synthetic/demo train and scenario data.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.data import TRAINS


def default_database_path() -> Path:
    configured = os.getenv("RAILFLOW_DB_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "data" / "railflow.sqlite3"


class RailFlowRepository:
    def __init__(self, database_path: str | Path | None = None, seed_trains: bool = True):
        self.database_path = Path(database_path) if database_path else default_database_path()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize(seed_trains=seed_trains)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def initialize(self, seed_trains: bool = True) -> None:
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS trains (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS scenario_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario TEXT NOT NULL,
                seed INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                payload TEXT NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS delay_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                features TEXT NOT NULL,
                actual_delay_min REAL NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""")
            count = db.execute("SELECT COUNT(*) FROM trains").fetchone()[0]
            if seed_trains and count == 0:
                now = datetime.now(timezone.utc).isoformat()
                db.executemany(
                    "INSERT INTO trains (id, payload, updated_at) VALUES (?, ?, ?)",
                    [(row["id"], json.dumps(row), now) for row in TRAINS],
                )

    def list_trains(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT payload FROM trains ORDER BY rowid").fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def get_train(self, train_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT payload FROM trains WHERE id=?", (train_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def save_train(self, train: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(train)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            db.execute(
                "INSERT INTO trains (id, payload, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                (train["id"], payload, now),
            )
        return train

    def delete_train(self, train_id: str) -> bool:
        with self._connect() as db:
            cursor = db.execute("DELETE FROM trains WHERE id=?", (train_id,))
            return cursor.rowcount > 0

    def save_scenario(self, result: dict[str, Any]) -> int:
        scenario = str(result.get("scenario", "unknown"))
        seed = int(result.get("seed", 0))
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO scenario_runs (scenario, seed, created_at, payload) VALUES (?, ?, ?, ?)",
                (scenario, seed, created_at, json.dumps(result)),
            )
            return int(cursor.lastrowid)

    def list_scenarios(self, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, scenario, seed, created_at, payload FROM scenario_runs "
                "ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            {"id": row["id"], "scenario": row["scenario"], "seed": row["seed"],
             "created_at": row["created_at"], "result": json.loads(row["payload"])}
            for row in rows
        ]

    def save_delay_feedback(self, features: list[float], actual_delay_min: float, source: str) -> int:
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO delay_feedback (features, actual_delay_min, source, created_at) VALUES (?, ?, ?, ?)",
                (json.dumps(features), actual_delay_min, source, datetime.now(timezone.utc).isoformat()),
            )
            return int(cursor.lastrowid)

    def list_delay_feedback(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT features, actual_delay_min FROM delay_feedback ORDER BY id").fetchall()
        return [{"features": json.loads(row["features"]), "actual_delay_min": row["actual_delay_min"]} for row in rows]

    def count_delay_feedback(self) -> int:
        with self._connect() as db:
            return int(db.execute("SELECT COUNT(*) FROM delay_feedback").fetchone()[0])
