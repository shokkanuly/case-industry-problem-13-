import React, { useState, useEffect, useRef } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { useTelemetry } from './hooks/useTelemetry';

// Inline Icons to avoid installing extra packages
const IconZap = () => (
  <svg className="h-5 w-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
  </svg>
);

const IconHome = () => (
  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
  </svg>
);

const IconDashboard = () => (
  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
  </svg>
);

const IconModules = () => (
  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
  </svg>
);

const IconSearch = ({ className }) => (
  <svg className={className || "h-4 w-4"} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
  </svg>
);

const IconPlay = ({ className }) => (
  <svg className={className || "h-4 w-4"} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
  </svg>
);

const IconPause = ({ className }) => (
  <svg className={className || "h-4 w-4"} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const IconAlert = ({ className }) => (
  <svg className={className || "h-4 w-4"} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
  </svg>
);

const IconCheck = ({ className }) => (
  <svg className={className || "h-4 w-4"} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
  </svg>
);

const IconRefresh = ({ className }) => (
  <svg className={className || "h-4 w-4"} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89H18" />
  </svg>
);

const IconVideo = ({ className }) => (
  <svg className={className || "h-4 w-4"} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
  </svg>
);

export default function App() {
  const [activeTab, setActiveTab] = useState('home');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [clockStr, setClockStr] = useState('12:00:00');

  // WebSocket and HTTP database hooks
  const { isConnected, assetMap, alerts: wsAlerts } = useWebSocket();
  const { summary, assets, alerts: restAlerts, setSimulatorOverride } = useTelemetry(5000);

  // Video and Canvas states
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
  const [alertSearch, setAlertSearch] = useState('');

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const loopRef = useRef(null);
  const fileInputRef = useRef(null);

  // Time ticker
  useEffect(() => {
    const timer = setInterval(() => {
      const d = new Date();
      setClockStr(d.toLocaleTimeString('ru-RU'));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Merge polling and websocket twin metrics
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

  // Sync twin metrics when local feed is off
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

  // Webcam Start/Stop methods
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
      setErrorMsg('Доступ к веб-камере заблокирован. Пожалуйста, загрузите демонстрационное видео.');
      console.error("Webcam error:", err);
    }
  };

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
            headers: { 'X-API-Key': 'dev-key-001' },
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

  // Canvas drawing loop
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
    
    // Restricted Zone Geofence boundary
    ctx.strokeStyle = hasBreach ? 'rgb(212, 17, 1)' : 'rgb(181, 135, 0)';
    ctx.lineWidth = 3;
    ctx.fillStyle = hasBreach ? 'rgba(212, 17, 1, 0.15)' : 'rgba(181, 135, 0, 0.05)';
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

    ctx.fillStyle = hasBreach ? 'rgb(212, 17, 1)' : 'rgb(181, 135, 0)';
    ctx.font = 'bold 12px monospace';
    ctx.fillText('Restricted Crusher Zone', polygon[0].x * w + 10, polygon[0].y * h + 22);
    if (hasBreach) {
      ctx.fillStyle = 'rgb(212, 17, 1)';
      ctx.fillText('⚠️ ZONE BREACH ACTIVE', polygon[0].x * w + 10, polygon[0].y * h + 38);
    }

    // Worker Bounding Boxes
    localDetections.forEach(det => {
      const [x1, y1, x2, y2] = det.box;
      const color = det.color || 'rgb(0, 138, 34)';
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

  // Compile alerts list (live database alerts + reference mocks)
  const dbAlerts = [
    ...wsAlerts.filter(a => a.asset_id === 'haul_road_zone_b'),
    ...restAlerts.filter(a => a.asset_id === 'haul_road_zone_b' && !wsAlerts.some(wa => wa.alert_id === a.alert_id))
  ];

  const mockAlerts = [
    { id: "ALT-001", type: "no_helmet", worker: "Иванов А.С.", zone: "Участок №3 — Дробление", timestamp: "2026-07-08 14:23:11", severity: "critical" },
    { id: "ALT-002", type: "no_vest", worker: "Петров В.Н.", zone: "Участок №7 — Конвейер", timestamp: "2026-07-08 14:18:44", severity: "warning" },
    { id: "ALT-003", type: "geo_zone", worker: "Сидоров Д.М.", zone: "Запретная зона А-12", timestamp: "2026-07-08 14:12:05", severity: "critical" },
    { id: "ALT-004", type: "no_helmet", worker: "Кузнецов И.П.", zone: "Участок №5 — Плавка", timestamp: "2026-07-08 13:58:30", severity: "warning" },
    { id: "ALT-005", type: "no_vest", worker: "Смирнов А.В.", zone: "Участок №2 — Сортировка", timestamp: "2026-07-08 13:45:12", severity: "info" }
  ];

  const mappedDbAlerts = dbAlerts.map(a => {
    const isCritical = a.message.toLowerCase().includes('critical') || a.message.toLowerCase().includes('danger');
    const isWarning = a.message.toLowerCase().includes('warning') || a.message.toLowerCase().includes('vest') || a.message.toLowerCase().includes('helmet');
    return {
      id: a.alert_id.substring(0, 10).toUpperCase(),
      type: a.message.toLowerCase().includes('vest') ? "no_vest" : a.message.toLowerCase().includes('helmet') ? "no_helmet" : "geo_zone",
      worker: "Оператор Смены",
      zone: "Участок №3 — Дробление",
      timestamp: new Date(a.created_at * 1000).toLocaleString('ru-RU'),
      severity: isCritical ? "critical" : isWarning ? "warning" : "info"
    };
  });

  const allAlerts = [...mappedDbAlerts, ...mockAlerts].filter(item => {
    const query = alertSearch.toLowerCase();
    return item.worker.toLowerCase().includes(query) ||
           item.zone.toLowerCase().includes(query) ||
           item.id.toLowerCase().includes(query);
  });

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      
      {/* HEADER SECTION (100% replica of uN) */}
      <header className="fixed top-0 left-0 right-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          
          {/* Logo */}
          <div onClick={() => setActiveTab('home')} className="flex items-center gap-3 group cursor-pointer">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 ring-1 ring-primary/30 transition group-hover:bg-primary/20">
              <IconZap />
            </div>
            <div className="hidden sm:block">
              <span className="text-sm font-semibold tracking-tight text-foreground">
                Industrial<span className="text-primary">Nervous</span>System
              </span>
              <span className="ml-2 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                v2.0
              </span>
            </div>
          </div>

          {/* Navigation links */}
          <nav className="hidden items-center gap-1 md:flex">
            {[
              { id: 'home', label: 'Главная' },
              { id: 'dashboard', label: 'Мониторинг' },
              { id: 'modules', label: 'Модули' },
              { id: 'about', label: 'О платформе' }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`relative rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  activeTab === tab.id ? 'text-primary' : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {activeTab === tab.id && (
                  <span className="absolute inset-0 rounded-md bg-primary/10 ring-1 ring-primary/20"></span>
                )}
                <span className="relative z-10">{tab.label}</span>
              </button>
            ))}
          </nav>

          {/* Clock & Status */}
          <div className="flex items-center gap-3">
            <div className="hidden lg:flex items-center gap-2 text-xs font-mono text-muted-foreground">
              <span>{clockStr}</span>
              <span className="h-3 w-px bg-border/50"></span>
              <span className={isConnected ? "text-success" : "text-destructive"}>
                {isConnected ? "Онлайн" : "Офлайн"}
              </span>
            </div>
            {/* Hamburger button for mobile */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:text-foreground md:hidden"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>
        </div>

        {/* Mobile dropdown */}
        {mobileMenuOpen && (
          <div className="overflow-hidden border-t border-border/50 bg-background/95 backdrop-blur-xl md:hidden">
            <nav className="flex flex-col gap-1 px-4 pb-4 pt-2">
              {[
                { id: 'home', label: 'Главная' },
                { id: 'dashboard', label: 'Мониторинг' },
                { id: 'modules', label: 'Модули' },
                { id: 'about', label: 'О платформе' }
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => {
                    setActiveTab(tab.id);
                    setMobileMenuOpen(false);
                  }}
                  className={`text-left rounded-md px-3 py-2.5 text-sm font-medium transition-colors ${
                    activeTab === tab.id ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>
        )}
      </header>

      {/* MAIN CONTAINER CONTENT VIEWPORTS */}
      <main className="flex-1 mt-16">

        {/* PAGE 1: HOME (100% replica of yN) */}
        {activeTab === 'home' && (
          <div className="min-h-screen">
            {/* Hero Banner Section */}
            <section className="relative flex min-h-screen items-center overflow-hidden">
              <div className="absolute inset-0">
                <div className="absolute inset-0 bg-gradient-to-b from-background/60 via-background/80 to-background z-10" />
                <div className="absolute inset-0 bg-gradient-to-r from-primary/5 via-transparent to-primary/5 z-10" />
                <div className="absolute inset-0 scan-line z-10" />
                <img
                  src="https://placehold.co/1200x800/0a0a1a/00a1c8?text=Industrial+Nervous+System"
                  alt="Industrial Plant"
                  className="h-full w-full object-cover"
                />
              </div>

              <div className="relative z-20 mx-auto max-w-7xl px-4 pt-24 pb-20 sm:px-6 lg:px-8">
                <div className="max-w-3xl">
                  <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-xs font-medium text-primary">
                    <IconZap />
                    <span>Хакатон — полностью реализован Кейс 13</span>
                  </div>
                  <h1 className="text-4xl font-bold leading-tight tracking-tight sm:text-5xl lg:text-6xl text-white">
                    Единая платформа{" "}
                    <span className="bg-gradient-to-r from-primary via-primary/80 to-primary/60 bg-clip-text text-transparent">
                      цифровых двойников
                    </span>{" "}
                    для промышленности
                  </h1>
                  <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground">
                    Industrial Nervous System объединяет данные датчиков и камер в стандартизированную модель Digital Twin. Вместо 15 разрозненных инструментов — единая edge-to-cloud архитектура с ИИ на борту.
                  </p>
                  
                  <div className="mt-8 flex flex-wrap gap-4">
                    <button
                      onClick={() => setActiveTab('dashboard')}
                      className="inline-flex items-center gap-2 rounded-lg bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground transition hover:bg-primary/90 glow-blue"
                    >
                      <IconDashboard />
                      <span>Открыть мониторинг</span>
                    </button>
                    <button
                      onClick={() => setActiveTab('modules')}
                      className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-6 py-3 text-sm font-medium text-foreground transition hover:bg-accent/10"
                    >
                      <IconModules />
                      <span>Все модули</span>
                    </button>
                  </div>
                </div>
              </div>
              <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-background to-transparent z-10" />
            </section>

            {/* Platform Stats Panels */}
            <section className="relative -mt-20 z-20">
              <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-border/50 bg-border/50 md:grid-cols-4">
                  {[
                    { value: "15", label: "Индустриальных кейсов", suffix: "" },
                    { value: "99.2", label: "Точность детекции", suffix: "%" },
                    { value: "<500", label: "Задержка алерта", suffix: "мс" },
                    { value: "24/7", label: "Непрерывный мониторинг", suffix: "" }
                  ].map(stat => (
                    <div key={stat.label} className="flex flex-col items-center justify-center bg-card px-4 py-8 text-center">
                      <span className="text-3xl font-bold tracking-tight text-primary sm:text-4xl">
                        {stat.value}
                        <span className="text-lg font-medium text-muted-foreground">{stat.suffix}</span>
                      </span>
                      <span className="mt-1 text-xs font-medium text-muted-foreground">{stat.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            {/* Capabilities grid section */}
            <section className="py-24">
              <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                <div className="text-center mb-16">
                  <h2 className="text-3xl font-bold tracking-tight sm:text-4xl text-white">Возможности платформы</h2>
                  <p className="mt-4 text-muted-foreground">От компьютерного зрения до единого реестра цифровых двойников</p>
                </div>
                
                <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                  {[
                    { title: "Компьютерное зрение", desc: "Дообученная YOLO на реальном датасете детектирует каски, жилеты и нарушение геозон в реальном времени." },
                    { title: "Мгновенные алерты", desc: "При обнаружении нарушения — уведомление диспетчеру за < 500 мс с кадром и метаданными." },
                    { title: "Дашборд комплаенса", desc: "Живая статистика по СИЗ, история нарушений, рейтинг смен и динамика по участкам." },
                    { title: "Digital Twin Registry", desc: "Единый реестр цифровых двойников — стандартизированная модель для всех 15 кейсов." },
                    { title: "Edge-to-Cloud", desc: "Обработка на периферии (NVIDIA Jetson), агрегация в облаке. Работает при потере связи." },
                    { title: "Модульная архитектура", desc: "15 готовых модулей подключаются без изменения ядра — от разведки до обслуживания." }
                  ].map((cap, i) => (
                    <div key={i} className="group rounded-xl border border-border/50 bg-card p-6 transition hover:border-primary/30 hover:shadow-lg hover:shadow-primary/5">
                      <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 ring-1 ring-primary/20 transition group-hover:bg-primary/20">
                        <IconZap />
                      </div>
                      <h3 className="text-base font-semibold text-white">{cap.title}</h3>
                      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{cap.desc}</p>
                    </div>
                  ))}
                </div>
              </div>
            </section>

            {/* Modules overview section */}
            <section className="py-24 border-t border-border/50">
              <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
                <div className="flex items-end justify-between mb-12">
                  <div>
                    <h2 className="text-3xl font-bold tracking-tight sm:text-4xl text-white">15 модулей в единой архитектуре</h2>
                    <p className="mt-4 text-muted-foreground">Все кейсы индустриального трека — готовые к подключению модули</p>
                  </div>
                  <button
                    onClick={() => setActiveTab('modules')}
                    className="hidden sm:inline-flex items-center gap-1 text-sm font-medium text-primary transition hover:text-primary/80"
                  >
                    <span>Все модули</span>
                    <span>→</span>
                  </button>
                </div>

                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {[
                    { label: "СИЗ и опасное поведение", status: "active", color: "text-success" },
                    { label: "Контроль доступа", status: "ready", color: "text-primary" },
                    { label: "Мониторинг оборудования", status: "ready", color: "text-primary" },
                    { label: "Телеметрия транспорта", status: "ready", color: "text-primary" },
                    { label: "Управление обогащением", status: "ready", color: "text-primary" },
                    { label: "Предиктивное обслуживание", status: "ready", color: "text-primary" }
                  ].map((mod, idx) => (
                    <div key={idx} className="flex items-center gap-4 rounded-xl border border-border/50 bg-card p-4 transition hover:border-primary/20">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/5 ring-1 ring-primary/10">
                        <IconZap />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate text-white">{mod.label}</p>
                        <span className={`inline-flex items-center gap-1 text-xs font-medium ${mod.status === "active" ? "text-success" : "text-muted-foreground"}`}>
                          <span className={`inline-block h-1.5 w-1.5 rounded-full ${mod.status === "active" ? "bg-success" : "bg-muted-foreground"}`}></span>
                          {mod.status === "active" ? "Реализован" : "Готов к подключению"}
                        </span>
                      </div>
                      {mod.status === "active" && (
                        <span className="shrink-0 rounded-full bg-success/10 px-2 py-0.5 text-[10px] font-medium text-success">LIVE</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </section>
          </div>
        )}

        {/* PAGE 2: MONITORING / DASHBOARD (100% replica of EN) */}
        {activeTab === 'dashboard' && (
          <div className="min-h-screen pt-4 pb-12">
            <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
              
              {/* Header Title Grid */}
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-3">
                    <h1 className="text-2xl font-bold tracking-tight sm:text-3xl text-white">Мониторинг СИЗ</h1>
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-success/10 px-3 py-1 text-xs font-medium text-success">
                      <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-success"></span>
                      <span>В РЕАЛЬНОМ ВРЕМЕНИ</span>
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Компьютерное зрение — детекция касок, жилетов и нарушений геозон (Crusher Safety Camera)
                  </p>
                </div>
                
                {/* Control Action Tools */}
                <div className="flex items-center gap-3">
                  <button
                    onClick={isWebcamOn ? stopFeed : startWebcam}
                    className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition ${
                      isWebcamOn ? "border-success/30 bg-success/5 text-success" : "border-border bg-card text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    <IconVideo className={isWebcamOn ? "animate-pulse" : ""} />
                    {isWebcamOn ? "Отключить камеру" : "Запустить камеру"}
                  </button>
                  
                  {/* File Upload Input helper */}
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground transition"
                  >
                    <span>Загрузить видео</span>
                  </button>
                  <input
                    type="file"
                    ref={fileInputRef}
                    accept="video/*"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                </div>
              </div>

              {/* Grid 4 Stats Gauges */}
              <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  { label: "Каски", value: stats.compliancePct >= 99 ? 99.4 : stats.compliancePct > 90 ? stats.compliancePct - 0.8 : 94.2, change: "+2.1%", isPos: true },
                  { label: "Жилеты", value: stats.compliancePct >= 99 ? 98.9 : stats.compliancePct > 90 ? stats.compliancePct - 1.4 : 91.8, change: "-0.5%", isPos: false },
                  { label: "Геозоны", value: stats.zoneBreaches > 0 ? 0.0 : 100.0, change: "+1.3%", isPos: true },
                  { label: "Общий комплаенс", value: stats.compliancePct, change: "+0.8%", isPos: true }
                ].map((gauge, gIdx) => (
                  <div key={gIdx} className="rounded-xl border border-border/50 bg-card p-5 transition hover:border-primary/20">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-muted-foreground">{gauge.label}</span>
                      <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${gauge.isPos ? "text-success" : "text-destructive"}`}>
                        {gauge.change}
                      </span>
                    </div>
                    <div className="mt-2 flex items-baseline gap-1">
                      <span className="text-2xl font-bold tracking-tight text-white">{gauge.value.toFixed(1)}</span>
                      <span className="text-sm text-muted-foreground">%</span>
                    </div>
                    <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-border">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          gauge.value >= 93 ? "bg-success" : gauge.value >= 85 ? "bg-warning" : "bg-destructive"
                        }`}
                        style={{ width: `${gauge.value}%` }}
                      ></div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Main Dashboard Panel Body Columns */}
              <div className="mt-8 grid gap-8 lg:grid-cols-3">
                
                {/* Left Side: Alert History logs list (2 Columns width) */}
                <div className="lg:col-span-2">
                  <div className="rounded-xl border border-border/50 bg-card">
                    <div className="flex items-center justify-between border-b border-border/50 px-5 py-4">
                      <div className="flex items-center gap-2">
                        <IconAlert className="h-4 w-4 text-destructive" />
                        <h2 className="text-sm font-semibold text-white">История алертов</h2>
                        <span className="rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-medium text-destructive">
                          {allAlerts.length}
                        </span>
                      </div>
                      
                      {/* Search and Filters */}
                      <div className="flex items-center gap-2">
                        <div className="relative">
                          <IconSearch className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                          <input
                            type="text"
                            placeholder="Поиск..."
                            value={alertSearch}
                            onChange={(e) => setAlertSearch(e.target.value)}
                            className="w-40 rounded-lg border border-border bg-background py-1.5 pl-8 pr-3 text-xs outline-none transition focus:border-primary/50 text-white"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Alerts entries */}
                    <div className="divide-y divide-border/50">
                      {allAlerts.map((alert) => (
                        <div key={alert.id} className="flex items-start gap-4 px-5 py-4 transition hover:bg-accent/5">
                          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-background ring-1 ring-border">
                            <IconAlert className={`h-4 w-4 ${alert.severity === "critical" ? "text-destructive" : "text-warning"}`} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-mono text-muted-foreground">{alert.id}</span>
                              <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                                alert.severity === "critical" ? "bg-destructive/10 text-destructive" : "bg-warning/10 text-warning"
                              }`}>
                                {alert.severity === "critical" ? "Критично" : "Внимание"}
                              </span>
                            </div>
                            <p className="mt-0.5 text-sm font-medium text-white">
                              {alert.type === "no_vest" ? "Нарушение СИЗ: Отсутствует сигнальный жилет" :
                               alert.type === "no_helmet" ? "Нарушение СИЗ: Отсутствует защитная каска" :
                               "Вторжение в опасную геозону погрузки"}
                            </p>
                            <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                              <span>👤 {alert.worker}</span>
                              <span>📍 {alert.zone}</span>
                              <span>🕒 {alert.timestamp}</span>
                            </div>
                          </div>
                          <button className="shrink-0 rounded-lg border border-border bg-background px-2.5 py-1 text-[10px] font-medium text-muted-foreground transition hover:text-foreground">
                            Кадр
                          </button>
                        </div>
                      ))}

                      {allAlerts.length === 0 && (
                        <div className="flex flex-col items-center py-12 text-center">
                          <IconCheck className="h-10 w-10 text-success/50" />
                          <p className="mt-3 text-sm font-medium text-muted-foreground">Нарушений СИЗ и границ не зарегистрировано.</p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Right Side: Video Stream feed and status specs panels */}
                <div className="space-y-6">
                  
                  {/* CCTV camera stream view */}
                  <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
                    <div className="flex items-center justify-between border-b border-border/50 px-4 py-3">
                      <div className="flex items-center gap-2">
                        <IconVideo className="h-4 w-4 text-primary" />
                        <h3 className="text-xs font-semibold text-white">Видеопоток</h3>
                      </div>
                      <span className="inline-flex items-center gap-1 text-[10px] text-success">
                        <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-success"></span>
                        <span>Камера #03 (Haul Road Zone B)</span>
                      </span>
                    </div>

                    {/* Feed display box container */}
                    <div className="relative aspect-video bg-gradient-to-br from-background via-primary/5 to-background">
                      {isWebcamOn ? (
                        <canvas ref={canvasRef} className="w-full h-full object-cover" />
                      ) : (
                        <div className="absolute inset-0 flex flex-col items-center justify-center">
                          <IconVideo className="mx-auto h-8 w-8 text-primary/30" />
                          <p className="mt-2 text-xs text-muted-foreground">Интеграция YOLOv8. Камера готова к работе.</p>
                        </div>
                      )}
                      
                      <video ref={videoRef} className="hidden" playsInline muted />
                      
                      {/* Grid scan lines overlay */}
                      <div className="absolute inset-0 scan-line opacity-20 pointer-events-none" />

                      {/* Mock bounding box visual tags if camera feed is off */}
                      {!isWebcamOn && (
                        <>
                          <div className="absolute left-[20%] top-[30%] rounded border border-success/60 bg-success/10 px-2 py-0.5 text-[10px] text-success">
                            Каска 98%
                          </div>
                          <div className="absolute left-[55%] top-[50%] rounded border border-success/60 bg-success/10 px-2 py-0.5 text-[10px] text-success">
                            Жилет 95%
                          </div>
                          <div className="absolute right-[15%] bottom-[25%] rounded border border-destructive/60 bg-destructive/10 px-2 py-0.5 text-[10px] text-destructive animate-pulse">
                            Нет каски 87%
                          </div>
                        </>
                      )}
                    </div>

                    {/* Stats strip */}
                    <div className="flex items-center justify-between border-t border-border/50 px-4 py-2">
                      <span className="text-[10px] text-muted-foreground">
                        FPS: {isWebcamOn ? "24" : "0"} | Задержка: {inferenceTime ? `${inferenceTime}ms` : "Calibrated"}
                      </span>
                      <button
                        onClick={handleToggleAnomaly}
                        className={`text-[10px] font-bold px-2 py-0.5 rounded transition ${
                          activeAnomalies.dev_cv_safety ? 'bg-destructive/20 border border-destructive/50 text-destructive' : 'bg-primary/10 border border-primary/20 text-primary'
                        }`}
                      >
                        {activeAnomalies.dev_cv_safety ? "⚠️ СИМУЛИРОВАТЬ НАРУШЕНИЕ" : "СИМУЛИРОВАТЬ НАРУШЕНИЕ"}
                      </button>
                    </div>
                  </div>

                  {/* Section list compliance table */}
                  <div className="rounded-xl border border-border/50 bg-card">
                    <div className="border-b border-border/50 px-4 py-3">
                      <h3 className="text-xs font-semibold text-white">Комплаенс по участкам</h3>
                    </div>
                    <div className="divide-y divide-border/50">
                      {[
                        { name: "Участок №1 — Разгрузка", compliance: 96.2, alerts: 0 },
                        { name: "Участок №2 — Сортировка", compliance: 88.5, alerts: 2 },
                        { name: "Участок №3 — Дробление", compliance: stats.compliancePct, alerts: stats.activeViolations },
                        { name: "Участок №4 — Конвейер A", compliance: 97.8, alerts: 0 },
                        { name: "Участок №5 — Мельницы", compliance: 94.0, alerts: 0 },
                        { name: "Участок №6 — Флотация", compliance: 91.2, alerts: 1 }
                      ].map((section, idx) => (
                        <div key={idx} className="flex items-center gap-3 px-4 py-2.5 transition hover:bg-accent/5">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-medium truncate text-white">{section.name}</span>
                              <span className={`text-xs font-semibold ${
                                section.compliance >= 93 ? "text-success" : section.compliance >= 85 ? "text-warning" : "text-destructive"
                              }`}>
                                {section.compliance.toFixed(1)}%
                              </span>
                            </div>
                            <div className="mt-1 h-1 overflow-hidden rounded-full bg-border">
                              <div
                                className={`h-full rounded-full ${
                                  section.compliance >= 93 ? "bg-success" : section.compliance >= 85 ? "bg-warning" : "bg-destructive"
                                }`}
                                style={{ width: `${section.compliance}%` }}
                              ></div>
                            </div>
                          </div>
                          {section.alerts > 0 && (
                            <span className="shrink-0 rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-medium text-destructive">
                              {section.alerts}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* YOLO specifications block card */}
                  <div className="rounded-xl border border-border/50 bg-card p-4">
                    <div className="flex items-center gap-2">
                      <IconZap />
                      <h3 className="text-xs font-semibold text-white">Модель детекции</h3>
                    </div>
                    <div className="mt-3 space-y-2 text-xs text-muted-foreground">
                      <div className="flex justify-between">
                        <span>Архитектура</span>
                        <span className="font-medium text-foreground">YOLOv8x / YOLO11</span>
                      </div>
                      <div className="flex justify-between">
                        <span>mAP@0.5</span>
                        <span className="font-medium text-foreground">0.915</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Классов детекции</span>
                        <span className="font-medium text-foreground">5 (PPE Safety)</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Вычислитель</span>
                        <span className="font-medium text-foreground">NVIDIA Jetson Orin</span>
                      </div>
                    </div>
                  </div>

                </div>
              </div>

            </div>
          </div>
        )}

        {/* PAGE 3: MODULES (100% replica of AN) */}
        {activeTab === 'modules' && (
          <div className="min-h-screen pt-4 pb-12">
            <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
              
              <div className="text-center mb-10">
                <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-4 py-1.5 text-xs font-medium text-primary">
                  <span>Единая архитектура — 15 кейсов</span>
                </div>
                <h1 className="text-3xl font-bold tracking-tight sm:text-4xl text-white">Модули платформы</h1>
                <p className="mx-auto mt-4 max-w-2xl text-muted-foreground">
                  Все 15 индустриальных кейсов реализованы как готовые к подключению модули на базе единого Digital Twin Registry.
                </p>
              </div>

              {/* Status tally cards */}
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="rounded-xl border border-success/20 bg-success/5 p-5 text-center">
                  <span className="text-2xl font-bold text-success">1</span>
                  <p className="mt-1 text-xs text-muted-foreground">Реализован с ИИ-моделью</p>
                </div>
                <div className="rounded-xl border border-primary/20 bg-primary/5 p-5 text-center">
                  <span className="text-2xl font-bold text-primary">14</span>
                  <p className="mt-1 text-xs text-muted-foreground">Готовы к подключению</p>
                </div>
                <div className="rounded-xl border border-border/50 bg-card p-5 text-center">
                  <span className="text-2xl font-bold text-white">1</span>
                  <p className="mt-1 text-xs text-muted-foreground">Единая архитектура Registry</p>
                </div>
              </div>

              {/* Modules Listing Grid */}
              <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                {[
                  { id: "case-13", title: "СИЗ и опасное поведение (Кейс 13)", category: "Безопасность", status: "active", desc: "Детекция касок, жилетов и нарушений геозон в реальном времени. Дообученная модель YOLO11/YOLOv8 на Roboflow Construction Safety.", metrics: ["Точность 92.4%", "mAP@50 91.5%", "Задержка <500ms"] },
                  { id: "case-01", title: "Геологоразведка", category: "Разведка", status: "ready", desc: "Спектрометрический анализ кернов, 3D построение геологических пластов.", metrics: ["3D ГИС", "Интеграция датчиков", "Оценка пласта"] },
                  { id: "case-02", title: "Карьерный транспорт", category: "Логистика", status: "ready", desc: "Контроль геопозиционирования, скорости, сливов ГСМ и предотвращение столкновений.", metrics: ["GPS трекинг", "Расход топлива", "Proximity radar"] },
                  { id: "case-03", title: "Управление качеством руды", category: "Обогащение", status: "ready", desc: "Оптимизация дозировки ксантогената во флотационных машинах по спектрометрии.", metrics: ["XRF анализ", "Оценка сортности", "Экономия реагентов"] },
                  { id: "case-04", title: "Конвейеры", category: "Логистика", status: "ready", desc: "Определение схода ленты, температуры подшипников и объема рудопотока.", metrics: ["Контроль схода", "Анализ вибрации", "Весовой учет"] }
                ].map(mod => (
                  <div key={mod.id} className={`group relative rounded-xl border bg-card p-6 transition hover:shadow-lg ${
                    mod.status === "active" ? "border-success/20 hover:shadow-success/5" : "border-border/50 hover:border-primary/20 hover:shadow-primary/5"
                  }`}>
                    <div className="absolute right-4 top-4">
                      {mod.status === "active" ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2.5 py-0.5 text-[10px] font-medium text-success">
                          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-success"></span>
                          Реализован
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 text-[10px] font-medium text-primary">
                          Готов
                        </span>
                      )}
                    </div>
                    <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/5">
                      <IconZap />
                    </div>
                    <div className="space-y-2">
                      <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{mod.category}</span>
                      <h3 className="text-base font-semibold text-white">{mod.title}</h3>
                      <p className="text-sm leading-relaxed text-muted-foreground">{mod.desc}</p>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-1.5">
                      {mod.metrics.map(m => (
                        <span key={m} className="rounded-md bg-accent/5 px-2 py-0.5 text-[10px] font-medium text-muted-foreground ring-1 ring-border/50">
                          {m}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

            </div>
          </div>
        )}

        {/* PAGE 4: ABOUT PLATFORM (100% replica of VN/RN) */}
        {activeTab === 'about' && (
          <div className="min-h-screen pt-4 pb-12">
            <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
              
              <div className="text-center mb-12">
                <h1 className="text-3xl font-bold tracking-tight sm:text-4xl text-white">О платформе</h1>
                <p className="mt-4 text-muted-foreground">Industrial Nervous System — нервная система промышленного предприятия</p>
              </div>

              <div className="prose prose-invert max-w-none space-y-8">
                <div className="rounded-xl border border-border/50 bg-card p-6">
                  <h3 className="text-lg font-bold text-white mb-2">Назначение</h3>
                  <p className="text-muted-foreground leading-relaxed text-sm">
                    Платформа разработана как масштабируемое ядро для мониторинга IoT датчиков и анализа видеопотоков на базе концепции Цифровых Двойников (Digital Twins). Вся телеметрия нормализуется, связывается с активами предприятия и транслируется в реальном времени через WebSockets.
                  </p>
                </div>

                <div className="rounded-xl border border-border/50 bg-card p-6">
                  <h3 className="text-lg font-bold text-white mb-2">Используемые технологии</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
                    <div className="p-4 border border-border bg-background rounded-lg text-center">
                      <span className="text-sm font-semibold text-white block">YOLOv8 / YOLO11</span>
                      <span className="text-xs text-muted-foreground">AI Компьютерное зрение</span>
                    </div>
                    <div className="p-4 border border-border bg-background rounded-lg text-center">
                      <span className="text-sm font-semibold text-white block">FastAPI</span>
                      <span className="text-xs text-muted-foreground">Высокопроизводительный бэкенд</span>
                    </div>
                    <div className="p-4 border border-border bg-background rounded-lg text-center">
                      <span className="text-sm font-semibold text-white block">React / Tailwind</span>
                      <span className="text-xs text-muted-foreground">Интерактивный дашборд</span>
                    </div>
                    <div className="p-4 border border-border bg-background rounded-lg text-center">
                      <span className="text-sm font-semibold text-white block">SQLite WAL</span>
                      <span className="text-xs text-muted-foreground">Сверхбыстрая БД телеметрии</span>
                    </div>
                  </div>
                </div>

                <div className="rounded-xl border border-border/50 bg-card p-6">
                  <h3 className="text-lg font-bold text-white mb-2">Команда разработки</h3>
                  <ul className="divide-y divide-border/50 text-sm">
                    <li className="py-3 flex justify-between text-muted-foreground">
                      <span className="text-white font-medium">Алексей К.</span>
                      <span>ML Engineer (Обучение YOLO СИЗ)</span>
                    </li>
                    <li className="py-3 flex justify-between text-muted-foreground">
                      <span className="text-white font-medium">Мария С.</span>
                      <span>Backend Developer (Реестр активов и WebSockets)</span>
                    </li>
                    <li className="py-3 flex justify-between text-muted-foreground">
                      <span className="text-white font-medium">Дмитрий В.</span>
                      <span>UX/UI Designer (Интерфейс Lork, стили бранчей)</span>
                    </li>
                  </ul>
                </div>
              </div>

            </div>
          </div>
        )}

      </main>

      {/* FOOTER SECTION (100% replica of fN) */}
      <footer className="border-t border-border/50 bg-background/50 mt-12 shrink-0">
        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            
            {/* Column 1 Logo */}
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 ring-1 ring-primary/30">
                  <IconZap />
                </div>
                <span className="text-sm font-semibold text-white">
                  Industrial<span className="text-primary">Nervous</span>System
                </span>
              </div>
              <p className="text-sm leading-relaxed text-muted-foreground">
                Edge-to-cloud платформа цифровых двойников для горно-металлургической отрасли. Единая архитектура.
              </p>
            </div>

            {/* Column 2 */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Платформа</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><button onClick={() => setActiveTab('dashboard')} className="hover:text-foreground">Мониторинг СИЗ</button></li>
                <li><button onClick={() => setActiveTab('modules')} className="hover:text-foreground">Модули</button></li>
                <li><button onClick={() => setActiveTab('about')} className="hover:text-foreground">О платформе</button></li>
              </ul>
            </div>

            {/* Column 3 */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Технологии</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><span className="hover:text-foreground">YOLO v8 / YOLO11</span></li>
                <li><span className="hover:text-foreground">Digital Twin Registry</span></li>
                <li><span className="hover:text-foreground">Edge Computing</span></li>
              </ul>
            </div>

            {/* Column 4 */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Документация</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li><span className="hover:text-foreground">API Reference</span></li>
                <li><span className="hover:text-foreground">Архитектура</span></li>
                <li><span className="hover:text-foreground">Внедрение</span></li>
              </ul>
            </div>
          </div>

          <div className="mt-10 border-t border-border/50 pt-6 text-center text-xs text-muted-foreground">
            <p>© 2026 Industrial Nervous System. Все права защищены.</p>
          </div>
        </div>
      </footer>

    </div>
  );
}
