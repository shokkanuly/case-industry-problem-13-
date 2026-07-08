import React, { useState, useEffect, useRef } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { useTelemetry } from './hooks/useTelemetry';
import { SparklineChart } from './components/SparklineChart';
import './App.css';

export default function App() {
  const { isConnected, assetMap, alerts: wsAlerts, logs: wsLogs } = useWebSocket();
  const { summary, assets, alerts: restAlerts, setSimulatorOverride } = useTelemetry(5000);
  
  const [clockStr, setClockStr] = useState('12:00:00');
  const [isWebcamOn, setIsWebcamOn] = useState(false);
  const [inferenceTime, setInferenceTime] = useState(0);
  const [localDetections, setLocalDetections] = useState([]);
  const [stats, setStats] = useState({
    personCount: 0,
    activeViolations: 0,
    zoneBreaches: 0,
    compliancePct: 100,
    currentStatus: 'Normal'
  });
  const [errorMsg, setErrorMsg] = useState('');
  const [activeAnomalies, setActiveAnomalies] = useState({ dev_cv_safety: false });

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const loopRef = useRef(null);
  const fileInputRef = useRef(null);

  // Clock ticks every second
  useEffect(() => {
    const timer = setInterval(() => {
      const d = new Date();
      setClockStr(d.toLocaleTimeString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Merge polling data with websocket stream
  const mergedAssets = (assets || []).map((apiAsset) => {
    const wsAsset = assetMap[apiAsset.asset_id];
    return wsAsset ? { ...apiAsset, ...wsAsset } : apiAsset;
  });

  const activeAsset = mergedAssets.find(a => a.asset_id === 'haul_road_zone_b') || {
    asset_id: 'haul_road_zone_b',
    asset_name: 'PPE & Behavior Compliance Camera',
    status: 'Normal',
    risk_score: 0.0,
    last_value: 100.0,
    last_unit: '%',
    history: []
  };

  const activePersonCount = activeAsset?.metadata?.person_count ?? 0;
  const activeViolations = activeAsset?.metadata?.active_violations ?? 0;
  const activeZoneBreaches = activeAsset?.metadata?.zone_breaches ?? 0;
  const activeCompliancePct = activeAsset?.last_value ?? 100;
  const activeStatus = activeAsset?.status ?? 'Normal';

  // Sync with twin asset from WebSocket when not running local feed
  useEffect(() => {
    if (!isWebcamOn && !videoRef.current?.src) {
      setStats({
        personCount: activePersonCount,
        activeViolations: activeViolations,
        zoneBreaches: activeZoneBreaches,
        compliancePct: activeCompliancePct,
        currentStatus: activeStatus
      });
    }
  }, [activePersonCount, activeViolations, activeZoneBreaches, activeCompliancePct, activeStatus, isWebcamOn]);

  // Start webcam
  const startWebcam = async () => {
    try {
      setErrorMsg('');
      if (videoRef.current && videoRef.current.src) {
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
      setErrorMsg('Webcam access denied or unavailable. Please use video file upload.');
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
    setStats({
      personCount: activeAsset.metadata?.person_count ?? 0,
      activeViolations: activeAsset.metadata?.active_violations ?? 0,
      zoneBreaches: activeAsset.metadata?.zone_breaches ?? 0,
      compliancePct: activeAsset.last_value ?? 100,
      currentStatus: activeAsset.status ?? 'Normal'
    });
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    stopFeed();
    setErrorMsg('');
    
    const fileUrl = URL.createObjectURL(file);
    if (videoRef.current) {
      videoRef.current.src = fileUrl;
      videoRef.current.loop = true;
      videoRef.current.play();
      setIsWebcamOn(true);
      startInferenceLoop();
    }
  };

  // Inference loop posting frames to backend
  const startInferenceLoop = () => {
    if (loopRef.current) clearInterval(loopRef.current);
    
    loopRef.current = setInterval(async () => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas) return;
      if (video.paused || video.ended || video.readyState < 2) return;
      
      const ctx = canvas.getContext('2d');
      if (canvas.width !== video.videoWidth) canvas.width = video.videoWidth;
      if (canvas.height !== video.videoHeight) canvas.height = video.videoHeight;
      
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      
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
    }, 400);
  };

  useEffect(() => {
    return () => {
      if (loopRef.current) clearInterval(loopRef.current);
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
    };
  }, []);

  // Frame rendering canvas drawing
  useEffect(() => {
    let animationId;
    const render = () => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (video && canvas && !video.paused && !video.ended) {
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        drawOverlay(ctx, canvas.width, canvas.height);
      }
      animationId = requestAnimationFrame(render);
    };
    
    if (isWebcamOn) {
      animationId = requestAnimationFrame(render);
    }
    
    return () => cancelAnimationFrame(animationId);
  }, [isWebcamOn, localDetections, stats]);

  const drawOverlay = (ctx, w, h) => {
    const polygon = [
      { x: 0.55, y: 0.15 },
      { x: 0.95, y: 0.15 },
      { x: 0.95, y: 0.85 },
      { x: 0.55, y: 0.85 }
    ];

    const hasBreach = stats.zoneBreaches > 0;

    // Draw geofence perimeter
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
    ctx.setLineDash([]);

    // Geofence texts
    ctx.fillStyle = hasBreach ? '#ef4444' : '#f97316';
    ctx.font = 'bold 12px monospace';
    ctx.fillText('RESTRICTED CRUSHER ZONE', polygon[0].x * w + 10, polygon[0].y * h + 22);
    
    if (hasBreach) {
      ctx.fillStyle = '#ef4444';
      ctx.fillText('⚠️ ZONE BREACH ACTIVE', polygon[0].x * w + 10, polygon[0].y * h + 38);
    }

    // Draw YOLO11 Bounding Boxes
    localDetections.forEach(det => {
      const [x1, y1, x2, y2] = det.box;
      const color = det.color || '#10b981';
      const label = det.label;
      
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      
      ctx.fillStyle = color;
      ctx.font = 'bold 10px monospace';
      const text = `${label} (${Math.round((det.conf || 0) * 100)}%)`;
      const textWidth = ctx.measureText(text).width;
      ctx.fillRect(x1 - 1, y1 - 16, textWidth + 8, 16);
      
      ctx.fillStyle = '#ffffff';
      ctx.fillText(text, x1 + 3, y1 - 4);
    });
  };

  const handleToggleAnomaly = async () => {
    const current = activeAnomalies.dev_cv_safety;
    setActiveAnomalies({ dev_cv_safety: !current });
    await setSimulatorOverride('dev_cv_safety', !current, true);
  };

  // Filter alerts specifically for Case 13
  const safetyAlerts = [
    ...wsAlerts.filter(a => a.asset_id === 'haul_road_zone_b'),
    ...restAlerts.filter(a => a.asset_id === 'haul_road_zone_b' && !wsAlerts.some(wa => wa.alert_id === a.alert_id))
  ].slice(0, 100);

  // Status-related classes
  const isCrit = stats.zoneBreaches > 0 || stats.currentStatus === 'Critical';
  const isWarn = stats.currentStatus === 'Warning' && !isCrit;
  let statusBadgeClass = 'normal';
  if (isCrit) statusBadgeClass = 'critical';
  else if (isWarn) statusBadgeClass = 'warning';

  return (
    <div className="app-layout" style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      
      {/* Top Header Shell */}
      <header className="top-bar">
        <div className="logo-section">
          <span className="logo-icon">💠</span>
          <span className="logo-text">INDUSTRIAL NERVOUS SYSTEM</span>
          <span className="logo-sub">• Copper Value Chain Platform</span>
        </div>

        <div className="logo-mid" style={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)', fontFamily: 'var(--font-heading)', fontSize: '12px', color: 'var(--text-secondary)' }}>
          Copper Value Chain • Digital Twin Platform
        </div>

        <div className="top-bar-stats">
          <div className="status-badge">
            <span className="status-dot-blink" style={{ background: isConnected ? '#10b981' : '#ef4444' }}></span>
            <span>Pipeline live</span>
          </div>
          <div className="stat-item">
            Devices: <span>1/1</span>
          </div>
          <div className="stat-item" style={{ fontFamily: 'var(--font-mono)' }}>
            {clockStr}
          </div>
        </div>
      </header>

      {/* Main Container */}
      <div className="main-container" style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '20px', flex: 1, minHeight: 0, overflowY: 'auto' }}>
        
        {/* Value Chain Live Status Mimic Bar */}
        <div className="glass-panel" style={{ flexShrink: 0 }}>
          <div className="panel-header">
            <span>VALUE CHAIN — LIVE STATUS</span>
            <span>SYNC STATE</span>
          </div>
          
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 40px', position: 'relative' }}>
            <div style={{ position: 'absolute', left: '10%', right: '10%', top: '50%', height: '1px', background: 'rgba(255,255,255,0.06)', zIndex: 1 }}></div>
            
            {/* Exploration */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 2, textAlign: 'center' }}>
              <div className="nav-case-indicator normal" style={{ width: '10px', height: '10px', borderRadius: '50%', marginBottom: '8px' }}></div>
              <div style={{ fontFamily: 'var(--font-heading)', fontSize: '10px', fontWeight: 'bold', color: '#fff' }}>EXPLORATION</div>
              <div style={{ fontSize: '9px', color: 'var(--text-secondary)', marginTop: '4px' }}>4 assets</div>
            </div>

            {/* Processing */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 2, textAlign: 'center' }}>
              <div className="nav-case-indicator normal" style={{ width: '10px', height: '10px', borderRadius: '50%', marginBottom: '8px' }}></div>
              <div style={{ fontFamily: 'var(--font-heading)', fontSize: '10px', fontWeight: 'bold', color: '#fff' }}>PROCESSING</div>
              <div style={{ fontSize: '9px', color: 'var(--text-secondary)', marginTop: '4px' }}>2 assets</div>
            </div>

            {/* Smelting */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 2, textAlign: 'center' }}>
              <div className="nav-case-indicator normal" style={{ width: '10px', height: '10px', borderRadius: '50%', marginBottom: '8px' }}></div>
              <div style={{ fontFamily: 'var(--font-heading)', fontSize: '10px', fontWeight: 'bold', color: '#fff' }}>SMELTING</div>
              <div style={{ fontSize: '9px', color: 'var(--text-secondary)', marginTop: '4px' }}>2 assets • 1 warning</div>
            </div>

            {/* Logistics & Safety */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 2, textAlign: 'center' }}>
              <div className={`nav-case-indicator ${statusBadgeClass}`} style={{ width: '10px', height: '10px', borderRadius: '50%', marginBottom: '8px' }}></div>
              <div style={{ fontFamily: 'var(--font-heading)', fontSize: '10px', fontWeight: 'bold', color: '#fff' }}>LOGISTICS & SAFETY</div>
              <div style={{ fontSize: '9px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                6 assets {stats.zoneBreaches > 0 ? '• 1 critical' : stats.activeViolations > 0 ? '• 1 warning' : ''}
              </div>
            </div>

            {/* Maintenance */}
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 2, textAlign: 'center' }}>
              <div className="nav-case-indicator normal" style={{ width: '10px', height: '10px', borderRadius: '50%', marginBottom: '8px' }}></div>
              <div style={{ fontFamily: 'var(--font-heading)', fontSize: '10px', fontWeight: 'bold', color: '#fff' }}>MAINTENANCE</div>
              <div style={{ fontSize: '9px', color: 'var(--text-secondary)', marginTop: '4px' }}>1 asset</div>
            </div>
          </div>
        </div>

        {/* 3-Column Layout */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 1fr', gap: '16px', flex: 1, minHeight: 0 }}>
          
          {/* COLUMN 1: SELECTED TWIN (PPE live Camera feed) */}
          <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div className="panel-header">
              <span>SELECTED TWIN</span>
              <span style={{ fontSize: '10px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>CASE 13</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '16px', flex: 1, minHeight: 0, overflowY: 'auto' }}>
              
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: '700', color: '#fff', margin: 0 }}>
                    PPE & Behavior Compliance Camera
                  </h2>
                  <span style={{ fontSize: '10px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                    haul_road_zone_b • Case 13
                  </span>
                </div>
                <span className={`case-badge ${statusBadgeClass}`}>
                  {stats.zoneBreaches > 0 ? 'CRITICAL' : stats.activeViolations > 0 ? 'WARNING' : 'NORMAL'}
                </span>
              </div>

              {/* Dials Block */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', background: 'rgba(0,0,0,0.15)', padding: '12px', borderRadius: '4px' }}>
                <div>
                  <div style={{ fontSize: '9px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Risk Index</div>
                  <div style={{ 
                    fontSize: '22px', 
                    fontWeight: 'bold', 
                    color: stats.zoneBreaches > 0 ? 'var(--state-critical)' : stats.activeViolations > 0 ? 'var(--state-warning)' : '#10b981' 
                  }}>
                    {stats.zoneBreaches > 0 ? 100.0 : Math.round(100 - stats.compliancePct)}%
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '9px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>PPE Compliance</div>
                  <div style={{ fontSize: '22px', fontWeight: 'bold', color: stats.compliancePct >= 90 ? '#10b981' : stats.compliancePct >= 70 ? '#f59e0b' : '#ef4444' }}>
                    {stats.compliancePct}%
                  </div>
                </div>
              </div>

              {/* Sparkline chart */}
              <div style={{ height: '40px', background: 'rgba(0,0,0,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '4px' }}>
                {activeAsset.history && activeAsset.history.length > 0 ? (
                  <SparklineChart data={activeAsset.history} accent={activeAsset.status !== 'Normal'} height={30} />
                ) : (
                  <span style={{ fontSize: '9px', color: 'var(--text-dim)' }}>Scanning pipeline live telemetry stream</span>
                )}
              </div>

              {/* Live Webcam / Video Feed Box */}
              <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: '260px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 'bold', color: 'var(--text-secondary)' }}>📹 Live Camera Inspection Feed</span>
                  {isWebcamOn && (
                    <span style={{ fontSize: '9px', color: '#10b981', fontFamily: 'monospace' }}>● LIVE (YOLO11)</span>
                  )}
                </div>

                <video ref={videoRef} style={{ display: 'none' }} playsInline muted />
                
                <div style={{ 
                  position: 'relative', 
                  width: '100%', 
                  flex: 1,
                  background: '#000', 
                  border: '1px solid rgba(255,255,255,0.08)', 
                  borderRadius: '4px',
                  overflow: 'hidden',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <canvas ref={canvasRef} style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                  
                  {!isWebcamOn && (
                    <div style={{ position: 'absolute', textAlign: 'center', color: '#9ca3af' }}>
                      <div style={{ fontSize: '28px', marginBottom: '4px' }}>📷</div>
                      <div style={{ fontSize: '11px', fontFamily: 'monospace' }}>CAMERA STREAM INACTIVE</div>
                      <div style={{ fontSize: '9px', marginTop: '2px' }}>Start Webcam or drag-and-drop a test video to analyze.</div>
                    </div>
                  )}

                  {errorMsg && (
                    <div style={{ position: 'absolute', top: 12, left: 12, right: 12, padding: '8px', background: 'rgba(239,68,68,0.9)', color: '#fff', fontSize: '10px', borderRadius: '4px', textAlign: 'center' }}>
                      {errorMsg}
                    </div>
                  )}
                </div>

                {/* Webcam Controls */}
                <div style={{ display: 'flex', gap: '8px', marginTop: '8px', flexWrap: 'wrap' }}>
                  {!isWebcamOn ? (
                    <button className="btn-anomaly active" onClick={startWebcam} style={{ padding: '6px 12px', background: '#10b981', color: '#000', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold', fontSize: '11px' }}>
                      🔌 Connect Webcam
                    </button>
                  ) : (
                    <button className="btn-anomaly" onClick={stopFeed} style={{ padding: '6px 12px', background: 'transparent', border: '1px solid #ef4444', color: '#ef4444', borderRadius: '4px', cursor: 'pointer', fontSize: '11px' }}>
                      Disconnect Feed
                    </button>
                  )}

                  <button className="btn-anomaly" onClick={() => fileInputRef.current?.click()} style={{ padding: '6px 12px', background: 'transparent', border: '1px solid rgba(255,255,255,0.2)', color: '#fff', borderRadius: '4px', cursor: 'pointer', fontSize: '11px' }}>
                    📁 Upload Demo Video
                  </button>
                  
                  <input type="file" ref={fileInputRef} style={{ display: 'none' }} accept="video/*" onChange={handleFileChange} />

                  {isWebcamOn && (
                    <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '10px', fontFamily: 'monospace', color: '#9ca3af' }}>
                      <span>Latency: <strong style={{ color: '#fff' }}>{inferenceTime}ms</strong></span>
                      <span>Model: <strong style={{ color: '#00f2fe' }}>YOLO11n</strong></span>
                    </div>
                  )}
                </div>

              </div>

            </div>
          </div>

          {/* COLUMN 2: PROCESS OPTIMIZATION (Safety Compliance Registry & Model Profile) */}
          <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
            <div className="panel-header">
              <span>PROCESS OPTIMIZATION</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '16px', flex: 1, overflowY: 'auto' }}>
              
              {/* Compliance Registry Block */}
              <div>
                <h3 style={{ fontSize: '13px', color: '#fff', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '6px', margin: '0 0 10px 0' }}>
                  Safety Compliance Registry
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', background: 'rgba(0,0,0,0.15)', padding: '12px', borderRadius: '4px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Detected Workers:</span>
                    <strong style={{ fontFamily: 'monospace', color: '#fff' }}>{stats.personCount}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Active Violations:</span>
                    <strong style={{ fontFamily: 'monospace', color: stats.activeViolations > 0 ? 'var(--state-warning)' : '#10b981' }}>
                      {stats.activeViolations}
                    </strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Restricted Zone status:</span>
                    <strong style={{ fontFamily: 'monospace', color: stats.zoneBreaches > 0 ? 'var(--state-critical)' : '#10b981' }}>
                      {stats.zoneBreaches > 0 ? '⚠️ INTRUSION DETECTED' : 'SECURE'}
                    </strong>
                  </div>
                </div>
              </div>

              {/* Model Profile Block */}
              <div>
                <h3 style={{ fontSize: '13px', color: '#fff', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '6px', margin: '0 0 10px 0' }}>
                  YOLO11-PPE Validation Profile
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px', marginBottom: '8px' }}>
                  <div style={{ background: 'rgba(0,0,0,0.2)', padding: '6px', borderRadius: '4px', textAlign: 'center' }}>
                    <div style={{ fontSize: '8px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>mAP@0.5</div>
                    <div style={{ fontSize: '14px', fontWeight: 'bold', fontFamily: 'monospace', color: '#00f2fe', marginTop: '2px' }}>91.5%</div>
                  </div>
                  <div style={{ background: 'rgba(0,0,0,0.2)', padding: '6px', borderRadius: '4px', textAlign: 'center' }}>
                    <div style={{ fontSize: '8px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Precision</div>
                    <div style={{ fontSize: '14px', fontWeight: 'bold', fontFamily: 'monospace', color: '#00f2fe', marginTop: '2px' }}>92.4%</div>
                  </div>
                  <div style={{ background: 'rgba(0,0,0,0.2)', padding: '6px', borderRadius: '4px', textAlign: 'center' }}>
                    <div style={{ fontSize: '8px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Recall</div>
                    <div style={{ fontSize: '14px', fontWeight: 'bold', fontFamily: 'monospace', color: '#00f2fe', marginTop: '2px' }}>89.1%</div>
                  </div>
                </div>
                <div style={{ fontSize: '10px', color: 'var(--text-dim)', lineHeight: '1.4' }}>
                  Dataset: <strong>Roboflow Construction Site Safety</strong><br/>
                  Classes: <code>person</code>, <code>helmet</code>, <code>no-helmet</code>, <code>vest</code>
                </div>
              </div>

              {/* Controller Override Injector */}
              <div>
                <h3 style={{ fontSize: '13px', color: '#fff', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '6px', margin: '0 0 10px 0' }}>
                  Interactive Simulator Controller
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', background: 'rgba(255,255,255,0.02)', padding: '12px', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '4px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontSize: '11px', fontWeight: 'bold', color: '#fff' }}>Simulate Safety Violation</span>
                      <span style={{ fontSize: '9px', color: 'var(--text-dim)' }}>Injects synthetic worker PPE breach telemetry</span>
                    </div>
                    <button 
                      onClick={handleToggleAnomaly}
                      className={`btn-anomaly ${activeAnomalies.dev_cv_safety ? 'active' : ''}`}
                      style={{ fontSize: '11px', padding: '4px 10px' }}
                    >
                      {activeAnomalies.dev_cv_safety ? 'Clear' : 'Inject Anomaly'}
                    </button>
                  </div>
                </div>
              </div>

            </div>
          </div>

          {/* COLUMN 3: CORE LOG LIVE (Safety events & AI console logs) */}
          <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div className="panel-header">
              <span>CORE LOG LIVE</span>
              <span className="live-status-tag" style={{ fontSize: '9px', color: '#10b981', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span className="status-dot-blink" style={{ width: '4px', height: '4px' }}></span> LIVE
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '16px', flex: 1, minHeight: 0 }}>
              
              {/* Event Alerts History */}
              <div style={{ display: 'flex', flexDirection: 'column', height: '45%', minHeight: 0 }}>
                <span style={{ fontSize: '11px', fontWeight: 'bold', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                  ⚠️ Critical Safety Events Log
                </span>
                <div style={{ flex: 1, overflowY: 'auto', background: 'rgba(0,0,0,0.15)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '4px', padding: '8px' }}>
                  {safetyAlerts.length === 0 ? (
                    <div style={{ fontSize: '10px', color: 'var(--text-dim)', textAlign: 'center', padding: '20px' }}>
                      No safety anomalies logged.
                    </div>
                  ) : (
                    safetyAlerts.map(a => (
                      <div key={a.alert_id} style={{ 
                        fontSize: '9px', 
                        fontFamily: 'var(--font-mono)',
                        borderLeft: `2.5px solid ${a.severity === 'Critical' ? 'var(--state-critical)' : 'var(--state-warning)'}`,
                        paddingLeft: '6px',
                        marginBottom: '8px'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-dim)' }}>
                          <span>{new Date(a.created_at * 1000).toLocaleTimeString()}</span>
                          <span style={{ color: a.severity === 'Critical' ? 'var(--state-critical)' : 'var(--state-warning)' }}>
                            {a.severity.toUpperCase()}
                          </span>
                        </div>
                        <div style={{ color: '#fff', marginTop: '2px' }}>{a.message}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Edge AI logs ticker */}
              <div style={{ display: 'flex', flexDirection: 'column', height: '55%', minHeight: 0 }}>
                <span style={{ fontSize: '11px', fontWeight: 'bold', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                  💻 Edge AI Model Inference Stream (Console)
                </span>
                <div style={{ 
                  flex: 1, 
                  overflowY: 'auto', 
                  background: '#040605', 
                  border: '1px solid rgba(255,255,255,0.05)', 
                  borderRadius: '4px', 
                  padding: '8px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '9px',
                  color: '#8b949e',
                  lineHeight: '1.4'
                }}>
                  {wsLogs.length === 0 ? (
                    <div style={{ color: 'var(--text-dim)', textAlign: 'center', padding: '20px' }}>
                      Awaiting live AI inference logs...
                    </div>
                  ) : (
                    wsLogs.map((log, index) => (
                      <div key={index} style={{ marginBottom: '4px', borderBottom: '1px solid rgba(255,255,255,0.01)', paddingBottom: '2px' }}>
                        {log}
                      </div>
                    ))
                  )}
                </div>
              </div>

            </div>
          </div>

        </div>

      </div>

    </div>
  );
}
