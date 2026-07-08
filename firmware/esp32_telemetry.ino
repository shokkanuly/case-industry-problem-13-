/**
 * EDGE TELEMETRY — ESP32 Firmware
 * Target Board: ESP32 Dev Module (WROOM-32D)
 * 
 * Reads physical sensors and posts JSON telemetry to FastAPI backend.
 * Data contract matches the exact payload spec defined in models.py.
 * 
 * Sensors supported:
 *   - HC-SR04 Ultrasonic (motion/proximity detection)
 *   - ACS712 Current Sensor (power monitoring)
 *   - DHT22 / Thermistor (ambient temperature)
 * 
 * IMPORTANT: This firmware is deployed AFTER the software pipeline is validated.
 * The simulator (esp32_simulator.py) proves the pipeline first.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>

// ─── Configuration (Update these before deployment) ───
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* API_URL       = "http://192.168.1.100:8000/api/telemetry";
const char* API_KEY       = "dev-key-001";
const char* DEVICE_ID     = "gate_1";
const char* DEVICE_TYPE   = "motion";       // "motion", "power", or "environment"

// ─── Sensor Pins ───
#define TRIGGER_PIN  14    // HC-SR04 Trigger
#define ECHO_PIN     12    // HC-SR04 Echo
#define TEMP_PIN     34    // Thermistor ADC (ADC1)
#define POWER_PIN    35    // ACS712 ADC (ADC1)

// ─── Timing ───
const unsigned long POST_INTERVAL_MS = 2000;
unsigned long lastPost = 0;

// ─── NTP Time Sync ───
const char* NTP_SERVER = "pool.ntp.org";
bool timeSync = false;

// ─── Battery Voltage (ESP32 ADC on pin 36 with voltage divider) ───
#define BATTERY_PIN 36

void setup() {
    Serial.begin(115200);
    Serial.println("\n═══════════════════════════════════");
    Serial.println("  EDGE TELEMETRY — ESP32 Node");
    Serial.printf("  Device: %s (%s)\n", DEVICE_ID, DEVICE_TYPE);
    Serial.println("═══════════════════════════════════\n");

    // Initialize sensor pins
    pinMode(TRIGGER_PIN, OUTPUT);
    pinMode(ECHO_PIN, INPUT);
    pinMode(TEMP_PIN, INPUT);
    pinMode(POWER_PIN, INPUT);
    pinMode(BATTERY_PIN, INPUT);

    // Connect to Wi-Fi
    Serial.printf("Connecting to Wi-Fi: %s", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 40) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\nConnected! IP: %s\n", WiFi.localIP().toString().c_str());
        Serial.printf("Signal: %d dBm\n", WiFi.RSSI());

        // Attempt NTP sync (may fail — server-side timestamp fallback handles this)
        configTime(0, 0, NTP_SERVER);
        struct tm timeinfo;
        if (getLocalTime(&timeinfo, 5000)) {
            timeSync = true;
            Serial.println("NTP time synchronized.");
        } else {
            Serial.println("NTP sync failed — server will assign timestamp.");
        }
    } else {
        Serial.println("\nWi-Fi connection FAILED. Will retry in loop.");
    }
}

// ─── Sensor Reads ───

float readUltrasonicDistance() {
    digitalWrite(TRIGGER_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIGGER_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIGGER_PIN, LOW);

    long duration = pulseIn(ECHO_PIN, HIGH, 30000);
    if (duration == 0) return -1.0;
    return duration * 0.034 / 2.0;
}

float readTemperature() {
    int raw = analogRead(TEMP_PIN);
    float voltage = (raw / 4095.0) * 3.3;
    // Simple thermistor calibration curve (adjust for your sensor)
    float tempC = (voltage * 15.0) - 5.0;
    return tempC;
}

float readPowerWatts() {
    int raw = analogRead(POWER_PIN);
    float voltage = (raw / 4095.0) * 3.3;
    // ACS712 5A: 185mV/A, zero-current at Vcc/2 (1.65V for 3.3V)
    float amps = max(0.0f, (voltage - 1.65f) * 18.0f);
    return 220.0 * amps;
}

float readBatteryVoltage() {
    int raw = analogRead(BATTERY_PIN);
    // Assumes 2:1 voltage divider (max 4.2V battery → 2.1V at ADC)
    float voltage = (raw / 4095.0) * 3.3 * 2.0;
    return min(4.2f, max(0.0f, voltage));
}

int getTimestamp() {
    if (!timeSync) return 0; // Signal server to use its own time
    return (int)time(nullptr);
}

void loop() {
    // Reconnect Wi-Fi if dropped
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("Wi-Fi lost. Reconnecting...");
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
        delay(5000);
        return;
    }

    unsigned long now = millis();
    if (now - lastPost < POST_INTERVAL_MS) return;
    lastPost = now;

    // Read sensors based on device type
    float value = 0.0;
    const char* event = "reading";
    const char* unit = "";

    if (strcmp(DEVICE_TYPE, "motion") == 0) {
        float distance = readUltrasonicDistance();
        if (distance >= 0 && distance < 15.0) {
            event = "trigger";
            value = 1.0;
        } else {
            event = "clear";
            value = 0.0;
        }
        unit = "count";
    } else if (strcmp(DEVICE_TYPE, "power") == 0) {
        value = readPowerWatts();
        unit = "W";
    } else if (strcmp(DEVICE_TYPE, "environment") == 0) {
        value = readTemperature();
        unit = "°C";
    }

    float batteryV = readBatteryVoltage();
    int rssi = WiFi.RSSI();

    // Build JSON payload matching the data contract
    StaticJsonDocument<256> doc;
    doc["device_id"]   = DEVICE_ID;
    doc["device_type"] = DEVICE_TYPE;
    doc["event"]       = event;
    doc["value"]       = round(value * 10.0) / 10.0;
    doc["unit"]        = unit;
    doc["timestamp"]   = getTimestamp();  // 0 if NTP failed → server handles it
    doc["battery_v"]   = round(batteryV * 100.0) / 100.0;
    doc["rssi_dbm"]    = rssi;

    String payload;
    serializeJson(doc, payload);

    // HTTP POST to FastAPI
    HTTPClient http;
    http.begin(API_URL);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-API-Key", API_KEY);

    Serial.printf("[%lu] POST: %s\n", millis() / 1000, payload.c_str());

    int code = http.POST(payload);
    if (code > 0) {
        Serial.printf("Response: %d — %s\n", code, http.getString().c_str());
    } else {
        Serial.printf("HTTP Error: %d\n", code);
    }

    http.end();
}
