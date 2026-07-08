import { StatusIndicator } from './StatusIndicator';

/**
 * DeviceGrid — Matrix of all registered edge devices.
 * Shows device ID, type, last value, battery, signal, and status.
 * Dims to 35% opacity when device is offline.
 */
export function DeviceGrid({ devices = [], deviceMap = {} }) {
  if (devices.length === 0) {
    return (
      <div className="empty-state">
        <div className="icon">📡</div>
        <div className="message">NO DEVICES REGISTERED</div>
        <div className="message">Start the simulator to see devices appear</div>
      </div>
    );
  }

  // Merge REST device data with live WebSocket data
  const merged = devices.map((dev) => {
    const live = deviceMap[dev.device_id];
    return {
      ...dev,
      last_value: live?.value ?? dev.last_value,
      last_unit: live?.unit ?? dev.last_unit,
      battery_v: live?.battery_v ?? dev.battery_v,
      rssi_dbm: live?.rssi_dbm ?? dev.rssi_dbm,
    };
  });

  const typeIcons = {
    motion: '🚪',
    power: '⚡',
    environment: '🌡️',
  };

  return (
    <div className="device-list">
      {merged.map((dev) => (
        <div
          key={dev.device_id}
          className={`device-card ${dev.status === 'offline' ? 'offline' : ''}`}
        >
          <StatusIndicator status={dev.status} />

          <div className="device-info">
            <span className="device-id">
              {typeIcons[dev.device_type] || '📡'} {dev.device_id}
            </span>
            <span className="device-type">{dev.device_type}</span>
          </div>

          <div className="device-meta">
            <span className="device-value">
              {dev.last_value != null ? formatValue(dev.last_value) : '—'}
              {dev.last_unit || ''}
            </span>
            <span className={`device-battery ${dev.battery_v < 2.8 ? 'low' : ''}`}>
              🔋 {dev.battery_v?.toFixed(2)}V · {dev.rssi_dbm}dBm
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function formatValue(v) {
  if (v >= 1000) return `${(v / 1000).toFixed(1)}k`;
  if (v >= 100) return Math.round(v).toString();
  return typeof v === 'number' ? v.toFixed(1) : v;
}
