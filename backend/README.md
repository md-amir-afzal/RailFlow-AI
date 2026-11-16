
### Phase 3 progress: conflict screening

The Conflict Detection workspace and `GET /api/conflicts?headway_min=8` endpoint screen the current synthetic timetable for estimated shared-section occupancy overlaps, single-track headway violations, and modeled multi-track capacity exceedances. The calculation uses scheduled departure plus current simulated delay and a constant average-speed traversal estimate. It is an advisory demonstration only; it does not model signalling blocks, interlocking, routesetting, platform occupation, braking curves, temporary restrictions, or certified railway rules.
