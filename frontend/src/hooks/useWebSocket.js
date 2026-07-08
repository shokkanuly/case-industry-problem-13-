import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * useWebSocket — Auto-reconnecting WebSocket hook for live telemetry and Digital Twins.
 * Receives batched asset updates from the backend every 500ms.
 */
export function useWebSocket(url = 'ws://localhost:8000/ws') {
  const [isConnected, setIsConnected] = useState(false);
  const [assetMap, setAssetMap] = useState({});
  const [alerts, setAlerts] = useState([]);
  const [logs, setLogs] = useState([]);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const reconnectDelay = useRef(1000);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      reconnectDelay.current = 1000;
      ws.send('ping');
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === 'telemetry_batch' && Array.isArray(msg.data)) {
          const newAlerts = [];
          const assetUpdates = [];
          const newLogs = [];

          msg.data.forEach((item) => {
            const ts = new Date().toLocaleTimeString();

            if (item.type === 'alert') {
              newAlerts.push({
                alert_id: item.alert_id,
                asset_id: item.asset_id,
                severity: item.severity,
                message: item.message,
                created_at: item.created_at,
              });
              newLogs.push(`[${ts}] [SYSTEM ALERT] ${item.severity.toUpperCase()}: ${item.message}`);
            } else if (item.type === 'violation_description') {
              setAlerts((prev) => {
                return prev.map(a => {
                  if (a.alert_id === item.alert_id) {
                    return { ...a, message: item.description };
                  }
                  return a;
                });
              });
              newLogs.push(`[${ts}] [AI Incident Report] Gemini updated description for alert ${item.alert_id.substring(0, 10).toUpperCase()}: "${item.description}"`);
            } else if (item.type === 'asset') {
              assetUpdates.push(item);

              // Generate scrolling edge AI inference ticker log line
              const devId = item.metadata?.recommended_value !== undefined 
                ? 'dev_furnace_sensor' 
                : item.asset_id === 'electrolysis_bath_12'
                ? 'dev_cv_shortcircuit'
                : item.asset_id === 'haul_road_zone_b'
                ? 'dev_cv_safety'
                : item.asset_id === 'flotation_pump_3'
                ? 'dev_vib_flotation'
                : 'dev_spec_analyzer';

              if (item.asset_id === 'electrolysis_bath_12') {
                if (item.status === 'Critical') {
                  newLogs.push(`[${ts}] [Edge CV-Thermal] ${devId}: ⚠ SHORT-CIRCUIT ANOMALY DETECTED at ${item.metadata.coordinate}! Temperature: ${item.last_value}°C (Risk: ${item.risk_score}%)`);
                } else {
                  newLogs.push(`[${ts}] [Edge CV-Thermal] ${devId}: Thermal camera scan normal. Mean Temp: ${item.last_value}°C`);
                }
              } else if (item.asset_id === 'haul_road_zone_b') {
                if (item.status === 'Critical' || item.status === 'Warning') {
                  newLogs.push(`[${ts}] [Edge YOLOv8-PPE] ${devId}: ⚠ SAFETY VIOLATION! Worker in restricted zone without helmet/PPE.`);
                } else {
                  newLogs.push(`[${ts}] [Edge YOLOv8-PPE] ${devId}: Haul road scan complete. PPE Compliance: 100%.`);
                }
              } else if (item.asset_id === 'flotation_pump_3') {
                if (item.status === 'Critical' || item.status === 'Warning') {
                  newLogs.push(`[${ts}] [Edge SPECTRAL-AI] ${devId}: ⚠ BEARING ANOMALY DETECTED! Vibration: ${item.last_value} mm/s @ ${item.metadata.spectral_peak_hz}Hz.`);
                } else {
                  newLogs.push(`[${ts}] [Edge SPECTRAL-AI] ${devId}: Pump health normal. Vibration RMS: ${item.last_value} mm/s.`);
                }
              } else if (item.asset_id === 'vanyukov_furnace_1') {
                const dev = item.current_deviation;
                const sign = dev >= 0 ? '+' : '';
                if (item.status !== 'Normal') {
                  newLogs.push(`[${ts}] [Edge Optimizer-Twin] ${devId}: ⚠ FURNACE OPTIMIZATION DEV: ${sign}${dev}% (Actual ${item.last_value}% vs. Rec ${item.recommended_value}%). Action Required.`);
                } else {
                  newLogs.push(`[${ts}] [Edge Optimizer-Twin] ${devId}: Furnace parameters optimal (Deviation: ${sign}${dev}%).`);
                }
              } else if (item.asset_id === 'geological_core_analyzer') {
                if (item.report_ref && item.last_value > 0) {
                  newLogs.push(`[${ts}] [Edge Spectrometer] ${devId}: Geology Core Scan Complete. Copper Grade: ${item.last_value}% Cu. Class: ${item.metadata.classification || 'Sample'}`);
                } else {
                  newLogs.push(`[${ts}] [Edge Spectrometer] ${devId}: Geological Core Analyzer calibrated and idle.`);
                }
              }
            }
          });

          // Update asset map
          if (assetUpdates.length > 0) {
            setAssetMap((prev) => {
              const next = { ...prev };
              assetUpdates.forEach((a) => {
                const existing = next[a.asset_id] || { history: [] };
                // Track risk score history for sparklines
                const history = [...existing.history, a.risk_score || 0.0].slice(-30);
                next[a.asset_id] = { ...a, history };
              });
              return next;
            });
          }

          // Append new alerts (keep last 100)
          if (newAlerts.length > 0) {
            setAlerts((prev) => [...newAlerts, ...prev].slice(0, 100));
          }

          // Append new logs (keep last 150)
          if (newLogs.length > 0) {
            setLogs((prev) => [...newLogs, ...prev].slice(0, 150));
          }
        }
      } catch (err) {
        // Ignore keepalive or malformed text
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      reconnectTimer.current = setTimeout(() => {
        reconnectDelay.current = Math.min(reconnectDelay.current * 1.5, 10000);
        connect();
      }, reconnectDelay.current);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [url]);

  useEffect(() => {
    connect();

    const keepalive = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping');
      }
    }, 25000);

    return () => {
      clearInterval(keepalive);
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { isConnected, assetMap, alerts, logs };
}

