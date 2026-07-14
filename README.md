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
