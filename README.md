# Paris Thermal Simulation

An interactive, web-based educational exploration environment designed to demonstrate the physical principles of summer thermal comfort and overheating mitigation in buildings. 

This application bridges the gap between academic building science and general public awareness. For students and educators, it acts as an interactive environment to test design hypotheses, evaluate real-time thermal performance, and spark discussions around passive cooling. Simultaneously, the tool was explicitly created to counter the prevalent thermal misconceptions observed during the severe 2026 heatwaves. In an era where the building industry's response to climate change is of critical global importance, the app democratizes building physics, translating complex overheating dynamics into accessible common knowledge.

## Features
* **Interactive 3D Diagram:** A dynamic isometric building representation that scales and reacts in real-time to user inputs (Window-to-Wall Ratio, Overhang Depth, External Shading).
* **Instantaneous Feedback:** Utilizes an offline surrogate database and constant-time $O(1)$ nearest-neighbor backend lookups to provide instant simulation results without browser timeouts.
* **Contour Heatmap:** A reactive 2D parameter-sweep visualization allowing users to map optimal combinations for cooling and heating demands.
* **Exportable Ledger:** Users can track their hypotheses and download full `.csv` ledgers of their simulation runs, including hourly sub-data for deep analysis.

## Tech Stack
* **Frontend:** [Flutter](https://flutter.dev/) (Dart) compiled to Web for barrier-free educational access.
* **Backend:** [FastAPI](https://fastapi.tiangolo.com/) (Python) for asynchronous, high-performance data serving.
* **Physics Engine:** Custom 3R2C RC-network thermal simulation engine solving implicit backward Euler integrations.

## Local Setup & Installation

### Backend (Python)
1. Navigate to the `backend/` directory.
2. Create a virtual environment: `python -m venv venv`
3. Activate the environment and install dependencies: `pip install -r requirements.txt`
4. Start the FastAPI server: `uvicorn main:app --reload --port 8000`


### Frontend (Flutter)
1. Navigate to the `frontend/` directory.
2. Install dependencies: `flutter pub get`
3. Run the application on a local web server: `flutter run -d chrome`

## Scientific Context
This tool was developed as part of research into gamification and e-learning tools for building science education. 

**Author:** Timothée ALLIO  
**Collaborators/Supervisors:** [Add Hicham Johra and others here]