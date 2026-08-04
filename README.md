# Paris Summer Comfort Digital Twin

A local, interactive thermal model of a single-zone Paris dwelling under future
climate scenarios. The dashboard lets a user change four building parameters
and runs a full-year (8,760-hour) dynamic simulation to estimate cooling demand
and overheating.

The application has two independently started parts:

- `frontend/frontend/`: Flutter web dashboard.
- `backend/`: FastAPI API, weather files, and the NumPy-based physics engine.

For the full architecture, data flow, API contract, model assumptions, and
developer instructions, see [APP_DOCUMENTATION.md](APP_DOCUMENTATION.md).

## Run locally

Start the API from the backend directory so its relative weather-file paths
resolve correctly:

```powershell
Set-Location backend
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```

In another terminal, start the Flutter web app:

```powershell
Set-Location frontend\frontend
flutter run -d chrome
```

The frontend is currently configured to call `http://127.0.0.1:8000`.

## Repository utilities

The root-level scripts are research/batch utilities rather than part of the
dashboard. `run_simulation.py`, `run_scenarios.py`, and `verify.py` currently
expect a root-level `weather/` directory, which is not present in this
checkout; see the notes in the full documentation before using them.
