import { useState, useEffect, useCallback } from 'react';

const API_BASE = 'http://localhost:8000';
const API_KEY = 'dev-key-001';

const headers = {
  'X-API-Key': API_KEY,
  'Content-Type': 'application/json',
};

/**
 * useTelemetry — REST polling hook for Digital Twin assets and analytics.
 * Fetches assets list, summaries, and alerts from backend.
 */
export function useTelemetry(pollIntervalMs = 5000) {
  const [summary, setSummary] = useState(null);
  const [assets, setAssets] = useState([]);
  const [powerTrend, setPowerTrend] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const [summaryRes, assetsRes, powerRes, alertsRes] = await Promise.all([
        fetch(`${API_BASE}/api/analytics/summary`, { headers }),
        fetch(`${API_BASE}/api/analytics/assets`, { headers }),
        fetch(`${API_BASE}/api/analytics/power?hours=24`, { headers }),
        fetch(`${API_BASE}/api/analytics/alerts?limit=50`, { headers }),
      ]);

      if (summaryRes.ok) setSummary(await summaryRes.json());
      if (assetsRes.ok) setAssets(await assetsRes.json());
      if (powerRes.ok) setPowerTrend(await powerRes.json());
      if (alertsRes.ok) setAlerts(await alertsRes.json());

      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, pollIntervalMs);
    return () => clearInterval(interval);
  }, [fetchAll, pollIntervalMs]);

  // Simulation controls trigger
  const setSimulatorOverride = async (deviceId, anomalyActive, connectionActive = true) => {
    try {
      const res = await fetch(`${API_BASE}/api/analytics/simulator/override`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          device_id: deviceId,
          anomaly_active: anomalyActive,
          connection_active: connectionActive,
        }),
      });
      if (res.ok) {
        // Trigger local refetch immediately to reflect status
        fetchAll();
        return true;
      }
    } catch (err) {
      console.error('Failed to trigger simulator override:', err);
    }
    return false;
  };

  return { summary, assets, powerTrend, alerts, isLoading, error, setSimulatorOverride, refetch: fetchAll };
}

