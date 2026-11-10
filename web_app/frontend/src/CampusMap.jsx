import { useEffect, useMemo, useState } from 'react';
import { getMapInfo, getRobotStatus, mapImageUrl } from './api';
import { groupColor, prettyPoint } from './campusPoints';

// Campus map info (image size, metres per pixel, origin, delivery points), loaded once
export function useCampusMap() {
  const [info, setInfo] = useState(null);
  const [error, setError] = useState('');
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let alive = true;
    getMapInfo()
      .then((data) => {
        if (alive) {
          setInfo(data);
          setError('');
        }
      })
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [version]);

  return { info, error, reload: () => setVersion((v) => v + 1) };
}

// Live robot status, polled every `ms` milliseconds
export function useRobotStatus(ms = 1000) {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      getRobotStatus()
        .then((s) => alive && setStatus(s))
        .catch(() => alive && setStatus({ status: 'offline' }));
    load();
    const t = setInterval(load, ms);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [ms]);

  return status;
}

/**
 * The campus map as the robot sees it (the SLAM map of the simulation), with
 * the delivery points, the robot and its route drawn on top.
 *
 * props:
 *   info          map info from useCampusMap()
 *   status        robot status (pose, route) or null
 *   selected      point name or array of names that are highlighted
 *   onSelect      (name) => void; makes points clickable
 *   badges        {pointName: number} small counters next to points
 *   previewPath   [[x, y], ...] planned route (dashed)
 *   order         [pointName, ...] numbers the stops in this order
 *   showHome      draw the home point (default true)
 */
function CampusMap({ info, status, selected, onSelect, badges = {}, previewPath, order,
                     showHome = true, height }) {
  const [hover, setHover] = useState(null);
  const [imgError, setImgError] = useState(false);

  const sel = useMemo(
    () => new Set(Array.isArray(selected) ? selected : selected ? [selected] : []),
    [selected],
  );

  if (!info) {
    return <div className="campus-map campus-map-empty">Loading the campus map…</div>;
  }

  const { width: W, height: H, resolution: res, x0, y0 } = info;
  const toPx = (x, y) => [(x - x0) / res, H - (y - y0) / res];
  const r = Math.max(7, Math.min(W, H) / 45);
  const font = r * 1.25;
  const pathStr = (pts) =>
    (pts || []).map(([x, y]) => toPx(x, y).map((v) => v.toFixed(1)).join(',')).join(' ');

  const points = (info.points || []).filter((p) => showHome || p.name !== 'home');
  const pose = status && status.pose;
  const route = status && status.route;
  const stopNumber = {};
  (order || []).forEach((n, i) => {
    stopNumber[n] = i + 1;
  });

  return (
    <div className="campus-map" style={height ? { maxHeight: height } : undefined}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" role="img"
           aria-label="Campus delivery map">
        {!imgError && (
          <image href={mapImageUrl()} x="0" y="0" width={W} height={H}
                 style={{ imageRendering: 'pixelated' }} onError={() => setImgError(true)} />
        )}
        {imgError && <rect x="0" y="0" width={W} height={H} fill="#e8f1f4" />}

        {previewPath && previewPath.length > 1 && (
          <polyline points={pathStr(previewPath)} fill="none" stroke="#1f6feb"
                    strokeWidth={r * 0.45} strokeDasharray={`${r} ${r * 0.6}`}
                    strokeLinecap="round" strokeLinejoin="round" opacity="0.85" />
        )}
        {route && route.length > 1 && (
          <polyline points={pathStr(route)} fill="none" stroke="#d1242f"
                    strokeWidth={r * 0.4} strokeLinecap="round" strokeLinejoin="round"
                    opacity="0.8" />
        )}

        {points.map((p) => {
          const [px, py] = toPx(p.x, p.y);
          const isHome = p.name === 'home';
          const isSel = sel.has(p.name);
          const color = isHome ? '#444' : groupColor(p.name);
          const badge = badges[p.name];
          const num = stopNumber[p.name];
          return (
            <g key={p.name} transform={`translate(${px},${py})`}
               className={onSelect && !isHome ? 'campus-point clickable' : 'campus-point'}
               onClick={() => onSelect && !isHome && onSelect(p.name)}
               onMouseEnter={() => setHover(p.name)} onMouseLeave={() => setHover(null)}>
              {isSel && <circle r={r * 1.9} fill={color} opacity="0.22" />}
              {isHome ? (
                <rect x={-r} y={-r} width={r * 2} height={r * 2} rx={r * 0.3} fill="#fff"
                      stroke={color} strokeWidth={r * 0.3} />
              ) : (
                <circle r={r} fill={isSel ? color : '#fff'} stroke={color}
                        strokeWidth={r * 0.3} />
              )}
              <text y={r * 0.42} textAnchor="middle" fontSize={font * 0.85} fontWeight="700"
                    fill={isSel ? '#fff' : color} pointerEvents="none">
                {isHome ? 'H' : num || p.markerId || '•'}
              </text>
              {badge > 0 && (
                <g transform={`translate(${r * 1.05},${-r * 1.05})`}>
                  <circle r={r * 0.75} fill="#d1242f" />
                  <text y={r * 0.3} textAnchor="middle" fontSize={font * 0.7} fill="#fff"
                        fontWeight="700" pointerEvents="none">{badge}</text>
                </g>
              )}
              {(hover === p.name || isSel) && (
                <text y={-r * 1.6} fontSize={font} fontWeight="700"
                      textAnchor={px > W * 0.8 ? 'end' : px < W * 0.2 ? 'start' : 'middle'}
                      x={px > W * 0.8 ? r : px < W * 0.2 ? -r : 0}
                      fill="#17211d" stroke="#fff" strokeWidth={font * 0.25}
                      paintOrder="stroke" pointerEvents="none">
                  {prettyPoint(p.name)}
                </text>
              )}
            </g>
          );
        })}

        {pose && Number.isFinite(pose.x) && (() => {
          const [px, py] = toPx(pose.x, pose.y);
          const a = -(pose.yawDeg || 0);
          return (
            <g transform={`translate(${px},${py}) rotate(${a})`} pointerEvents="none">
              <circle r={r * 1.5} fill="#d1242f" opacity="0.18" />
              <polygon points={`${r * 1.4},0 ${-r * 0.9},${r * 0.85} ${-r * 0.5},0 ${-r * 0.9},${-r * 0.85}`}
                       fill="#d1242f" stroke="#fff" strokeWidth={r * 0.15} />
            </g>
          );
        })()}
      </svg>

      <div className="campus-map-legend">
        <span><i className="dot" /> Delivery point (ArUco ID)</span>
        <span><i className="robot" /> Robot</span>
        <span><i className="line red" /> Current route</span>
        {previewPath && <span><i className="line blue" /> Planned route</span>}
      </div>
    </div>
  );
}

export default CampusMap;
