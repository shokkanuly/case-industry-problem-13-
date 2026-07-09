import React, { useRef, useEffect, useState, useCallback } from 'react';

/**
 * PhonePage — full-screen phone camera streaming page.
 * Designed for mobile browsers. Opens phone camera and streams
 * frames via WebSocket to the backend YOLO analysis pipeline.
 *
 * Usage: Open http://<server-ip>:5174/phone on your phone browser.
 */

const FRAME_INTERVAL_MS = 200; // 5 FPS — good balance for 1080p + YOLO latency

export default function PhonePage() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);
  const intervalRef = useRef(null);
  const streamRef = useRef(null);

  const [status, setStatus] = useState('idle'); // idle | connecting | streaming | error | disconnected
  const [facingMode, setFacingMode] = useState('environment'); // rear camera by default
  const [framesSent, setFramesSent] = useState(0);
  const [wsUrl, setWsUrl] = useState('');
  const [lastError, setLastError] = useState('');
  const [detectionInfo, setDetectionInfo] = useState(null);

  // Detect backend URL (same host, port 8000)
  useEffect(() => {
    const host = window.location.hostname;
    setWsUrl(`ws://${host}:8000/ws`);
  }, []);

  const stopStream = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (wsRef.current) wsRef.current.close();
    if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
    intervalRef.current = null;
    wsRef.current = null;
    streamRef.current = null;
  }, []);

  const startStream = useCallback(async (facing) => {
    stopStream();
    setStatus('connecting');
    setLastError('');

    try {
      // Request camera access
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: facing,
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false
      });
      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      // Connect WebSocket
      const ws = new WebSocket(wsUrl || `ws://${window.location.hostname}:8000/ws`);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('streaming');
        // Send frames at regular interval
        intervalRef.current = setInterval(() => {
          if (!videoRef.current || !canvasRef.current) return;
          if (ws.readyState !== WebSocket.OPEN) return;

          const video = videoRef.current;
          if (video.videoWidth === 0) return;

          const canvas = canvasRef.current;
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          const ctx = canvas.getContext('2d');
          ctx.drawImage(video, 0, 0);
          const dataUrl = canvas.toDataURL('image/jpeg', 0.75);

          ws.send(JSON.stringify({
            type: 'phone_frame',
            frame: dataUrl,
            timestamp: Date.now()
          }));
          setFramesSent(n => n + 1);
        }, FRAME_INTERVAL_MS);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'analysis_result' || data.person_count !== undefined) {
            setDetectionInfo(data);
          }
        } catch {}
      };

      ws.onerror = () => {
        setStatus('error');
        setLastError('WebSocket connection failed. Make sure you are on the same WiFi as the server.');
      };

      ws.onclose = () => {
        if (intervalRef.current) clearInterval(intervalRef.current);
        setStatus('disconnected');
      };

    } catch (err) {
      setStatus('error');
      if (err.name === 'NotAllowedError') {
        setLastError('Camera access denied. Please allow camera in browser settings.');
      } else if (err.name === 'NotFoundError') {
        setLastError('No camera found on this device.');
      } else {
        setLastError(`Camera error: ${err.message}`);
      }
    }
  }, [wsUrl, stopStream]);

  const toggleCamera = useCallback(() => {
    const newFacing = facingMode === 'environment' ? 'user' : 'environment';
    setFacingMode(newFacing);
    startStream(newFacing);
  }, [facingMode, startStream]);

  useEffect(() => {
    if (wsUrl) startStream(facingMode);
    return stopStream;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsUrl]);

  const statusColor = {
    idle: '#6b7280',
    connecting: '#f59e0b',
    streaming: '#10b981',
    error: '#ef4444',
    disconnected: '#6b7280',
  }[status];

  const statusLabel = {
    idle: 'Ожидание...',
    connecting: 'Подключение...',
    streaming: '● Трансляция активна',
    error: '✗ Ошибка',
    disconnected: '○ Отключено',
  }[status];

  const violations = detectionInfo?.active_violations ?? 0;
  const persons = detectionInfo?.person_count ?? 0;
  const compliance = detectionInfo?.compliance_pct ?? 100;

  return (
    <div style={{
      position: 'fixed', inset: 0,
      background: '#000',
      display: 'flex', flexDirection: 'column',
      fontFamily: "'Inter', sans-serif",
      userSelect: 'none',
      WebkitUserSelect: 'none'
    }}>
      {/* Video fill */}
      <video
        ref={videoRef}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
        playsInline muted autoPlay
      />
      <canvas ref={canvasRef} style={{ display: 'none' }} />

      {/* Top bar */}
      <div style={{
        position: 'relative', zIndex: 10,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '16px 20px',
        background: 'linear-gradient(to bottom, rgba(0,0,0,0.75), transparent)'
      }}>
        <div>
          <div style={{ color: '#c8f542', fontWeight: 800, fontSize: 15, letterSpacing: '0.05em' }}>
            IndustrialNervousSystem
          </div>
          <div style={{ color: '#6b7280', fontSize: 11, marginTop: 2 }}>Камера устройства</div>
        </div>
        <div style={{
          padding: '5px 12px', borderRadius: 999,
          background: 'rgba(0,0,0,0.5)',
          border: `1.5px solid ${statusColor}`,
          color: statusColor, fontSize: 11, fontWeight: 700
        }}>
          {statusLabel}
        </div>
      </div>

      {/* Detection overlay badges */}
      {status === 'streaming' && detectionInfo && (
        <div style={{
          position: 'absolute', top: 80, left: '50%', transform: 'translateX(-50%)',
          display: 'flex', gap: 8, zIndex: 10
        }}>
          <Badge label={`👤 ${persons}`} color={persons > 0 ? '#3b82f6' : '#374151'} />
          <Badge
            label={violations > 0 ? `⚠ ${violations} нарушений` : '✓ Соответствует'}
            color={violations > 0 ? '#ef4444' : '#10b981'}
          />
          <Badge label={`${compliance}%`} color={compliance < 80 ? '#f59e0b' : '#10b981'} />
        </div>
      )}

      {/* Error message */}
      {lastError && (
        <div style={{
          position: 'absolute', top: '40%', left: 20, right: 20,
          background: 'rgba(239,68,68,0.15)', border: '1px solid #ef4444',
          borderRadius: 12, padding: '16px 20px', color: '#fca5a5',
          fontSize: 13, textAlign: 'center', zIndex: 20
        }}>
          {lastError}
        </div>
      )}

      {/* Frames counter */}
      {status === 'streaming' && (
        <div style={{
          position: 'absolute', top: 130, right: 16, zIndex: 10,
          background: 'rgba(0,0,0,0.45)', borderRadius: 8,
          padding: '4px 10px', color: '#6b7280', fontSize: 10
        }}>
          {framesSent} кадров отправлено
        </div>
      )}

      {/* Bottom controls */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 10,
        padding: '24px 32px 40px',
        background: 'linear-gradient(to top, rgba(0,0,0,0.80), transparent)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between'
      }}>
        {/* Reconnect */}
        <TapButton
          onTap={() => startStream(facingMode)}
          icon="↺"
          label="Переподключить"
        />

        {/* Record indicator */}
        <div style={{
          width: 64, height: 64, borderRadius: '50%',
          background: status === 'streaming' ? '#ef4444' : '#374151',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: status === 'streaming' ? '0 0 0 6px rgba(239,68,68,0.25)' : 'none',
          transition: 'all 0.3s ease'
        }}>
          <div style={{
            width: status === 'streaming' ? 20 : 28,
            height: status === 'streaming' ? 20 : 28,
            borderRadius: status === 'streaming' ? 4 : '50%',
            background: '#fff',
            transition: 'all 0.3s ease'
          }} />
        </div>

        {/* Flip camera */}
        <TapButton
          onTap={toggleCamera}
          icon="⟳"
          label={facingMode === 'environment' ? 'Фронтальная' : 'Задняя'}
        />
      </div>
    </div>
  );
}

function Badge({ label, color }) {
  return (
    <div style={{
      padding: '5px 12px', borderRadius: 999,
      background: 'rgba(0,0,0,0.6)',
      border: `1.5px solid ${color}`,
      color, fontSize: 12, fontWeight: 700,
      whiteSpace: 'nowrap'
    }}>
      {label}
    </div>
  );
}

function TapButton({ onTap, icon, label }) {
  return (
    <button
      onClick={onTap}
      style={{
        background: 'rgba(255,255,255,0.1)',
        border: '1.5px solid rgba(255,255,255,0.2)',
        borderRadius: 14, padding: '10px 16px',
        color: '#fff', cursor: 'pointer',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
        WebkitTapHighlightColor: 'transparent',
        fontSize: 22
      }}
    >
      <span>{icon}</span>
      <span style={{ fontSize: 10, color: '#9ca3af', fontWeight: 600 }}>{label}</span>
    </button>
  );
}
