"""Reproducible discrete-event-style corridor occupancy simulation."""
from __future__ import annotations
import random
from copy import deepcopy
from datetime import datetime, timedelta
from collections import defaultdict
from app.railway_network.graph import GRAPH

SCENARIOS = {'normal', 'heavy_traffic', 'junction_delay', 'single_track', 'platform_block', 'maintenance'}


def run_scenario(trains, scenario='heavy_traffic', seed=42, intensity=30):
    if scenario not in SCENARIOS:
        raise ValueError(f'Unsupported scenario: {scenario}')
    if not 0 <= int(intensity) <= 180:
        raise ValueError('intensity must be between 0 and 180')
    rng = random.Random(seed)
    rows = deepcopy(trains)
    events = []
    occupancy = defaultdict(list)
    for train in sorted(rows, key=lambda t: t.get('scheduled_departure', '')):
        route = train.get('route', [])
        if len(route) < 2 or any(not GRAPH.has_edge(a, b) for a, b in zip(route, route[1:])):
            raise ValueError(f"Train {train.get('id')} has an infeasible route")
        added = 0
        if scenario == 'heavy_traffic': added = rng.randint(0, intensity)
        elif scenario == 'junction_delay' and any(GRAPH.degree(n) >= 3 for n in route[1:-1]): added = intensity
        elif scenario == 'single_track' and any(GRAPH[a][b].get('tracks', 1) == 1 for a, b in zip(route, route[1:])): added = intensity // 2
        elif scenario == 'platform_block' and train.get('category') in ('Express', 'Superfast'): added = intensity // 3
        elif scenario == 'maintenance' and len(route) > 3: added = intensity // 2
        delay = max(0, int(train.get('delay_min', 0))) + added
        depart = datetime.fromisoformat(train['scheduled_departure'].replace('Z', '+00:00')) + timedelta(minutes=delay)
        cursor = depart
        section_events = []
        for a, b in zip(route, route[1:]):
            edge = GRAPH[a][b]
            duration = max(1.0, edge['distance_km'] / max(float(train.get('speed_kmph', 80)), 1) * 60)
            start, end = cursor, cursor + timedelta(minutes=duration)
            key = tuple(sorted((a, b)))
            active = sum(1 for x, y, _ in occupancy[key] if start < y and end > x)
            capacity = int(edge.get('tracks', 1))
            section_events.append({'from': a, 'to': b, 'entry': start.isoformat(), 'exit': end.isoformat(), 'capacity': capacity, 'overlap_count_before_entry': active})
            occupancy[key].append((start, end, train['id']))
            cursor = end
        train.update({'delay_min': delay, 'status': 'Delayed' if delay > 5 else 'On time', 'simulation_added_delay_min': added, 'simulated_arrival': cursor.isoformat(), 'section_events': section_events})
        events.append({'train_id': train['id'], 'event': 'SIMULATED_ROUTE_COMPLETION', 'at': cursor.isoformat(), 'sections_traversed': len(section_events)})
    section_summary = []
    for (a, b), intervals in occupancy.items():
        peak = 0
        for start, end, _ in intervals:
            peak = max(peak, sum(1 for x, y, _ in intervals if x < end and y > start))
        cap = int(GRAPH[a][b].get('tracks', 1))
        section_summary.append({'from': a, 'to': b, 'track_capacity': cap, 'peak_overlapping_trains': peak, 'capacity_exceeded_in_schedule': peak > cap, 'congestion': 'Critical' if peak > cap else 'High' if peak == cap else 'Low'})
    return {'scenario': scenario, 'seed': seed, 'intensity': intensity, 'trains': rows,
            'events': events, 'section_occupancy': section_summary,
            'total_delay_min': sum(t['delay_min'] for t in rows),
            'disclaimer': 'Deterministic synthetic simulation only. Not live railway operations or a certified safety model.'}
