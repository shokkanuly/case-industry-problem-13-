import React from 'react';

export default function RecommendationDial({ value, min = 0, max = 20, unit = '', title = 'Optimal' }) {
  const radius = 70;
  const strokeWidth = 12;
  const circumference = 2 * Math.PI * radius;
  
  const percent = Math.min(Math.max((value - min) / (max - min), 0), 1);
  const strokeDashoffset = circumference - percent * circumference;
  
  let color = 'var(--neon-cyan)';
  if (percent > 0.8) color = 'var(--state-critical)';
  else if (percent > 0.6) color = 'var(--state-warning)';

  const angle = (percent * 180) - 90;

  return (
    <div className="dial-container">
      <svg className="dial-circle-svg" width="200" height="200">
        <circle 
          className="dial-bg" 
          cx="100" 
          cy="100" 
          r={radius} 
          strokeWidth={strokeWidth} 
        />
        <circle 
          className="dial-progress" 
          cx="100" 
          cy="100" 
          r={radius} 
          strokeWidth={strokeWidth} 
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          stroke={color}
          style={{ filter: `drop-shadow(0 0 5px ${color})` }}
        />
        <polygon 
          className="dial-needle" 
          points="97,100 103,100 100,40" 
          style={{ 
            transform: `rotate(${angle}deg)`, 
            fill: color, 
            filter: `drop-shadow(0 0 4px ${color})` 
          }} 
        />
        <circle cx="100" cy="100" r="8" fill="#fff" />
      </svg>
      <div className="dial-readout">
        <span className="dial-value">{value.toFixed(1)}{unit}</span>
        <span className="dial-label">{title}</span>
      </div>
    </div>
  );
}
