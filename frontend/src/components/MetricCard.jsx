import { SparklineChart } from './SparklineChart';

/**
 * MetricCard — Large number display with label, unit, trend arrow, and sparkline.
 * Flashes red border when value exceeds alert threshold.
 */
export function MetricCard({ label, value, unit, trend, history = [], isAlert = false }) {
  const trendArrow = trend === 'up' ? '↑' : trend === 'down' ? '↓' : '→';
  const trendClass = trend || 'flat';

  // Format large numbers
  const formatted =
    value === null || value === undefined
      ? '—'
      : typeof value === 'number'
        ? value >= 10000
          ? `${(value / 1000).toFixed(1)}k`
          : value >= 100
            ? Math.round(value).toString()
            : value.toFixed(1)
        : value;

  return (
    <div className={`metric-card ${isAlert ? 'alert-active' : ''}`}>
      <div className="label">{label}</div>
      <div className="value-row">
        <span className="big-number data-flash" key={formatted}>
          {formatted}
        </span>
        {unit && <span className="unit">{unit}</span>}
      </div>
      <div className={`trend ${trendClass}`}>{trendArrow} {trend || 'stable'}</div>
      {history.length > 1 && (
        <div className="sparkline-container">
          <SparklineChart data={history} accent={isAlert} />
        </div>
      )}
    </div>
  );
}
