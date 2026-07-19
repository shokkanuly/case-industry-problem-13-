import React, { useState, useEffect } from 'react';
import RecommendationDial from '../Shared/RecommendationDial';
import EngineDemoPanel from './EngineDemoPanel';

// Helper component for drawing SVG sparklines
function Sparkline({ data, color = 'var(--neon-cyan)', width = 100, height = 30 }) {
  if (!data || data.length === 0) return null;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min === 0 ? 1 : max - min;
  const points = data.map((val, idx) => {
    const x = (idx / (data.length - 1)) * width;
    const y = height - ((val - min) / range) * height;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width={width} height={height}>
      <polyline fill="none" stroke={color} strokeWidth="1.5" points={points} />
    </svg>
  );
}

export const CASE_RENDERERS = {
  // === CASE 01: Exploration Survey ===
  '01': ({ asset, onToggleAnomaly, isAnomalyActive }) => {
    const areaMapped = asset?.metadata?.area_mapped_pct ?? 84.5;
    const anomalies = asset?.metadata?.anomalies_flagged ?? 4;
    
    // Generate a beautiful 8x8 search matrix representing altitude/alteration
    const gridCells = Array.from({ length: 64 }, (_, idx) => {
      // Create clustered patterns based on indices to look like real geology
      const x = idx % 8;
      const y = Math.floor(idx / 8);
      const isAnomaly = (x === 3 && y === 2) || (x === 4 && y === 3) || (x === 2 && y === 5);
      const elevation = Math.sin(x / 2.0) * 12 + Math.cos(y / 1.5) * 8 + 50;
      const alteration = isAnomaly ? 85 + Math.random() * 10 : 10 + Math.random() * 20;
      return { id: idx, elevation, alteration, isAnomaly };
    });

    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: '20px' }}>
        <div className="glass-panel">
          <div className="panel-header">
            <span>🗺️ Drone Remote Sensing Prospect Heatmap</span>
            <span>Flight Grid 50x50</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(8, 1fr)', gap: '4px', background: 'rgba(0,0,0,0.3)', padding: '10px' }}>
            {gridCells.map(c => (
              <div 
                key={c.id} 
                style={{
                  aspectRatio: '1',
                  background: c.isAnomaly ? 'rgba(236,72,153,0.3)' : `rgba(0, 242, 254, ${c.alteration / 200})`,
                  border: c.isAnomaly ? '1.5px solid var(--neon-pink)' : '1px solid rgba(255,255,255,0.03)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '9px',
                  fontFamily: 'var(--font-mono)',
                  color: c.isAnomaly ? 'var(--neon-pink)' : '#7b88a8',
                  fontWeight: c.isAnomaly ? 'bold' : 'normal',
                  animation: c.isAnomaly ? 'alert-flash 1s infinite alternate' : 'none'
                }}
              >
                {c.alteration.toFixed(0)}%
              </div>
            ))}
          </div>

          <div style={{ marginTop: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '11px', fontFamily: 'var(--font-mono)' }}>
              <span>AREA MAPPED PROJECTION</span>
              <span>{areaMapped}%</span>
            </div>
            <div style={{ height: '6px', background: 'rgba(255,255,255,0.05)', overflow: 'hidden' }}>
              <div style={{ width: `${areaMapped}%`, height: '100%', background: 'var(--neon-cyan)' }}></div>
            </div>
          </div>
        </div>

        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="panel-header">Survey Diagnostics</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ background: 'rgba(0,0,0,0.2)', padding: '12px', borderLeft: '3px solid var(--neon-cyan)' }}>
              <div style={{ fontSize: '11px', color: '#7b88a8' }}>ACTIVE PROSPECT ANOMALIES</div>
              <div style={{ fontSize: '24px', fontWeight: 'bold', fontFamily: 'var(--font-mono)' }}>{anomalies} zones</div>
            </div>
            
            <div style={{ fontSize: '12px', color: '#9ca3af', lineHeight: '1.4' }}>
              Weighing remote-sensing data fusion score:<br/>
              <code>Score = Elevation*0.2 + Alteration*0.5 + Lineament*0.3</code>
            </div>

            <button 
              className={`btn-control-action ${isAnomalyActive ? 'active' : ''}`}
              onClick={() => onToggleAnomaly('dev_spec_analyzer')}
              style={{ marginTop: '10px', alignSelf: 'stretch' }}
            >
              {isAnomalyActive ? 'Reset Scan' : 'Inject Scan Anomaly'}
            </button>
          </div>
        </div>
      </div>
    );
  },

  // === CASE 02: Portable Core Analyzer ===
  '02': ({ asset, onToggleAnomaly, isAnomalyActive }) => {
    const mineral = asset?.metadata?.mineral_type ?? 'Awaiting scan';
    const confidence = asset?.metadata?.confidence ?? asset?.metadata?.copper_pct !== undefined ? 94.2 : 0;
    const grade = asset?.metadata?.copper_pct ?? 0.0;

    const tickets = [
      { id: 'SMP-304', mineral: mineral !== 'Awaiting scan' ? mineral : 'Chalcopyrite', grade: `${grade > 0 ? grade : 3.42}% Cu`, confidence: `${confidence > 0 ? confidence : 95.8}%` },
      { id: 'SMP-303', mineral: 'Bornite', grade: '2.84% Cu', confidence: '91.2%' },
      { id: 'SMP-302', mineral: 'Pyrite (Gangue)', grade: '0.12% Cu', confidence: '98.5%' }
    ];

    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: '20px' }}>
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div className="panel-header">🧪 Scanned Assay Tickets</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {tickets.map(t => (
              <div key={t.id} style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(0,242,254,0.15)', padding: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#6b7280', fontFamily: 'var(--font-mono)' }}>
                  <span>ID: {t.id}</span>
                  <span>CONF: {t.confidence}</span>
                </div>
                <div style={{ fontSize: '15px', fontWeight: 'bold', color: '#fff', marginTop: '6px' }}>{t.mineral}</div>
                <div style={{ fontSize: '13px', color: 'var(--neon-cyan)', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>Est Grade: {t.grade}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="panel-header">
            <span>📈 Laser Wavelength intensity graph</span>
            <span>Ref library: LIBS</span>
          </div>

          <div style={{ height: '180px', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.05)' }}>
            <svg viewBox="0 0 400 180" width="100%" height="100%">
              {/* Draw wavelength peaks */}
              <path 
                d="M 10 160 Q 60 150 100 80 T 180 140 T 260 40 T 320 150 T 390 160" 
                fill="none" 
                stroke="var(--neon-pink)" 
                strokeWidth="2" 
              />
              <circle cx="260" cy="40" r="4" fill="var(--neon-cyan)" />
              <text x="270" y="45" fill="var(--neon-cyan)" fontFamily="var(--font-mono)" fontSize="9px">Peak: 512nm (Cu signature)</text>
            </svg>
          </div>

          <button 
            className={`btn-control-action ${isAnomalyActive ? 'active' : ''}`}
            onClick={() => onToggleAnomaly('dev_spec_analyzer')}
            style={{ alignSelf: 'stretch' }}
          >
            {isAnomalyActive ? 'Assay Idle' : 'Trigger Core Sample Scan'}
          </button>
        </div>
      </div>
    );
  },

  // === CASE 03: Ore Grade Control ===
  '03': ({ asset, onToggleAnomaly, isAnomalyActive }) => {
    const recommended = asset?.recommended_value ?? 12.4;
    const deviation = asset?.current_deviation ?? 0.0;
    const grade = asset?.last_value ?? 4.82;

    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: '20px' }}>
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="panel-header">📊 Inline XRF Grade % on Conveyor</div>
          <div style={{ position: 'relative', height: '180px', background: 'rgba(0,0,0,0.35)', border: '1px solid rgba(0,242,254,0.1)' }}>
            {/* Target band overlay */}
            <div style={{ position: 'absolute', top: '25%', bottom: '25%', left: 0, right: 0, background: 'rgba(16,185,129,0.04)', borderTop: '1px dashed rgba(16,185,129,0.2)', borderBottom: '1px dashed rgba(16,185,129,0.2)' }}>
              <span style={{ position: 'absolute', right: 10, top: 4, fontSize: '9px', color: 'var(--state-normal)', fontFamily: 'var(--font-mono)' }}>TARGET BAND: 4.2% - 5.2%</span>
            </div>
            
            <svg viewBox="0 0 500 180" width="100%" height="100%" style={{ position: 'absolute', top: 0, left: 0 }}>
              {/* Static trend line */}
              <polyline 
                fill="none" 
                stroke="var(--neon-cyan)" 
                strokeWidth="2" 
                points={`0,100 80,110 160,80 240,120 320,90 400,105 480,${180 - ((grade - 3) / 3) * 180}`} 
              />
            </svg>
          </div>
          
          <div style={{ border: '1px solid rgba(255,255,255,0.05)', background: 'rgba(0,0,0,0.2)', padding: '12px', fontSize: '12px' }}>
            <strong>Conveyor Belt Section #2</strong>: PGNAA sensor telemetry stream active. Adjusting reagent dosage loops dynamically.
          </div>
        </div>

        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="panel-header">Reagent Dosage</div>
          <RecommendationDial 
            value={recommended} 
            min={0} 
            max={30} 
            unit=" mL/t" 
            title="Dosage recommendation" 
          />
          <button 
            className={`btn-control-action ${isAnomalyActive ? 'active' : ''}`}
            onClick={() => onToggleAnomaly('dev_ore_grade_sensor')}
            style={{ alignSelf: 'stretch' }}
          >
            {isAnomalyActive ? 'Reset Anomaly' : 'Inject Grade Deviation'}
          </button>
        </div>
      </div>
    );
  },

  // === CASE 04: Electrolysis Bath Automation ===
  '04': ({ asset, onToggleAnomaly, isAnomalyActive }) => {
    const coord = asset?.metadata?.coordinate ?? 'None';
    const tempAnomaly = asset?.metadata?.temperature_anomaly_c ?? 0.0;
    
    // Generate anode-cathode cell grid layout
    const cells = Array.from({ length: 32 }, (_, i) => {
      const isBad = (i === 11 && isAnomalyActive);
      return { id: i + 1, temp: isBad ? 98.4 : 76.5 + Math.random() * 4, isBad };
    });

    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: '20px' }}>
        <div className="glass-panel">
          <div className="panel-header">🔋 Electrolysis Cells Bath Grid</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(8, 1fr)', gap: '6px' }}>
            {cells.map(c => (
              <div 
                key={c.id} 
                style={{
                  aspectRatio: '1.2',
                  border: c.isBad ? '1.5px solid var(--state-critical)' : '1px solid rgba(0,242,254,0.15)',
                  background: c.isBad ? 'rgba(239,68,68,0.25)' : 'rgba(0,0,0,0.3)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '9px',
                  fontFamily: 'var(--font-mono)',
                  animation: c.isBad ? 'alert-flash 0.5s infinite alternate' : 'none'
                }}
              >
                <span style={{ color: c.isBad ? 'var(--state-critical)' : '#9ca3af' }}>C-{c.id}</span>
                <span style={{ fontWeight: 'bold', color: c.isBad ? '#fff' : 'var(--neon-cyan)' }}>{c.temp.toFixed(1)}°C</span>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="panel-header">Cathode Inspection Feed</div>
          
          <div style={{ flex: 1, minHeight: '140px', background: '#000', border: '1px solid var(--neon-cyan)', position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {isAnomalyActive ? (
              <div style={{ textAlign: 'center', color: 'var(--state-critical)' }}>
                <div style={{ fontSize: '14px', fontWeight: 'bold' }}>SHORT CIRCUIT DETECTED</div>
                <div style={{ fontSize: '10px', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>Cell Coordinate: {coord}</div>
              </div>
            ) : (
              <span style={{ fontSize: '11px', color: 'var(--state-normal)', fontFamily: 'var(--font-mono)' }}>CAM-04: FEED OPERATIONAL</span>
            )}
            <div style={{ position: 'absolute', top: 8, left: 8, width: 6, height: 6, borderRadius: '50%', background: 'red', animation: 'blink-node 1s infinite' }}></div>
          </div>

          <button 
            className={`btn-control-action ${isAnomalyActive ? 'active' : ''}`}
            onClick={() => onToggleAnomaly('dev_cv_shortcircuit')}
            style={{ alignSelf: 'stretch' }}
          >
            {isAnomalyActive ? 'Clear Short-Circuit' : 'Inject Short-Circuit Anomaly'}
          </button>
        </div>
      </div>
    );
  },

  // === CASE 05: Slope Stability ===
  '05': ({ asset, onToggleAnomaly, isAnomalyActive }) => {
    const rate = asset?.last_value ?? 0.12;
    
    return (
      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: '20px' }}>
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div className="panel-header">⛰️ Pit Wall Geotechnical Cross-Section</div>
          
          <div style={{ position: 'relative', height: '200px', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.05)' }}>
            <svg viewBox="0 0 400 200" width="100%" height="100%">
              {/* Geotechnical pit wall profile */}
              <path d="M 10 20 L 100 60 L 180 120 L 290 180 L 390 180" fill="none" stroke="#6b7280" strokeWidth="3" />
              {/* Nodes */}
              <circle cx="100" cy="60" r="7" fill={isAnomalyActive ? 'var(--state-critical)' : 'var(--neon-cyan)'} style={{ animation: isAnomalyActive ? 'blink-node 0.8s infinite' : 'none' }} />
              <text x="110" y="64" fill="#fff" fontFamily="var(--font-mono)" fontSize="9px">NODE-W01</text>

              <circle cx="180" cy="120" r="7" fill="var(--neon-cyan)" />
              <text x="190" y="124" fill="#fff" fontFamily="var(--font-mono)" fontSize="9px">NODE-W02</text>
            </svg>
          </div>
          
          <div style={{ fontSize: '10px', color: '#6b7280', fontStyle: 'italic', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '8px' }}>
            CAVEAT: Real slope safety systems use highly-validated commercial InSAR and geotechnical sensor arrays. This represents displacement velocity metrics only.
          </div>
        </div>

        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="panel-header">Displacement rates</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ background: 'rgba(0,0,0,0.2)', padding: '12px', borderLeft: '3px solid var(--neon-cyan)' }}>
              <div style={{ fontSize: '10px', color: '#7b88a8' }}>VELOCITY OF WALL DRIFT</div>
              <div style={{ fontSize: '20px', fontWeight: 'bold', fontFamily: 'var(--font-mono)' }}>{rate} mm/day</div>
            </div>
            <Sparkline data={isAnomalyActive ? [0.1, 0.4, 1.2, 3.8, 8.4, 14.2] : [0.1, 0.12, 0.11, 0.13, 0.12]} color={isAnomalyActive ? 'var(--state-critical)' : 'var(--neon-cyan)'} />
          </div>

          <button 
            className={`btn-control-action ${isAnomalyActive ? 'active' : ''}`}
            onClick={() => onToggleAnomaly('dev_slope_radar')}
            style={{ alignSelf: 'stretch', marginTop: 'auto' }}
          >
            {isAnomalyActive ? 'Clear Threat' : 'Inject Landslip Threat'}
          </button>
        </div>
      </div>
    );
  },

  // === CASES 6-15: live engine demos via /api/cases/{id}/demo ===
  '06': () => <EngineDemoPanel caseId={6} descriptor={{ name: 'Haul Truck Blind-Zone Safety', stage: 'hardware-later', algorithm: 'Sector classification + closing-speed time-to-collision grading' }} />,
  '07': () => <EngineDemoPanel caseId={7} descriptor={{ name: 'Vanyukov Furnace Optimization', stage: 'software', algorithm: 'Physics oxygen/mass balance + EWMA residual correction' }} />,
  '08': () => <EngineDemoPanel caseId={8} descriptor={{ name: 'Predictive Maintenance', stage: 'software', algorithm: 'FFT fault-band analysis + ISO 20816-3 zone classification' }} />,
  '09': () => <EngineDemoPanel caseId={9} descriptor={{ name: 'Balkhash Biodiversity Monitoring', stage: 'hardware-later', algorithm: 'Registration-frequency trend + Shannon diversity index' }} />,
  '10': () => <EngineDemoPanel caseId={10} descriptor={{ name: 'Underground Safety Mesh', stage: 'hardware-later', algorithm: 'Store-and-forward buffering with in-order burst replay' }} />,
  '11': () => <EngineDemoPanel caseId={11} descriptor={{ name: 'Energy Consumption Optimization', stage: 'software', algorithm: 'Greedy tariff-aware load-shift under a peak-demand cap' }} />,
  '12': () => <EngineDemoPanel caseId={12} descriptor={{ name: 'Driver Fatigue / Microsleep', stage: 'software', algorithm: 'PERCLOS (P80) + microsleep run-length detection, speed-gated' }} />,
  '13': (props) => <Case13Monitor {...props} />,
  '14': () => <EngineDemoPanel caseId={14} descriptor={{ name: 'Reversing Wagon Rear Camera', stage: 'hardware-later', algorithm: 'Proximity + motion-dwell fusion with flicker-reject filter' }} />,
  '15': () => <EngineDemoPanel caseId={15} descriptor={{ name: 'Concrete/Asphalt Core Analyzer', stage: 'hardware-later', algorithm: 'Spectral material match + SonReb NDT strength estimate' }} />,
};

function Case13Monitor({ asset, onToggleAnomaly, isAnomalyActive }) {
  const [isWebcamOn, setIsWebcamOn] = React.useState(false);
  const [inferenceTime, setInferenceTime] = React.useState(0);
  const [localDetections, setLocalDetections] = React.useState([]);
  const [stats, setStats] = React.useState({
    personCount: 0,
    activeViolations: 0,
    zoneBreaches: 0,
    compliancePct: 100,
    currentStatus: 'Normal'
  });
  const [alerts, setAlerts] = React.useState([]);
  const [errorMsg, setErrorMsg] = React.useState('');
  
  const videoRef = React.useRef(null);
  const canvasRef = React.useRef(null);
  const streamRef = React.useRef(null);
  const loopRef = React.useRef(null);
  const fileInputRef = React.useRef(null);
  
  // Fetch historical alerts for Case 13
  const fetchAlerts = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/analytics/alerts?limit=50', {
        headers: { 'X-API-Key': 'dev-key-001' }
      });
      if (response.ok) {
        const data = await response.json();
        // Filter alerts specific to haul_road_zone_b
        const filtered = data.filter(a => a.asset_id === 'haul_road_zone_b');
        setAlerts(filtered);
      }
    } catch (err) {
      console.error("Failed to fetch Case 13 alerts:", err);
    }
  };

  React.useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 4000);
    return () => clearInterval(interval);
  }, []);

  // Sync with twin asset from WebSocket when not running local feed
  React.useEffect(() => {
    if (!isWebcamOn && !videoRef.current?.src && asset) {
      setStats({
        personCount: asset.metadata?.person_count ?? 0,
        activeViolations: asset.metadata?.active_violations ?? 0,
        zoneBreaches: asset.metadata?.zone_breaches ?? 0,
        compliancePct: asset.last_value ?? 100,
        currentStatus: asset.status ?? 'Normal'
      });
    }
  }, [asset, isWebcamOn]);

  // Start webcam
  const startWebcam = async () => {
    try {
      setErrorMsg('');
      if (videoRef.current && videoRef.current.src) {
        // Clean up file video if playing
        videoRef.current.src = '';
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 }
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }
      setIsWebcamOn(true);
      startInferenceLoop();
    } catch (err) {
      setErrorMsg('Webcam access denied or unavailable. Please use file upload.');
      console.error("Webcam error:", err);
    }
  };

  // Stop webcam and loops
  const stopFeed = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
      videoRef.current.src = '';
    }
    if (loopRef.current) {
      clearInterval(loopRef.current);
      loopRef.current = null;
    }
    setIsWebcamOn(false);
    setLocalDetections([]);
    // Restore twin asset values
    if (asset) {
      setStats({
        personCount: asset.metadata?.person_count ?? 0,
        activeViolations: asset.metadata?.active_violations ?? 0,
        zoneBreaches: asset.metadata?.zone_breaches ?? 0,
        compliancePct: asset.last_value ?? 100,
        currentStatus: asset.status ?? 'Normal'
      });
    }
  };

  // Video File selection
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    stopFeed(); // Stop webcam
    setErrorMsg('');
    
    const fileUrl = URL.createObjectURL(file);
    if (videoRef.current) {
      videoRef.current.src = fileUrl;
      videoRef.current.loop = true;
      videoRef.current.play();
      setIsWebcamOn(true); // Active mode
      startInferenceLoop();
    }
  };

  // Inference Loop
  const startInferenceLoop = () => {
    if (loopRef.current) clearInterval(loopRef.current);
    
    loopRef.current = setInterval(async () => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas) return;
      if (video.paused || video.ended || video.readyState < 2) return;
      
      const ctx = canvas.getContext('2d');
      // Set resolution matching video source
      if (canvas.width !== video.videoWidth) canvas.width = video.videoWidth;
      if (canvas.height !== video.videoHeight) canvas.height = video.videoHeight;
      
      // Draw to canvas
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      
      // Send frame blob
      canvas.toBlob(async (blob) => {
        if (!blob) return;
        
        const formData = new FormData();
        formData.append('file', blob, 'frame.jpg');
        
        const start = performance.now();
        try {
          const res = await fetch('http://localhost:8000/api/telemetry/case13/inference', {
            method: 'POST',
            headers: {
              'X-API-Key': 'dev-key-001'
            },
            body: formData
          });
          
          if (res.ok) {
            const data = await res.json();
            setInferenceTime(Math.round(performance.now() - start));
            setLocalDetections(data.detections || []);
            setStats({
              personCount: data.person_count,
              activeViolations: data.active_violations,
              zoneBreaches: data.zone_breaches,
              compliancePct: data.compliance_pct,
              currentStatus: data.current_status
            });
          }
        } catch (err) {
          console.error("Frame inference failed:", err);
        }
      }, 'image/jpeg', 0.7);
    }, 400); // 2.5 FPS
  };

  React.useEffect(() => {
    return () => {
      if (loopRef.current) clearInterval(loopRef.current);
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
    };
  }, []);

  // Canvas drawing effect for rendering smooth video feed + overlay bounding boxes
  React.useEffect(() => {
    let animationId;
    const render = () => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (video && canvas && !video.paused && !video.ended) {
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        // Draw overlays
        drawOverlay(ctx, canvas.width, canvas.height);
      }
      animationId = requestAnimationFrame(render);
    };
    
    if (isWebcamOn) {
      animationId = requestAnimationFrame(render);
    }
    
    return () => cancelAnimationFrame(animationId);
  }, [isWebcamOn, localDetections, stats]);

  // Ray-casting geofence drawing
  const drawOverlay = (ctx, w, h) => {
    // Restricted crusher zone coordinates
    const polygon = [
      { x: 0.55, y: 0.15 },
      { x: 0.95, y: 0.15 },
      { x: 0.95, y: 0.85 },
      { x: 0.55, y: 0.85 }
    ];

    const hasBreach = stats.zoneBreaches > 0;

    // Draw Polygon
    ctx.strokeStyle = hasBreach ? '#ef4444' : '#f97316';
    ctx.lineWidth = 3;
    ctx.fillStyle = hasBreach ? 'rgba(239, 68, 68, 0.15)' : 'rgba(249, 115, 22, 0.05)';
    ctx.setLineDash([8, 4]);
    
    ctx.beginPath();
    ctx.moveTo(polygon[0].x * w, polygon[0].y * h);
    for (let i = 1; i < polygon.length; i++) {
      ctx.lineTo(polygon[i].x * w, polygon[i].y * h);
    }
    ctx.closePath();
    ctx.stroke();
    ctx.fill();
    ctx.setLineDash([]); // Reset dash

    // Labels
    ctx.fillStyle = hasBreach ? '#ef4444' : '#f97316';
    ctx.font = 'bold 12px monospace';
    ctx.fillText('RESTRICTED CRUSHER ZONE', polygon[0].x * w + 10, polygon[0].y * h + 22);
    
    if (hasBreach) {
      ctx.fillStyle = '#ef4444';
      ctx.fillText('⚠️ ZONE BREACH ACTIVE', polygon[0].x * w + 10, polygon[0].y * h + 38);
    }

    // Draw Detections
    localDetections.forEach(det => {
      const [x1, y1, x2, y2] = det.box;
      const color = det.color || '#10b981';
      const label = det.label;
      
      // Bounding box
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      
      // Label Background
      ctx.fillStyle = color;
      ctx.font = 'bold 10px monospace';
      const text = `${label} (${Math.round((det.conf || 0) * 100)}%)`;
      const textWidth = ctx.measureText(text).width;
      ctx.fillRect(x1 - 1, y1 - 16, textWidth + 8, 16);
      
      // Label Text
      ctx.fillStyle = '#ffffff';
      ctx.fillText(text, x1 + 3, y1 - 4);
    });
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '20px' }}>
      {/* COLUMN 1: LIVE FEED & OVERLAYS */}
      <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
        <div className="panel-header">
          <span>📹 Real-Time Safety Inspection Feed</span>
          {isWebcamOn && (
            <span style={{ fontSize: '10px', color: 'var(--state-normal)', animation: 'blink-node 1.5s infinite', fontFamily: 'var(--font-mono)' }}>
              ● LIVE (YOLO11)
            </span>
          )}
        </div>
        
        {/* Hidden video element for media stream */}
        <video 
          ref={videoRef} 
          style={{ display: 'none' }} 
          playsInline 
          muted 
        />
        
        {/* Canvas Display */}
        <div style={{ 
          position: 'relative', 
          width: '100%', 
          aspectRatio: '4/3', 
          background: '#000', 
          border: '1px solid var(--border-color)', 
          borderRadius: '4px',
          overflow: 'hidden',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          <canvas 
            ref={canvasRef} 
            style={{ width: '100%', height: '100%', objectFit: 'contain' }} 
          />
          
          {!isWebcamOn && (
            <div style={{ position: 'absolute', textAlign: 'center', color: 'var(--text-secondary)' }}>
              <div style={{ fontSize: '32px', marginBottom: '8px' }}>📷</div>
              <div style={{ fontSize: '12px', fontFamily: 'var(--font-mono)' }}>FEED INACTIVE</div>
              <div style={{ fontSize: '10px', marginTop: '4px' }}>Start Webcam or upload a test video to begin.</div>
            </div>
          )}
          
          {errorMsg && (
            <div style={{ position: 'absolute', top: 12, left: 12, right: 12, padding: '10px', background: 'rgba(239,68,68,0.9)', color: '#fff', fontSize: '11px', borderRadius: '4px', textAlign: 'center' }}>
              {errorMsg}
            </div>
          )}
        </div>

        {/* Controls strip */}
        <div style={{ display: 'flex', gap: '10px', marginTop: '16px', flexWrap: 'wrap' }}>
          {!isWebcamOn ? (
            <button className="btn-control-action active" onClick={startWebcam}>
              🔌 Connect Webcam Feed
            </button>
          ) : (
            <button className="btn-control-action" onClick={stopFeed} style={{ borderColor: 'var(--state-critical)', color: 'var(--state-critical)' }}>
              🔌 Disconnect Feed
            </button>
          )}

          <button className="btn-control-action" onClick={() => fileInputRef.current?.click()}>
            📁 Upload Demo Video
          </button>
          
          <input 
            type="file" 
            ref={fileInputRef} 
            style={{ display: 'none' }} 
            accept="video/*,image/*" 
            onChange={handleFileChange} 
          />

          {isWebcamOn && (
            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
              <span>Latency: <strong style={{ color: '#fff' }}>{inferenceTime}ms</strong></span>
              <span>Model: <strong style={{ color: 'var(--neon-cyan)' }}>YOLO11n</strong></span>
            </div>
          )}
        </div>
      </div>

      {/* COLUMN 2: COMPLIANCE STATS & ALERTS */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        
        {/* Compliance Meter */}
        <div className="glass-panel">
          <div className="panel-header">Compliance Registry Status</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', alignItems: 'center' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', borderRight: '1px solid var(--border-color)', paddingRight: '15px' }}>
              <span style={{ fontSize: '10px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>60s Rolling Rate</span>
              <div style={{ 
                fontSize: '36px', 
                fontWeight: 'bold', 
                fontFamily: 'var(--font-mono)', 
                color: stats.compliancePct >= 90 ? 'var(--state-normal)' : stats.compliancePct >= 70 ? 'var(--state-warning)' : 'var(--state-critical)',
                marginTop: '4px'
              }}>
                {stats.compliancePct}%
              </div>
              <span className={`case-badge ${stats.currentStatus.toLowerCase()}`} style={{ marginTop: '8px' }}>
                {stats.currentStatus}
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Detected Personnel:</span>
                <strong style={{ fontFamily: 'var(--font-mono)', color: '#fff' }}>{stats.personCount}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Active Violations:</span>
                <strong style={{ fontFamily: 'var(--font-mono)', color: stats.activeViolations > 0 ? 'var(--state-warning)' : '#fff' }}>
                  {stats.activeViolations}
                </strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Zone Intrusion:</span>
                <strong style={{ fontFamily: 'var(--font-mono)', color: stats.zoneBreaches > 0 ? 'var(--state-critical)' : '#fff' }}>
                  {stats.zoneBreaches > 0 ? 'BREACH ACTIVE' : 'NO INTRUSION'}
                </strong>
              </div>
            </div>
          </div>
        </div>

        {/* Model Metrics Card */}
        <div className="glass-panel">
          <div className="panel-header">YOLO11-PPE Validation Profile</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '12px' }}>
            <div style={{ background: 'rgba(0,0,0,0.2)', padding: '8px', borderRadius: '4px', textAlign: 'center' }}>
              <div style={{ fontSize: '9px', color: 'var(--text-dim)' }}>mAP@0.5</div>
              <div style={{ fontSize: '16px', fontWeight: 'bold', fontFamily: 'var(--font-mono)', color: 'var(--neon-cyan)' }}>91.5%</div>
            </div>
            <div style={{ background: 'rgba(0,0,0,0.2)', padding: '8px', borderRadius: '4px', textAlign: 'center' }}>
              <div style={{ fontSize: '9px', color: 'var(--text-dim)' }}>Precision</div>
              <div style={{ fontSize: '16px', fontWeight: 'bold', fontFamily: 'var(--font-mono)', color: 'var(--neon-cyan)' }}>92.4%</div>
            </div>
            <div style={{ background: 'rgba(0,0,0,0.2)', padding: '8px', borderRadius: '4px', textAlign: 'center' }}>
              <div style={{ fontSize: '9px', color: 'var(--text-dim)' }}>Recall</div>
              <div style={{ fontSize: '16px', fontWeight: 'bold', fontFamily: 'var(--font-mono)', color: 'var(--neon-cyan)' }}>89.1%</div>
            </div>
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text-dim)', lineHeight: '1.4' }}>
            <strong>Source Dataset:</strong> Roboflow Construction Site Safety (8K+ annotated images).<br/>
            <strong>Classes:</strong> Human, Helmet, No-Helmet, Vest.
          </div>
        </div>

        {/* Core Log Filtered */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: '140px' }}>
          <div className="panel-header">Compliance Event History</div>
          <div style={{ overflowY: 'auto', flex: 1, maxHeight: '180px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {alerts.length === 0 ? (
              <div style={{ fontSize: '10px', color: 'var(--text-dim)', textAlign: 'center', padding: '20px' }}>
                No safety events recorded.
              </div>
            ) : (
              alerts.map((a) => (
                <div key={a.alert_id} style={{ 
                  fontSize: '10px', 
                  fontFamily: 'var(--font-mono)', 
                  borderLeft: `2.5px solid ${a.severity === 'Critical' ? 'var(--state-critical)' : a.severity === 'Warning' ? 'var(--state-warning)' : 'var(--state-normal)'}`,
                  padding: '4px 0 4px 8px',
                  background: 'rgba(255,255,255,0.01)',
                  borderBottom: '1px solid rgba(255,255,255,0.02)'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-dim)' }}>
                    <span>{new Date(a.created_at * 1000).toLocaleTimeString()}</span>
                    <span style={{ color: a.severity === 'Critical' ? 'var(--state-critical)' : a.severity === 'Warning' ? 'var(--state-warning)' : 'var(--state-normal)' }}>
                      {a.severity.toUpperCase()}
                    </span>
                  </div>
                  <div style={{ color: '#fff', marginTop: '2px', lineHeight: '1.3' }}>{a.message}</div>
                </div>
              ))
            )}
          </div>
        </div>

      </div>
    </div>
  );
}

