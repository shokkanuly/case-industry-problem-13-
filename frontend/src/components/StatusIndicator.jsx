/**
 * StatusIndicator — 8px pulsing dot component
 * 3 states: online (green pulse), offline (gray static), alert (red rapid pulse)
 */
export function StatusIndicator({ status = 'offline' }) {
  return <span className={`status-dot ${status}`} />;
}
