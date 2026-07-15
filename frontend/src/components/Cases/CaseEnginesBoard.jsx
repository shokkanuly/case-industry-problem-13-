import React, { useState, useEffect } from 'react';
import EngineDemoPanel from './EngineDemoPanel';

const API_BASE = 'http://localhost:8000';
const API_KEY = 'dev-key-001';

const STAGE_BADGE = {
  software: { label: 'Software-only', bg: 'rgba(34,211,238,0.12)', fg: '#22d3ee' },
  'hardware-later': { label: 'HW later', bg: 'rgba(245,158,11,0.12)', fg: '#f59e0b' },
  live: { label: 'Live', bg: 'rgba(16,185,129,0.12)', fg: '#10b981' },
};

/**
 * Interactive board over the /api/cases engine layer: lists all 15 case
 * engines and runs their real algorithm demos in the side panel. This is
 * the front door to the software-first core — every case is exercisable
 * with zero hardware.
 */
export default function CaseEnginesBoard() {
  const [cases, setCases] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/cases`, { headers: { 'X-API-Key': API_KEY } });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const body = await res.json();
        setCases(body.cases);
        setSelected(body.cases.find((c) => c.case_id === 13)?.case_id ?? body.cases[0]?.case_id);
      } catch (e) {
        setError(`Could not reach engine API (${e.message}). Start the backend on :8000.`);
      }
    })();
  }, []);

  const selectedDescriptor = cases.find((c) => c.case_id === selected);

  return (
    <div style={{ padding: '16px 0' }}>
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: '#fff', margin: 0 }}>Case Engine Registry</h2>
        <p style={{ fontSize: 13, color: 'var(--text-secondary, #94a3b8)', marginTop: 6, maxWidth: 720 }}>
          All 15 industrial cases share one algorithmic core exposed over <code>/api/cases</code>.
          Select a case to run its real algorithm against a synthetic scenario — no hardware required.
        </p>
      </div>

      {error && (
        <div style={{ fontSize: 12, color: 'var(--state-critical, #ef4444)', background: 'rgba(239,68,68,0.08)', padding: 12, borderRadius: 6, marginBottom: 16 }}>
          {error}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 1fr) 1.6fr', gap: 20, alignItems: 'start' }}>
        {/* Case list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {cases.map((c) => {
            const badge = STAGE_BADGE[c.stage] || STAGE_BADGE.software;
            const active = c.case_id === selected;
            return (
              <button
                key={c.case_id}
                onClick={() => setSelected(c.case_id)}
                style={{
                  textAlign: 'left',
                  padding: '10px 12px',
                  borderRadius: 8,
                  border: active ? '1px solid var(--neon-cyan, #22d3ee)' : '1px solid rgba(255,255,255,0.06)',
                  background: active ? 'rgba(34,211,238,0.08)' : 'rgba(0,0,0,0.2)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                }}
              >
                <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: 11, color: 'var(--text-dim, #64748b)', minWidth: 22 }}>
                  {String(c.case_id).padStart(2, '0')}
                </span>
                <span style={{ flex: 1, fontSize: 12, color: '#fff' }}>{c.name}</span>
                <span style={{ fontSize: 8, fontWeight: 700, textTransform: 'uppercase', padding: '2px 6px', borderRadius: 4, background: badge.bg, color: badge.fg }}>
                  {badge.label}
                </span>
              </button>
            );
          })}
        </div>

        {/* Selected engine demo */}
        <div>
          {selected != null && (
            <EngineDemoPanel caseId={selected} descriptor={selectedDescriptor} />
          )}
        </div>
      </div>
    </div>
  );
}
