'use client';

import React, { useRef, useEffect, useCallback, useId } from 'react';

const TITLE = 'AWS Security Autopilot';

export default function AWSSecurityAutopilotTextEffect() {
  const hoverWrapRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const maskGradientRef = useRef<SVGRadialGradientElement>(null);
  const id = useId().replace(/:/g, '');

  const textGradientId = `textGradient-${id}`;
  const revealMaskId = `revealMask-${id}`;
  const textMaskId = `textMask-${id}`;

  const setMaskPosition = useCallback((ev: MouseEvent) => {
    const svg = svgRef.current;
    const gradient = maskGradientRef.current;
    if (!svg || !gradient) return;
    const rect = svg.getBoundingClientRect();
    const x = ((ev.clientX - rect.left) / rect.width) * 100;
    const y = ((ev.clientY - rect.top) / rect.height) * 100;
    gradient.setAttribute('cx', `${x}%`);
    gradient.setAttribute('cy', `${y}%`);
  }, []);

  useEffect(() => {
    const wrap = hoverWrapRef.current;
    const gradient = maskGradientRef.current;
    if (!wrap || !gradient) return;

    const onEnter = () => {
      wrap.addEventListener('mousemove', setMaskPosition);
    };
    const onLeave = () => {
      wrap.removeEventListener('mousemove', setMaskPosition);
      gradient.setAttribute('cx', '50%');
      gradient.setAttribute('cy', '50%');
    };

    wrap.addEventListener('mouseenter', onEnter);
    wrap.addEventListener('mouseleave', onLeave);
    return () => {
      wrap.removeEventListener('mouseenter', onEnter);
      wrap.removeEventListener('mouseleave', onLeave);
      wrap.removeEventListener('mousemove', setMaskPosition);
    };
  }, [setMaskPosition]);

  return (
    <>
      <style>{`
        .aws-autopilot-text-outline {
          fill: none;
          stroke: #e5e5e5;
          stroke-width: 0.3;
          opacity: 0.9;
          transition: opacity 0.2s;
        }
        .aws-autopilot-text-wrap:hover .aws-autopilot-text-outline {
          opacity: 0.7;
        }
        .aws-autopilot-text-gradient {
          fill: #ffffff;
          stroke: none;
          font: bold 48px helvetica, sans-serif;
        }
      `}</style>
      {/* Size by width so the SVG scales with no empty space; min-width makes the text actually large */}
      <div
        ref={hoverWrapRef}
        className="aws-autopilot-text-wrap inline-block w-full select-none"
        style={{ marginTop: 0, minWidth: 'min(95vw, 60rem)' }}
      >
        <svg
          ref={svgRef}
          viewBox="0 0 700 100"
          xmlns="http://www.w3.org/2000/svg"
          className="block w-full"
          style={{ height: 'auto', aspectRatio: '700 / 100' }}
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
            <linearGradient
              id={textGradientId}
              x1="0%"
              y1="0%"
              x2="100%"
              y2="0%"
            >
              <stop offset="0%" stopColor="#263b5d" />
              <stop offset="25%" stopColor="#ef4444" />
              <stop offset="50%" stopColor="#3b82f6" />
              <stop offset="75%" stopColor="#06b6d4" />
              <stop offset="100%" stopColor="#8b5cf6" />
            </linearGradient>
            <radialGradient
              ref={maskGradientRef}
              id={revealMaskId}
              r="42%"
              cx="50%"
              cy="50%"
            >
              <stop offset="0%" stopColor="white" />
              <stop offset="100%" stopColor="black" />
            </radialGradient>
            <mask id={textMaskId}>
              <rect
                x={0}
                y={0}
                width="100%"
                height="100%"
                fill={`url(#${revealMaskId})`}
              />
            </mask>
          </defs>
          <text
            x={350}
            y={50}
            textAnchor="middle"
            dominantBaseline="middle"
            className="aws-autopilot-text-outline aws-autopilot-text-gradient"
          >
            {TITLE}
          </text>
          <text
            x={350}
            y={50}
            textAnchor="middle"
            dominantBaseline="middle"
            className="aws-autopilot-text-gradient"
          >
            {TITLE}
          </text>
        </svg>
      </div>
    </>
  );
}
