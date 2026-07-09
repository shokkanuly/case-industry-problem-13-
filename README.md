# Problem 13: Industrial Nervous System — PPE & Safety Compliance Digital Twin

> Live Edge Video Telemetry & AI Compliance Pipeline: Mobile/CCTV Feed ➔ YOLO + Face Recognition ➔ FastAPI Backend ➔ Real-Time React Dashboard with Gemini Reasoner

## Overview

Industrial Nervous System is a state-of-the-art computer vision platform designed to enforce safety compliance (PPE gear checks) and monitor restricted areas in industrial settings (specifically Crusher/Conveyor zones). 

It is the complete implementation of **Problem 13 (PPE & Behavior Compliance Camera)**:
- **YOLO Pipeline**: Runs real-time object detection (detecting workers, helmets, vests, and safety violations).
- **AI Face Recognition**: Uses local template correlation and OpenCV cascades to match faces from webcam or mobile uploads against the personnel database.
- **Dynamic Alerts**: Dynamically tracks worker names and roles and logs detailed incident alerts.
- **Digital Twin**: Connects telemetry statistics directly to the SQLite backend and pushes them via WebSockets to a premium React dashboard.
- **Gemini Reasoner**: Employs Gemini's vision capability to generate structured incident summaries and reports.

---

## Architecture

```
 Mobile Phone (WiFi Mode) / Webcam 
        │ (Base64 JPEG Streams)
        ▼
   FastAPI Server (localhost:8000) ────▶ SQLite Database (workers, alerts, telemetry)
        │ 
        ├─▶ 1. OpenCV Haar Cascades + Template Face Correlation (Face ID match)
        ├─▶ 2. YOLO PPE Compliance Model (Helmet, vest, geofence checks)
        ├─▶ 3. WebSocket Hub
        ▼
 React Dashboard (localhost:5174) ◀──▶ Gemini Flash API (AI Reports)
```

---

## Quick Start

### 1. Start the Backend
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Activate your virtual environment and install dependencies:
   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Run the backend server:
   ```bash
   python run.py
   ```
   The backend will start on `http://localhost:8000`.

### 2. Start the React Frontend Dashboard
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install node dependencies and start the development server:
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run dev
   ```
   The frontend dashboard will run at `http://localhost:5174`.

### 3. Connect Mobile Phone Camera as Live Feed
1. Open the dashboard in your computer browser (`http://localhost:5174`).
2. Go to the **Мониторинг** (Monitoring) tab and click the **📱 Телефон (WiFi)** source button.
3. Scan the generated QR Code with your phone, or open the link directly on your mobile device (both must be on the same local WiFi network).
4. Tap **📷 Запустить камеру телефона** on your mobile screen. Your phone is now a wireless edge camera!

---

## Key Features

1. **AI Face Recognition (Face ID)**: Go to **Персонал (БД)** tab to register employees with a photo (via file upload or webcam snapshot). The system runs template matching to identify people live.
2. **Dynamic Alerting**: Real-time alerts log the specific name, role, and infractions of any identified worker (e.g. `[Alikhan Aibek Shokanuly] CRITICAL: engineer Alikhan Aibek Shokanuly detected with missing PPE gear!`).
3. **Scrollable Modal Archive**: Displays the last 10 alerts on the dashboard card, with a "Вся история" button to view and search the full database history in a sleek modal overlay.
