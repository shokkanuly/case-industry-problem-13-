/**
 * AlertTimeline — Vertical scrolling feed of status-transition alerts.
 * Alerts display with severity colors (Critical vs. Warning).
 */
export function AlertTimeline({ alerts = [] }) {
  if (alerts.length === 0) {
    return (
      <div className="empty-state">
        <div className="icon">✓</div>
        <div className="message">NO ACTIVE ALERTS</div>
        <div className="message">All assets operating normally</div>
      </div>
    );
  }

  return (
    <div className="alert-list">
      {alerts.map((alert) => (
        <div 
          key={alert.alert_id} 
          className={`alert-item ${alert.severity === 'Critical' ? 'severity-critical' : 'severity-warning'}`}
        >
          <div className="alert-header">
            <span className="alert-device">⚠ {alert.asset_id}</span>
            <span className="alert-time">{formatTimestamp(alert.created_at)}</span>
          </div>
          <div className="alert-message">{alert.message}</div>
          <span className="alert-type">{alert.severity}</span>
        </div>
      ))}
    </div>
  );
}

function formatTimestamp(ts) {
  if (!ts) return '—';
  const date = new Date(ts * 1000);
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

