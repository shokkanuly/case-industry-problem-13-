import React, { useRef, useEffect, useState, useCallback } from 'react';

/**
 * PhonePage — full-screen phone camera streaming page.
 * Supports both:
 * 1. Live stream (requires secure context HTTPS or chrome flags bypass)
 * 2. Snap upload fallback (works on any HTTP connection using native file capture)
 */

const FRAME_INTERVAL_MS = 250; // 4 FPS

export default function PhonePage() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);
  const intervalRef = useRef(null);
  const streamRef = useRef(null);
  const fileInputRef = useRef(null);

  const [status, setStatus] = useState('idle'); // idle | connecting | streaming | error | disconnected | snaps_mode
  const [facingMode, setFacingMode] = useState('environment'); // rear
  const [framesSent, setFramesSent] = useState(0);
  const [wsUrl, setWsUrl] = useState('');
  const [lastError, setLastError] = useState('');
  const [detectionInfo, setDetectionInfo] = useState(null);
  const [hasMediaDevices, setHasMediaDevices] = useState(true);
  const [snapPreview, setSnapPreview] = useState(null);

  useEffect(() => {
    const host = window.location.hostname;
    setWsUrl(`ws://${host}:8000/ws`);

    // Check if secure context mediaDevices is available
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setHasMediaDevices(false);
      setStatus('snaps_mode');
    }
  }, []);

  const stopStream = useCallback(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (wsRef.current) wsRef.current.close();
    if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
    intervalRef.current = null;
    wsRef.current = null;
    streamRef.current = null;
  }, []);

  // Connect WebSocket for snap mode
  const ensureWebSocket = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      return wsRef.current;
    }
    const ws = new WebSocket(wsUrl || `ws://${window.location.hostname}:8000/ws`);
    wsRef.current = ws;
    
    ws.onopen = () => {
      if (status !== 'snaps_mode') setStatus('streaming');
    };
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'phone_analysis' || data.person_count !== undefined) {
          setDetectionInfo(data);
        }
      } catch {}
    };
    ws.onerror = () => {
      setLastError('Не удалось подключить WebSocket. Проверьте сеть.');
    };
    ws.onclose = () => {
      if (status === 'streaming') setStatus('disconnected');
    };
    return ws;
  }, [wsUrl, status]);

  const startStream = useCallback(async (facing) => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setHasMediaDevices(false);
      setStatus('snaps_mode');
      ensureWebSocket();
      return;
    }

    stopStream();
    setStatus('connecting');
    setLastError('');

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: facing,
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false
      });
      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      const ws = ensureWebSocket();

      ws.onopen = () => {
        setStatus('streaming');
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
          const dataUrl = canvas.toDataURL('image/jpeg', 0.70);

          ws.send(JSON.stringify({
            type: 'phone_frame',
            frame: dataUrl,
            timestamp: Date.now()
          }));
          setFramesSent(n => n + 1);
        }, FRAME_INTERVAL_MS);
      };

    } catch (err) {
      setStatus('error');
      setLastError(`Ошибка камеры: ${err.message}. Переключаем в режим фото-захвата.`);
      setTimeout(() => {
        setStatus('snaps_mode');
        ensureWebSocket();
      }, 3000);
    }
  }, [ensureWebSocket, stopStream]);

  // Handle native mobile snapshot upload fallback
  const handleSnapCapture = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onloadend = () => {
      const dataUrl = reader.result;
      setSnapPreview(dataUrl);
      
      // Ensure WebSocket is open and send
      const ws = ensureWebSocket();
      const sendFrame = () => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: 'phone_frame',
            frame: dataUrl,
            timestamp: Date.now()
          }));
          setFramesSent(n => n + 1);
        } else {
          setTimeout(sendFrame, 100);
        }
      };
      sendFrame();
    };
    reader.readAsDataURL(file);
  };

  useEffect(() => {
    if (wsUrl) {
      if (hasMediaDevices) {
        startStream(facingMode);
      } else {
        ensureWebSocket();
      }
    }
    return stopStream;
  }, [wsUrl, hasMediaDevices, startStream, facingMode, ensureWebSocket, stopStream]);

  const toggleCamera = () => {
    const newFacing = facingMode === 'environment' ? 'user' : 'environment';
    setFacingMode(newFacing);
    if (hasMediaDevices) startStream(newFacing);
  };

  const statusColor = {
    idle: '#6b7280',
    connecting: '#f59e0b',
    streaming: '#10b981',
    snaps_mode: '#3b82f6',
    error: '#ef4444',
    disconnected: '#6b7280',
  }[status];

  const statusLabel = {
    idle: 'Ожидание...',
    connecting: 'Подключение...',
    streaming: '● Трансляция СИЗ',
    snaps_mode: '📸 Режим фото-кнопки',
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
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      color: '#fff'
    }}>
      {/* Background Live Video / Static Snap Preview */}
      {status === 'streaming' ? (
        <video
          ref={videoRef}
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
          playsInline muted autoPlay
        />
      ) : snapPreview ? (
        <img
          src={snapPreview}
          alt="Snap Preview"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', opacity: 0.8 }}
        />
      ) : (
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          padding: 24, textAlign: 'center', background: '#0a0d14'
        }}>
          <span style={{ fontSize: 48, marginBottom: 12 }}>🔒</span>
          <h3 style={{ fontSize: 16, fontWeight: 700, margin: '0 0 8px' }}>Защищенный контекст (HTTPS)</h3>
          <p style={{ fontSize: 12, color: '#9ca3af', lineHeight: '1.6', maxWidth: 280 }}>
            Мобильные браузеры блокируют live-видео через HTTP. Используйте фото-кнопку снизу, либо настройте HTTPS.
          </p>
        </div>
      )}
      
      <canvas ref={canvasRef} style={{ display: 'none' }} />

      {/* Top Header */}
      <div style={{
        position: 'relative', zIndex: 10,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '16px 20px',
        background: 'linear-gradient(to bottom, rgba(0,0,0,0.85), transparent)'
      }}>
        <div>
          <div style={{ color: '#c8f542', fontWeight: 800, fontSize: 15, letterSpacing: '0.05em' }}>
            IndustrialNervousSystem
          </div>
          <div style={{ color: '#9ca3af', fontSize: 10, marginTop: 2 }}>
            {status === 'snaps_mode' ? 'Нажмите кнопку снизу для снимка' : 'Камера устройства'}
          </div>
        </div>
        <div style={{
          padding: '5px 12px', borderRadius: 999,
          background: 'rgba(0,0,0,0.6)',
          border: `1.5px solid ${statusColor}`,
          color: statusColor, fontSize: 11, fontWeight: 700
        }}>
          {statusLabel}
        </div>
      </div>

      {/* Badges Overlays */}
      {detectionInfo && (
        <div style={{
          position: 'absolute', top: 76, left: '50%', transform: 'translateX(-50%)',
          display: 'flex', gap: 6, zIndex: 10
        }}>
          <Badge label={`👤 ${persons}`} color={persons > 0 ? '#3b82f6' : '#9ca3af'} />
          <Badge
            label={violations > 0 ? `⚠ ${violations} нарушений` : '✓ Соответствует'}
            color={violations > 0 ? '#ef4444' : '#10b981'}
          />
          <Badge label={`${compliance}%`} color={compliance < 80 ? '#f59e0b' : '#10b981'} />
        </div>
      )}

      {/* Hidden File Input for snapshot bypass */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleSnapCapture}
        style={{ display: 'none' }}
      />

      {/* Quick guide helper for Chrome Flags */}
      {!hasMediaDevices && !snapPreview && (
        <div style={{
          position: 'absolute', top: '35%', left: 20, right: 20,
          background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 12, padding: '16px 20px', fontSize: 11, color: '#9ca3af',
          lineHeight: '1.5', zIndex: 10
        }}>
          <div style={{ color: '#fff', fontWeight: 700, marginBottom: 6 }}>💡 Включение Live-камеры на Android:</div>
          Откройте в Chrome: <span style={{ color: '#c8f542', fontFamily: 'monospace' }}>chrome://flags</span><br/>
          Найдите: <span style={{ color: '#fff' }}>"Insecure origins treated as secure"</span><br/>
          Добавьте: <span style={{ color: '#c8f542', fontFamily: 'monospace' }}>{`http://${window.location.hostname}:5174`}</span><br/>
          Переключите in Enabled и перезапустите браузер.
        </div>
      )}

      {/* Bottom control pad */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 10,
        padding: '24px 32px 40px',
        background: 'linear-gradient(to top, rgba(0,0,0,0.85), transparent)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 24
      }}>
        {status === 'snaps_mode' ? (
          // Giant Snapshot button for HTTP bypass
          <button
            onClick={() => fileInputRef.current?.click()}
            style={{
              background: '#3b82f6',
              border: 'none',
              borderRadius: 16,
              padding: '16px 28px',
              color: '#fff',
              fontWeight: 800,
              fontSize: 14,
              boxShadow: '0 8px 16px rgba(59,130,246,0.3)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8
            }}
          >
            <span style={{ fontSize: 20 }}>📸</span> Сделать снимок для СИЗ
          </button>
        ) : (
          <>
            <TapButton onTap={() => startStream(facingMode)} icon="↺" label="Перезапуск" />
            <div style={{
              width: 60, height: 60, borderRadius: '50%',
              background: status === 'streaming' ? '#ef4444' : '#374151',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: status === 'streaming' ? '0 0 0 6px rgba(239,68,68,0.2)' : 'none',
            }}>
              <div style={{
                width: status === 'streaming' ? 20 : 26,
                height: status === 'streaming' ? 20 : 26,
                borderRadius: status === 'streaming' ? 4 : '50%',
                background: '#fff'
              }} />
            </div>
            <TapButton onTap={toggleCamera} icon="⟳" label="Камера" />
          </>
        )}
      </div>
    </div>
  );
}

function Badge({ label, color }) {
  return (
    <div style={{
      padding: '4px 10px', borderRadius: 999,
      background: 'rgba(0,0,0,0.7)',
      border: `1.5px solid ${color}`,
      color, fontSize: 11, fontWeight: 700,
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
        background: 'rgba(255,255,255,0.06)',
        border: '1px solid rgba(255,255,255,0.15)',
        borderRadius: 14, padding: '8px 14px',
        color: '#fff', cursor: 'pointer',
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
        fontSize: 18
      }}
    >
      <span>{icon}</span>
      <span style={{ fontSize: 9, color: '#9ca3af', fontWeight: 600 }}>{label}</span>
    </button>
  );
}
