import React, { useState, useEffect, useCallback } from 'react';

const API_BASE = 'http://localhost:8000';
const API_KEY = 'dev-key-001';

const STATUS_COLOR = {
  normal: 'var(--state-normal, #10b981)',
  warning: 'var(--state-warning, #f59e0b)',
  critical: 'var(--state-critical, #ef4444)',
};

const STAGE_LABEL = {
  software: 'Software-only',
  'hardware-later': 'HW later',
  live: 'Live',
};

// Tiny inline SVG sparkline for any numeric series the engine returns.
function Series({ data, color }) {
  if (!data || data.length < 2) return null;
  const w = 260, h = 48;
  const max = Math.max(...data), min = Math.min(...data);
  const range = max - min || 1;
  const pts = data
    .map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * h}`)
    .join(' ');
  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ height: 48 }}>
      <polyline fill="none" stroke={color} strokeWidth="1.5" points={pts} />
    </svg>
  );
}

function MetricRow({ label, value }) {
  let display = value;
  if (Array.isArray(value)) display = `${value.length} item(s)`;
  else if (value !== null && typeof value === 'object') display = JSON.stringify(value);
  else if (typeof value === 'boolean') display = value ? 'yes' : 'no';
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 11, padding: '3px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
      <span style={{ color: 'var(--text-secondary, #94a3b8)' }}>{label}</span>
      <strong style={{ fontFamily: 'var(--font-mono, monospace)', color: '#fff', textAlign: 'right' }}>{String(display)}</strong>
    </div>
  );
}

/**
 * Generic renderer for any of the 15 case engines. Calls the real
 * /api/cases/{id}/demo endpoint and renders the algorithm's live output —
 * no hardware, no mock data baked into the UI.
 */
export default function EngineDemoPanel({ caseId, descriptor }) {
  const [scenario, setScenario] = useState('anomaly');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [source, setSource] = useState(null);
  const [showSource, setShowSource] = useState(false);

  const toggleSource = async () => {
    if (showSource) { setShowSource(false); return; }
    if (!source || source.case_id !== caseId) {
      try {
        const res = await fetch(`${API_BASE}/api/cases/${caseId}/source`, {
          headers: { 'X-API-Key': API_KEY },
        });
        if (res.ok) setSource(await res.json());
      } catch { /* source viewer is best-effort */ }
    }
    setShowSource(true);
  };

  useEffect(() => { setShowSource(false); setSource(null); }, [caseId]);

  const runDemo = useCallback(async (sc) => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/cases/${caseId}/demo?scenario=${sc}`, {
        headers: { 'X-API-Key': API_KEY },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(`Backend unavailable (${e.message}). Start the engine server on :8000.`);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => { runDemo(scenario); }, [caseId, scenario, runDemo]);

  const result = data?.result;
  const color = result ? STATUS_COLOR[result.status] : 'var(--neon-cyan, #22d3ee)';
  const seriesKeys = result ? Object.keys(result.series || {}) : [];

  return (
    <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>⚙️ Live Engine — {descriptor?.name || `Case ${caseId}`}</span>
        <span style={{ fontSize: 9, fontFamily: 'var(--font-mono, monospace)', color: 'var(--text-dim, #64748b)' }}>
          {STAGE_LABEL[descriptor?.stage] || descriptor?.stage}
        </span>
      </div>

      {descriptor?.algorithm && (
        <div style={{ fontSize: 11, color: 'var(--text-secondary, #94a3b8)', lineHeight: 1.4 }}>
          <strong style={{ color: 'var(--neon-cyan, #22d3ee)' }}>Algorithm:</strong> {descriptor.algorithm}
        </div>
      )}

      {descriptor?.architecture_type && (
        <div style={{ fontSize: 11, color: 'var(--text-secondary, #94a3b8)', lineHeight: 1.4 }}>
          <strong style={{ color: 'var(--neon-cyan, #22d3ee)' }}>Architecture:</strong> {descriptor.architecture_type}
        </div>
      )}

      {descriptor?.why_distinct && (
        <div style={{ fontSize: 11, color: 'var(--text-dim, #64748b)', lineHeight: 1.4, fontStyle: 'italic', borderLeft: '2px solid rgba(34,211,238,0.3)', paddingLeft: 8 }}>
          {descriptor.why_distinct}
        </div>
      )}

      {descriptor?.brief?.problem && (
        <div style={{ display: 'grid', gap: 8, background: 'rgba(0,0,0,0.2)', padding: 12, borderRadius: 6 }}>
          <div style={{ fontSize: 11, lineHeight: 1.45 }}>
            <strong style={{ color: '#ef4444' }}>Problem:</strong>{' '}
            <span style={{ color: 'var(--text-secondary, #94a3b8)' }}>{descriptor.brief.problem}</span>
          </div>
          <div style={{ fontSize: 11, lineHeight: 1.45 }}>
            <strong style={{ color: '#10b981' }}>Solution:</strong>{' '}
            <span style={{ color: 'var(--text-secondary, #94a3b8)' }}>{descriptor.brief.solution}</span>
          </div>
          {descriptor.brief.stage1 && (
            <div style={{ fontSize: 11, lineHeight: 1.45 }}>
              <strong style={{ color: 'var(--neon-cyan, #22d3ee)' }}>Implemented (Stage 1):</strong>{' '}
              <span style={{ color: 'var(--text-secondary, #94a3b8)' }}>{descriptor.brief.stage1}</span>
            </div>
          )}
        </div>
      )}

      <button className="btn-control-action" onClick={toggleSource} style={{ alignSelf: 'flex-start', fontSize: 11 }}>
        {showSource ? '📄 Hide engine source' : '📄 View engine source code'}
      </button>

      {showSource && source && (
        <div style={{ background: 'rgba(0,0,0,0.35)', border: '1px solid rgba(34,211,238,0.15)', borderRadius: 6, overflow: 'hidden' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 10px', fontSize: 10, fontFamily: 'var(--font-mono, monospace)', color: 'var(--text-dim, #64748b)', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
            <span>backend/app/cases/{source.filename}</span>
            <span>{source.lines} lines · python</span>
          </div>
          <pre style={{ margin: 0, padding: 12, fontSize: 10.5, lineHeight: 1.5, maxHeight: 420, overflow: 'auto', color: '#cbd5e1', fontFamily: 'var(--font-mono, monospace)', whiteSpace: 'pre' }}>
            {source.source}
          </pre>
        </div>
      )}

      <div style={{ display: 'flex', gap: 8 }}>
        {['normal', 'anomaly'].map((sc) => (
          <button
            key={sc}
            className={`btn-control-action ${scenario === sc ? 'active' : ''}`}
            onClick={() => setScenario(sc)}
            style={{ flex: 1, fontSize: 11 }}
          >
            {sc === 'normal' ? '🟢 Normal scenario' : '🔴 Anomaly scenario'}
          </button>
        ))}
      </div>

      {loading && <div style={{ fontSize: 11, color: 'var(--text-dim, #64748b)' }}>Running engine…</div>}
      {error && (
        <div style={{ fontSize: 11, color: 'var(--state-critical, #ef4444)', background: 'rgba(239,68,68,0.08)', padding: 10, borderRadius: 4 }}>
          {error}
        </div>
      )}

      {result && !loading && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', background: 'rgba(0,0,0,0.25)', borderLeft: `3px solid ${color}`, borderRadius: 3 }}>
            <span style={{ textTransform: 'uppercase', fontSize: 10, fontWeight: 'bold', color, fontFamily: 'var(--font-mono, monospace)' }}>
              {result.status}
            </span>
            <span style={{ fontSize: 12, color: '#fff' }}>{result.headline}</span>
          </div>

          {seriesKeys.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {seriesKeys.slice(0, 2).map((k) => (
                <div key={k}>
                  <div style={{ fontSize: 9, textTransform: 'uppercase', color: 'var(--text-dim, #64748b)', fontFamily: 'var(--font-mono, monospace)' }}>{k}</div>
                  <Series data={result.series[k]} color={color} />
                </div>
              ))}
            </div>
          )}

          <div>
            <div style={{ fontSize: 9, textTransform: 'uppercase', color: 'var(--text-dim, #64748b)', marginBottom: 4 }}>Computed metrics</div>
            {Object.entries(result.metrics)
              .filter(([, v]) => typeof v !== 'object' || v === null || Array.isArray(v))
              .slice(0, 10)
              .map(([k, v]) => <MetricRow key={k} label={k} value={v} />)}
          </div>

          {result.recommendations?.length > 0 && (
            <div>
              <div style={{ fontSize: 9, textTransform: 'uppercase', color: 'var(--text-dim, #64748b)', marginBottom: 4 }}>Recommendations</div>
              {result.recommendations.map((r, i) => (
                <div key={i} style={{ fontSize: 11, color: '#cbd5e1', padding: '3px 0 3px 10px', borderLeft: `2px solid ${color}`, marginBottom: 4 }}>
                  {r}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
