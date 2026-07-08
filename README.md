# Edge Telemetry for Operational Efficiency

> End-to-end IoT telemetry pipeline: ESP32 Edge → FastAPI Backend → Brutalist Dashboard

## Architecture

```
ESP32 Devices (Simulated)        FastAPI Engine           Brutalist Dashboard
┌─────────────────────┐     ┌──────────────────────┐    ┌──────────────────┐
│  gate_1  (motion)   │────▶│  POST /api/telemetry │───▶│  Metrics Grid    │
│  meter_1 (power)    │     │  SQLite + WAL Mode   │    │  Device Registry │
│  env_1   (environ.) │     │  WebSocket /ws       │───▶│  Alert Timeline  │
└─────────────────────┘     └──────────────────────┘    └──────────────────┘
```

## Quick Start

### 1. Start the Backend
```bash
cd backend
pip3 install -r requirements.txt
python3 run.py
```
Backend runs at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

### 2. Start the Simulator
```bash
cd simulator
python3 esp32_simulator.py
```
Simulates 3 virtual edge devices posting every 2 seconds.

### 3. Start the Dashboard
```bash
cd frontend
npm install
npm run dev
```
Dashboard runs at `http://localhost:5173`.

## Data Contract

Every edge device sends this JSON payload:
```json
{
  "device_id": "gate_1",
  "device_type": "motion",
  "event": "trigger",
  "value": 1.0,
  "unit": "count",
  "timestamp": 1719901234,
  "battery_v": 3.21,
  "rssi_dbm": -67
}
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/telemetry` | Ingest a telemetry packet |
| GET | `/api/telemetry/latest` | Last N readings |
| GET | `/api/telemetry/history` | Device history |
| GET | `/api/analytics/summary` | Dashboard summary |
| GET | `/api/analytics/power` | Power hourly trend |
| GET | `/api/analytics/traffic` | Motion hourly trend |
| GET | `/api/analytics/alerts` | Recent alerts |
| GET | `/api/devices` | Device registry |
| WS | `/ws` | Real-time WebSocket stream |
| GET | `/health` | Health check |

All endpoints require `X-API-Key` header (default: `dev-key-001`).

## Project Structure

```
Startup/
├── backend/           # FastAPI telemetry engine
│   ├── app/
│   │   ├── main.py        # App factory + lifespan
│   │   ├── config.py      # Environment settings
│   │   ├── database.py    # SQLite + WAL
│   │   ├── models.py      # Pydantic schemas
│   │   ├── middleware.py   # API key auth
│   │   ├── routes/        # API endpoints
│   │   └── services/      # Business logic
│   ├── .env
│   └── run.py
├── simulator/         # Virtual ESP32 swarm
│   ├── esp32_simulator.py
│   └── config.json
├── frontend/          # Brutalist React dashboard
│   └── src/
│       ├── App.jsx
│       ├── index.css      # Design system
│       ├── components/    # UI components
│       └── hooks/         # Data hooks
└── firmware/          # Real ESP32 code (Step 5)
    └── esp32_telemetry.ino
```

## Pitch Deck: Technical Case Details (15 Hackathon Problems)

Each operational case is built on a registry-driven twin architecture, demonstrating the technical workflow required to map edge telemetry to business logic.

1. **Case 1 (Autonomous Exploration Survey)**: Synthetic terrain data represents coordinate-mapped altitudinal grids, fracturing lineaments, and multispectral alteration indices. It stands in for a drone-mounted multispectral camera and LiDAR array. The algorithm runs a weighted remote-sensing data fusion score, which is a genuine simplified technique used in geological prospecting.
2. **Case 2 (Core Sample Spectroscopy Scan)**: Synthetic spectrum peaks represent chemical composition. It stands in for a handheld laser-induced breakdown spectroscopy (LIBS) analyzer. The algorithm classifies sample mineral composition using peak matching rules, representing a genuine simplified spectroscopy classification technique. *Note: Production deployment requires physical LIBS spectrometer hardware.*
3. **Case 3 (Flotation Ore Grade Optimization)**: Synthetic ore composition represents input copper grade. It stands in for an online X-ray fluorescence (XRF) conveyor sensor. The algorithm runs a mathematical regression estimating Xanthate collector reagent demand relative to copper input grades, simulating a genuine process-control loop.
4. **Case 4 (Electrolysis Bath Short-Circuit CV)**: Synthetic thermal matrices represent temperature anomalies across cathode arrays. It stands in for a rail-mounted overhead infrared camera. The algorithm detects short circuits using coordinate deviation mapping, which is a genuine computer-vision spatial thresholding technique.
5. **Case 5 (Pit Slope Stability Monitoring)**: Synthetic displacement trends represent slow rock wall creep. It stands in for a ground-based synthetic aperture radar (GB-SAR) system. The algorithm computes displacement velocity and *acceleration*, which is the genuine signal-processing technique geologists use to predict failures, though production deployment requires long-term validation against advanced geotechnical models.
6. **Case 6 (Haul Truck Blind Zone Proximity)**: Synthetic proximity data represents distance to nearby haul obstacles. It stands in for 77GHz FMCW radar modules. The algorithm computes collision risk dynamically weighted by speed and transmission gear, illustrating a genuine active proximity alert model.
7. **Case 7 (Vanyukov Furnace Blast Regime Optimization)**: Synthetic coke and gas ratios represent smelting melt parameters. It stands in for blast air and furnace gas sensors. The algorithm calculates deviation from optimal target melting regimes, illustrating a genuine process-tuning loop.
8. **Case 8 (Flotation Machine Diagnostics)**: Synthetic vibration amplitudes represent motor harmonics. It stands in for bearing-mounted accelerometers. The algorithm checks spectral velocity peaks to isolate loose bearing frequencies, representing a genuine predictive maintenance signal-processing technique.
9. **Case 9 (Balkhash Lake Biodiversity Monitor)**: Synthetic camera events represent trail sightings. It stands in for smart cellular-connected camera traps. The algorithm monitors rolling species tallies and novelty sighting counts, simulating a genuine indicator-species ecology tracker.
10. **Case 10 (Underground Communication Mesh Status)**: Synthetic latency and packet drop rates represent tunnel wireless conditions. It stands in for mesh Wi-Fi nodes. The algorithm tracks packet delivery parameters, illustrating a genuine network-health ping monitoring tool.
11. **Case 11 (Grinding Mill Tariff Peak Optimizer)**: Synthetic power loads represent mill motor demand. It stands in for smart industrial submeters. The algorithm monitors a simulated peak time-of-day tariff schedule to advise load-shifting windows, representing a genuine peak-shaving demand-response logic.
12. **Case 12 (Driver Fatigue Microsleep Alarm)**: Synthetic blink durations represent eyelid closure times. It stands in for dashboard-mounted infrared camera systems. The algorithm calculates rolling eye-closure percentages (**PERCLOS**), which is the genuine, published scientific metric used in commercial fatigue detection systems.
13. **Case 13 (PPE & Behavior Compliance Camera)**: Synthetic pose metrics represent worker bounding box coordinates. It stands in for fixed CCTV safety feeds. The algorithm measures vest/helmet presence and restricted area breaches, showing a genuine edge YOLOv8 detection contract.
14. **Case 14 (Reversing Wagon Coupling Camera)**: Synthetic proximity ranges represent rear clearance. It stands in for wagon-mounted ultrasonic sensors. The algorithm checks obstacles inside reversing speed constraints, showing a genuine railway safety clearance logic.
15. **Case 15 (Concrete Core Spectroscopy Scanner)**: Synthetic spectral wavelengths represent material density. It stands in for a handheld asphalt/concrete spectrometer. The algorithm runs rule-based classification peaks to categorize material curing strengths, demonstrating a genuine spectroscopy validation method. *Note: Production deployment requires physical concrete scanner hardware.*

## License

Private — All rights reserved.
