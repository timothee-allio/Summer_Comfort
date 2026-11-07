# Year-Round Energy Demand & Overheating Explorer

An interactive, web-based educational exploration environment designed to demonstrate the physical principles of summer thermal comfort and overheating mitigation in buildings. 

This application bridges the gap between academic building science and general public awareness. For students and educators, it acts as an interactive environment to test design hypotheses, evaluate real-time thermal performance, and spark discussions around passive cooling. Simultaneously, the tool was explicitly created to counter the prevalent thermal misconceptions observed during the severe 2026 heatwaves. In an era where the building industry's response to climate change is of critical global importance, the app democratizes building physics, translating complex overheating dynamics into accessible common knowledge.

## Features
* **Interactive 3D Diagram:** A dynamic isometric building representation that scales and reacts in real-time to user inputs (window area, overhang depth, external shading, wall insulation).
* **Annual Simulation on Demand:** Each run simulates a full year (8,760 hours) of a single-zone house with a dynamic RC thermal model in about 1 s, with and without air conditioning.
* **Summer Comfort Indicators:** Besides cooling and heating demand, the app reports overheating hours above 28 °C and the peak operative temperature of the same house *without* air conditioning, which is where the effect of shading and ventilation shows.
* **Contour Heatmap:** A reactive 2D map of cooling demand, heating demand or overheating hours over any two design parameters, computed by multilinear interpolation of a precomputed database of 52,488 annual simulations (a few milliseconds per map).
* **Exportable Ledger:** Users can track their hypotheses and download full `.csv` ledgers of their simulation runs, including hourly sub-data for deep analysis.

## Tech Stack
* **Frontend:** [Flutter](https://flutter.dev/) (Dart) compiled to Web for barrier-free educational access.
* **Backend:** [FastAPI](https://fastapi.tiangolo.com/) (Python) serving single simulations and heatmaps.
* **Physics Engine:** Custom 3R2C RC-network thermal simulation engine solving implicit backward Euler integrations (Made with Claude), in `backend/building_sim.py`.

## How the heatmap data is produced
`backend/generate_database.py` simulates every point of the grid defined in `backend/app_grid.py` (9 values for each of wall R-value, window area, overhang depth and night ventilation, with and without external shading) for the four weather cases (Paris 2050 / 2090, typical / heat-wave year), with and without air conditioning. The results are stored in `backend/simulation_database.json`, which the API loads at startup and interpolates.

If you change the engine or the grid, regenerate the database (it uses all CPU cores and can be resumed if interrupted):
```
cd backend
python generate_database.py
```

## Local Setup & Installation

### Backend (Python)
1. Navigate to the `backend/` directory.
2. Create a virtual environment: `python -m venv venv`
3. Activate it (`.\venv\Scripts\Activate.ps1` on Windows) and install dependencies: `pip install -r requirements.txt`
4. Start the FastAPI server: `uvicorn main:app --reload --port 8000`
5. The interactive API documentation is available at http://127.0.0.1:8000/docs

### Frontend (Flutter)
1. Navigate to the `frontend/frontend/` directory.
2. Install dependencies: `flutter pub get`
3. Run the application in Chrome: `flutter run -d chrome` (add `--release` for full speed)

### With Docker
From the repository root: `docker compose up --build`, then open http://localhost (the API is on port 8000).

### Physics checks
`python verify.py` (from the repository root) runs steady-state, solar-geometry, control-logic and energy-balance sanity checks of the engine. It also runs automatically on GitHub for every push and pull request.

## Scientific Context
This tool was developed as part of research into gamification and e-learning tools for building science education. 

**Author:** Timothée ALLIO  
**Collaborators/Supervisors:** Hicham Johra