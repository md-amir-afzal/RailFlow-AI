"""Constraint-aware corridor scheduler for the illustrative network.

This is a deterministic planning heuristic, not a certified railway interlocking system.
It reserves modeled track sections, respects section track capacity and minimum headway,
and never invents a route or changes its topology.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timedelta
from collections import defaultdict
from app.railway_network.graph import GRAPH


def _dt(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"Invalid scheduled_departure: {value!r}") from exc


def _section_minutes(a: str, b: str, speed: float) -> float:
    edge = GRAPH.get_edge_data(a, b)
    if edge is None:
        raise ValueError(f"Route contains unknown track section {a}-{b}")
    return max(1.0, edge['distance_km'] / max(float(speed), 1.0) * 60.0)


def optimize(trains, headway=8, horizon_hours=24):
    """Schedule trains against shared section reservations using earliest-feasible dispatch.

    Priority is used as a tie-breaker for trains with the same requested departure.
    Each modeled physical section has ``tracks`` parallel capacity slots. Opposing
    movements share the same section resource, intentionally conservative for this demo.
    """
    if not 1 <= int(headway) <= 60:
        raise ValueError('headway must be between 1 and 60 minutes')
    rows = deepcopy(trains)
    for t in rows:
        route = t.get('route', [])
        if len(route) < 2 or any(not GRAPH.has_edge(a, b) for a, b in zip(route, route[1:])):
            raise ValueError(f"Train {t.get('id')} has an infeasible modeled route")
    rows.sort(key=lambda t: (_dt(t['scheduled_departure']), -int(t.get('priority', 1)), t['id']))
    reservations = defaultdict(list)
    results = []
    horizon = timedelta(hours=horizon_hours)

    for train in rows:
        requested = _dt(train['scheduled_departure']) + timedelta(minutes=max(0, int(train.get('delay_min', 0))))
        route = train['route']
        speed = float(train.get('speed_kmph', 80))
        candidate = requested
        chosen = None
        while candidate - requested <= horizon:
            cursor = candidate
            proposed = []
            feasible = True
            for a, b in zip(route, route[1:]):
                duration = timedelta(minutes=_section_minutes(a, b, speed))
                section = tuple(sorted((a, b)))
                tracks = int(GRAPH[a][b].get('tracks', 1))
                active = reservations[section]
                # A section can host up to its modeled number of trains simultaneously.
                # Headway additionally separates entry times on each shared section.
                entry_conflicts = [r for r in active if abs((cursor-r['entry']).total_seconds()) < headway*60]
                overlapping = [r for r in active if cursor < r['exit'] and cursor+duration > r['entry']]
                if len(overlapping) >= tracks or (tracks == 1 and entry_conflicts):
                    next_time = min((r['exit'] + timedelta(minutes=headway if tracks == 1 else 0)
                                     for r in (overlapping or entry_conflicts)), default=cursor)
                    candidate += max(timedelta(minutes=1), next_time-cursor)
                    feasible = False
                    break
                proposed.append((section, cursor, cursor+duration))
                cursor += duration
            if feasible:
                chosen = (candidate, cursor, proposed)
                break
        if chosen is None:
            raise ValueError(f"No feasible slot found for train {train['id']} within {horizon_hours} hours")
        departure, arrival, proposed = chosen
        for section, entry, exit_at in proposed:
            reservations[section].append({'entry': entry, 'exit': exit_at, 'train_id': train['id']})
        original_departure = _dt(train['scheduled_departure'])
        optimized_delay = max(0, round((departure-original_departure).total_seconds()/60))
        original_delay = max(0, int(train.get('delay_min', 0)))
        item = deepcopy(train)
        item.update({
            'optimized_departure': departure.isoformat(),
            'optimized_arrival': arrival.isoformat(),
            'optimized_delay_min': optimized_delay,
            'change_min': optimized_delay-original_delay,
            'planned_wait_min': max(0, round((departure-requested).total_seconds()/60)),
            'explanation': 'Earliest feasible dispatch after checking every modeled route section, track capacity and minimum entry headway.',
        })
        results.append(item)

    original_total = sum(max(0, int(t.get('delay_min', 0))) for t in rows)
    optimized_total = sum(t['optimized_delay_min'] for t in results)
    return {
        'status': 'FEASIBLE_HEURISTIC', 'method': 'Section-reservation earliest-feasible scheduler',
        'headway_min': headway, 'horizon_hours': horizon_hours,
        'original_total_delay_min': original_total, 'optimized_total_delay_min': optimized_total,
        'delay_change_min': optimized_total-original_total, 'trains': results,
        'resource_sections_reserved': len(reservations),
        'safety_note': 'Decision-support proposal only. Not connected to signals, interlocking, switches or train control; authorized railway validation is mandatory.'
    }
