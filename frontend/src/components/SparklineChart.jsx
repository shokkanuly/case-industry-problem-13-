/**
 * SparklineChart — Pure SVG sparkline (no charting library).
 * Shows last 60 data points as a minimal line with filled area.
 */
export function SparklineChart({ data = [], accent = false, height = 40 }) {
  if (data.length < 2) return null;

  const width = 200;
  const padding = 2;
  const points = data.slice(-60);

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;

  const coords = points.map((val, i) => {
    const x = padding + (i / (points.length - 1)) * (width - padding * 2);
    const y = height - padding - ((val - min) / range) * (height - padding * 2);
    return { x, y };
  });

  const linePath = coords.map((c, i) => `${i === 0 ? 'M' : 'L'} ${c.x} ${c.y}`).join(' ');

  const areaPath = `${linePath} L ${coords[coords.length - 1].x} ${height} L ${coords[0].x} ${height} Z`;

  return (
    <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <path className="area" d={areaPath} />
      <path className={`line ${accent ? 'accent' : ''}`} d={linePath} />
    </svg>
  );
}
