import { useState, useEffect } from 'react';
import { StatusIndicator } from './StatusIndicator';

/**
 * Header — Stark top bar with brand, pipeline status, device count, and live clock.
 */
export function Header({ isConnected, activeDevices, totalDevices }) {
  const [clock, setClock] = useState('');

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setClock(
        now.toLocaleTimeString('en-US', {
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        })
      );
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="header">
      <div className="header-brand">
        <h1>EDGE TELEMETRY</h1>
        <span className="subtitle">OPERATIONAL INTELLIGENCE</span>
      </div>

      <div className="header-status">
        <div className="header-stat">
          <StatusIndicator status={isConnected ? 'online' : 'offline'} />
          <span>{isConnected ? 'PIPELINE LIVE' : 'DISCONNECTED'}</span>
        </div>

        <div className="header-stat">
          <span>DEVICES</span>
          <span className="value">
            {activeDevices}/{totalDevices}
          </span>
        </div>

        <div className="header-clock">{clock}</div>
      </div>
    </header>
  );
}
