# RailFlow AI — Development & Verification Report

## Project status

RailFlow AI is a local synthetic railway traffic-management decision-support prototype. The backend implements a sample graph, train CRUD, delay-model estimates, route search, section-reservation scheduling, conflict screening, congestion indicators, disruption simulation, SQLite persistence and a simple Q&A endpoint.

The frontend has been rebuilt as a responsive React/TypeScript operations dashboard. The interface is organized into Overview, Train Operations, AI Predictions, Smart Scheduling, Congestion Forecast, Conflict Detection, Route Intelligence, Scenario History, Analytics and AI Assistant.

## Frontend work in this update

- Replaced the dense, single-line dashboard with a maintainable page/component structure.
- Added responsive desktop, tablet and mobile navigation, including a slide-in mobile sidebar.
- Added a consistent command-center visual system: status indicators, metric cards, tables, charts, map schematic, alert/watchlist cards, forms and modal interactions.
- Added backend connection status, last-refresh time, retry state and user-facing action feedback.
- Implemented add train form with station/route fields and server-side validation; edits/deletes use the existing SQLite-backed API.
- Added route search UI using the actual route API response fields (`stations`, `travel_minutes`, `score`).
- Connected scheduling headway control to `POST /api/optimize`.
- Connected scenario selection/intensity to `POST /api/simulate`; saved runs render from the nested SQLite history response.
- Added API proxy in Vite so local browser requests use `/api` and do not need a hardcoded browser host.
- Pinned frontend dependency versions to avoid unbounded `latest` package changes.
- Added Windows first-time setup and repeat-run scripts, macOS/Linux scripts, and Docker Compose frontend service.

## Backend implementation

- FastAPI REST API with synthetic sample data.
- NetworkX graph with 12 sample stations and 15 illustrative sections.
- scikit-learn delay baselines evaluated against generated synthetic data.
- SQLite repository persists train CRUD state and scenario run history.
- Deterministic section-reservation scheduling heuristic checks modeled track capacity and minimum headway.
- Conflict screening estimates section occupancy intervals and flags single-track overlap/headway or multi-track capacity exceedance.
- Congestion is a route-overlap density proxy, not a live occupancy forecast.

## Verification in this environment

| Check | Result |
|---|---|
| Backend pytest suite | **18 passed** |
| Python compileall | Passed |
| API integration smoke test | Passed — 12 endpoint checks (10 GET, 2 POST compute) plus train CRUD round-trip |
| Frontend stylesheet parse | Passed — PostCSS parser |
| Docker Compose YAML parse | Passed — YAML parser |
| Frontend TSX syntax transpilation | Passed (TypeScript transpile parser) |
| Frontend dependency installation | **Blocked** — npm registry DNS returned `EAI_AGAIN` |
| Frontend `tsc` type-check | Not completed — React/Vite/Recharts packages could not be installed |
| Frontend production build | Not completed — npm dependencies unavailable |
| Docker build | Not run — Docker CLI unavailable in this environment |

The source has been syntax-transpiled, but that is not a substitute for a full TypeScript type-check or Vite production build. Run `npm install` then `npm run build` inside `frontend/` on a machine with npm registry access.

## Run instructions

- Windows: double-click `setup_windows.bat` once; later use `run_windows.bat`.
- macOS/Linux: run `./setup_local.sh` once; later use `./run_local.sh`.
- Docker: run `docker compose up --build` from the project root.

Dashboard: `http://127.0.0.1:5173` (local scripts) or `http://localhost:5173` (Docker). API docs: `http://127.0.0.1:8000/docs`.

## Safety and data limitations

All included station, section, train, delay, prediction and simulation values are synthetic/illustrative. The map is schematic and not geographically authoritative. The prediction metrics do not demonstrate real operational accuracy. The optimizer is a heuristic, and conflict screening is a simplified estimate; neither models certified railway signalling/interlocking rules, block sections, route locking, platform occupation, braking curves or all railway operating constraints. No interface to live railway operations or train-control hardware exists. This prototype must never be used to dispatch or control trains.
