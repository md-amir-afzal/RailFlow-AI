"""Explainable train-to-train conflict screening for the sample corridor.

Uses planned departure + current simulated delay and modeled section traversal
estimates. It is a screening aid over synthetic data, not an interlocking model.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from itertools import combinations

from app.railway_network.graph import GRAPH


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def detect_conflicts(trains: list[dict], headway_min: int = 8) -> dict:
    if not 1 <= int(headway_min) <= 60:
        raise ValueError("headway_min must be between 1 and 60 minutes")

    section_movements: dict[tuple[str, str], list[dict]] = defaultdict(list)
    invalid_route_train_ids = []
    for train in trains:
        route = train.get("route", [])
        if len(route) < 2 or any(not GRAPH.has_edge(a, b) for a, b in zip(route, route[1:])):
            invalid_route_train_ids.append(train.get("id", "UNKNOWN"))
            continue
        departure = _parse_time(train["scheduled_departure"]) + timedelta(
            minutes=max(0, int(train.get("delay_min", 0)))
        )
        speed = max(1.0, float(train.get("speed_kmph", 80)))
        for a, b in zip(route, route[1:]):
            edge = GRAPH[a][b]
            duration = timedelta(minutes=max(1.0, edge["distance_km"] / speed * 60.0))
            section = tuple(sorted((a, b)))
            section_movements[section].append({
                "train_id": train["id"],
                "train_name": train.get("name", train["id"]),
                "entry": departure,
                "exit": departure + duration,
                "tracks": int(edge.get("tracks", 1)),
            })
            departure += duration

    conflicts = []
    for (a, b), movements in section_movements.items():
        movements.sort(key=lambda item: (item["entry"], item["train_id"]))
        tracks = movements[0]["tracks"]
        for first, second in combinations(movements, 2):
            if first["train_id"] == second["train_id"]:
                continue
            overlap = first["entry"] < second["exit"] and second["entry"] < first["exit"]
            entry_gap = abs((second["entry"] - first["entry"]).total_seconds()) / 60
            headway_violation = entry_gap < headway_min
            if tracks == 1 and (overlap or headway_violation):
                conflicts.append({
                    "section": f"{a} – {b}",
                    "from": a,
                    "to": b,
                    "track_count": tracks,
                    "conflict_type": "SECTION_OVERLAP" if overlap else "HEADWAY_VIOLATION",
                    "severity": "Critical" if overlap else "High",
                    "train_ids": [first["train_id"], second["train_id"]],
                    "train_names": [first["train_name"], second["train_name"]],
                    "entry_times": [first["entry"].isoformat(), second["entry"].isoformat()],
                    "exit_times": [first["exit"].isoformat(), second["exit"].isoformat()],
                    "entry_gap_min": round(entry_gap, 1),
                    "overlap": overlap,
                    "overlap_min": round(max(0.0, (min(first["exit"], second["exit"]) - max(first["entry"], second["entry"])).total_seconds() / 60), 1),
                    "explanation": (
                        "Estimated section occupancy overlaps."
                        if overlap else f"Estimated entry gap is below the {headway_min}-minute demo headway."
                    ),
                })

        # For multi-track sections, flag only periods when simultaneous modeled
        # occupancy exceeds the declared parallel-track count.
        if tracks > 1:
            boundaries = sorted({m["entry"] for m in movements} | {m["exit"] for m in movements})
            for start, end in zip(boundaries, boundaries[1:]):
                if end <= start:
                    continue
                active = [m for m in movements if m["entry"] < end and m["exit"] > start]
                if len(active) > tracks:
                    conflicts.append({
                        "section": f"{a} – {b}",
                        "from": a,
                        "to": b,
                        "track_count": tracks,
                        "conflict_type": "TRACK_CAPACITY_EXCEEDED",
                        "severity": "Critical",
                        "train_ids": sorted({m["train_id"] for m in active}),
                        "train_names": sorted({m["train_name"] for m in active}),
                        "entry_times": [start.isoformat()],
                        "exit_times": [end.isoformat()],
                        "entry_gap_min": None,
                        "overlap": True,
                        "overlap_min": round((end - start).total_seconds() / 60, 1),
                        "explanation": f"{len(active)} trains overlap on a section modeled with {tracks} parallel tracks.",
                    })
                    break

    conflicts.sort(key=lambda item: (item["severity"] != "Critical", item["from"], item["to"], item["train_ids"]))
    return {
        "headway_min": headway_min,
        "conflict_count": len(conflicts),
        "critical_count": sum(item["severity"] == "Critical" for item in conflicts),
        "conflicts": conflicts,
        "invalid_route_train_ids": invalid_route_train_ids,
        "method": "Estimated section-entry/exit overlap and minimum-headway screening",
        "data_mode": "SYNTHETIC DEMO",
        "safety_note": "Screening only. Does not model signalling blocks, interlocking, routesetting, platform occupation, braking curves or railway operating rules. Never use as an authority to dispatch trains.",
    }
