# Industrial Nervous System — Production 4-Layer IIoT Digital Twin

> Live Edge Video Telemetry & AI Compliance Pipeline: Mobile/CCTV Feed ➔ YOLO + Face Recognition ➔ Decoupled Message Broker (MQTT) ➔ Ingestion Consumer ➔ DuckDB Columnar Time-Series + SQLite Relational Registry ➔ Real-Time React Dashboard & FMS/CMMS/DCS Enterprise Integrations with Gemini Reasoner

---

## Overview

Industrial Nervous System is a production-grade industrial IoT platform designed to enforce safety compliance (PPE gear checks) and monitor restricted areas in industrial settings (specifically Crusher/Conveyor zones). 

This version upgrades the system to a complete **4-Layer Industrial Architecture**:
1. **Layer 1 (Physical/Edge)**: Simulated telemetry edge sensors and live webcam or mobile phone streams sending Base64 JPEG frames.
2. **Layer 2 (Data Ingestion/Broker)**: Decoupled message broker (MQTT with local in-memory Virtual Broker fallback) decoupling signal producers from twin consumers.
3. **Layer 3 (Digital Twin Core)**: 
   * **Relational database (SQLite)** for asset registry, personnel database, alerts, and safety violations.
   * **High-frequency columnar time-series database (DuckDB/InfluxDB)** storing signal metrics (vibration, thermal, signal health) separate from relational assets.
4. **Layer 4 (Application/Integrations)**: Real-time React dashboard with automated API/data feeds into the mine's existing enterprise systems: **Fleet Management System (FMS)**, **CMMS (Maintenance Tickets)**, and **DCS/SCADA registers**.

*Detailed specifications for all 15 industrial cases and their Stage-1 software roadmap are documented in [docs/15_cases_architecture.md](docs/15_cases_architecture.md).*

---

## Architecture

```
  [ Edge Devices / Sensors / Mobile / Webcam ]
                      │
                      ▼
             FastAPI Ingestion API
                      │ (Publish)
                      ▼
           Message Broker (MQTT / Fallback Queue)
           ├── Topic: industrial/telemetry/raw
           └── Topic: industrial/alerts
                      │
                      ├─▶ [ Ingestion Subscriber Task ] ──▶ DuckDB Time-Series DB (Vibration, Thermal, Health)
                      │                                   └── SQLite Relational DB (Assets, Workers)
                      │
                      ├─▶ [ CMMS Auto Ticket Worker ] ────▶ Generate SQLite Work Orders ("Inspect conveyor B...")
                      │
                      └─▶ [ WebSocket Broadcast Hub ] ───▶ React Frontend Dashboard (Port 5174)
                                                          ├── Real-Time Telemetry & Safety Twin
                                                          └── Enterprise Integrations Tab (FMS, CMMS, SCADA)
```

---

## Quick Start

### 1. (Optional) Start Docker Infrastructure
To use a production-grade MQTT message broker (Mosquitto) and a time-series historian (InfluxDB):
```bash
docker compose up -d
```
*Note: If Docker is not running, the backend automatically falls back to an in-memory **Virtual Message Broker** (asyncio queues) and a local **DuckDB** file (`telemetry_ts.duckdb`), allowing the application to work out-of-the-box.*

### 2. Start the Backend
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Activate your virtual environment and install dependencies (use ABI compatibility environment variable if using Python 3.14+ to compile wheels):
   ```bash
   source .venv/bin/activate
   PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 pip install -r requirements.txt
   ```
3. Run the backend server:
   ```bash
   python run.py
   ```
   The backend will start on `http://localhost:8000`.

### 3. Start the React Frontend Dashboard
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install node dependencies and start the development server:
   ```bash
   npm install
   npm run dev
   ```
   The frontend dashboard will run securely at `https://localhost:5174` (requires bypassing SSL warnings for self-signed certificates in browser dev mode).

### 4. Connect Mobile Phone Camera as Live Feed
1. Open the dashboard in your computer browser (`https://localhost:5174`).
2. Go to the **Мониторинг** (Monitoring) tab and click the **📱 Телефон (WiFi)** source button.
3. Scan the generated QR Code with your phone, or open the link directly on your mobile device (both must be on the same local WiFi network).
4. Tap **📷 Запустить камеру телефона** on your mobile screen. Your phone is now a wireless edge camera!

---

## Key Features

1. **Enterprise Integrations (Layer 4)**: Navigate to the **Интеграции** (Integrations) tab to view live enterprise feeds:
   * **SCADA / DCS Gateway**: Exposes twin parameters as simulated Modbus TCP registers (4xxxx holding registers).
   * **Диспетчеризация FMS**: Issues dynamic dispatch instructions (e.g. `SLOW ZONE` or `TEMPORARY STOP`) to haul trucks depending on restricted zone safety breaches.
   * **CMMS / ТОиР**: Automatically logs maintenance tickets (e.g. `SAFETY CHECK: Critical compliance alert`) whenever a worker breaches safety rules.
2. **AI Face Recognition (Face ID)**: Go to **Персонал (БД)** tab to register employees with a photo (via file upload or webcam snapshot). The system runs template matching to identify people live.
3. **Dynamic Alerting**: Real-time alerts log the specific name, role, and infractions of any identified worker (e.g. `[Alikhan Aibek Shokanuly] CRITICAL: engineer Alikhan Aibek Shokanuly detected with missing PPE gear!`).
4. **Scrollable Modal Archive**: Displays the last 10 alerts on the dashboard card, with a "Вся история" button to view and search the full database history in a sleek modal overlay.
5. **Gemini Reasoner**: Employs Gemini's vision capability to generate structured incident summaries and reports.
6. **Case Engine Registry (all 15 cases)**: Every industrial case has a real algorithmic core implemented as a `CaseEngine` under `backend/app/cases/`, exposed over a uniform API and browsable in the **Движки** (Engines) tab. Each engine runs against a built-in synthetic scenario, so all 15 cases are exercisable end-to-end with zero hardware.

---

## Case Engine Layer (software-first core)

The heart of the software-first argument: 15 independent algorithm engines, one contract, one API. None require hardware to run — each ships a `simulate()` that generates a realistic input payload and a `compute()` that runs the actual method.

| API | Purpose |
| --- | --- |
| `GET /api/cases` | List all 15 engine descriptors (name, category, stage, algorithm). |
| `GET /api/cases/{id}` | One engine's descriptor + input schema. |
| `GET /api/cases/{id}/demo?scenario=normal\|anomaly` | Run the engine's built-in synthetic scenario end-to-end. |
| `POST /api/cases/{id}/run` | Run the engine over a caller-supplied payload (`{"payload": {...}}`). |

The real method behind each case:

| # | Case | Algorithm |
| --- | --- | --- |
| 01 | Exploration survey | Weighted multi-layer raster fusion + connected-component target extraction |
| 02 | Portable ore analyzer | Baseline-removed cosine-similarity spectral matching |
| 03 | Ore grade control | PI dosing control with dead-band + slew-rate limiting |
| 04 | Electrolysis short-circuit | Robust (MAD) z-score thermal hot-spot detection |
| 05 | Pit slope stability | **Fukuzono inverse-velocity** time-to-failure extrapolation |
| 06 | Haul-truck blind zone | Sector classification + closing-speed time-to-collision |
| 07 | Vanyukov furnace | Physics O₂/mass balance + EWMA residual correction (advisory) |
| 08 | Predictive maintenance | **FFT** fault-band analysis + **ISO 20816-3** zone classification |
| 09 | Balkhash biodiversity | Registration-frequency trend + Shannon diversity index |
| 10 | Underground mesh | Store-and-forward buffering + in-order burst replay |
| 11 | Energy optimization | Greedy tariff-aware load-shift under a peak-demand cap |
| 12 | Driver fatigue | **PERCLOS** (P80) + microsleep run-length detection, speed-gated |
| 13 | PPE & behavior | YOLO11 + InsightFace + geofence (live camera pipeline) |
| 14 | Reversing wagon camera | Proximity + motion-dwell fusion with flicker-reject filter |
| 15 | Construction core | Spectral material match + **SonReb** NDT strength estimate |

### Running the tests

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt pytest
pytest            # 111 tests: algorithm known-answer checks, engine contract, API
```
