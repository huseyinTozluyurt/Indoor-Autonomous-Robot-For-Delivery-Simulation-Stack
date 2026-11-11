import { arucoAccuracy } from '../data.js'

// Line chart: PnP range error vs distance for a 0.30 m marker (Report 2, synthetic test).
export default function AccuracyChart() {
  const W = 560, H = 300, L = 52, R = 16, T = 18, B = 44
  const xs = arucoAccuracy.distances
  const xMax = 9, yMax = 80
  const x = (d) => L + ((d - 0) / xMax) * (W - L - R)
  const y = (v) => T + (1 - v / yMax) * (H - T - B)
  const cls = ['s1', 's2', 's3']
  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Range error in centimetres against distance in metres for three marker angles. Error stays under 8 cm up to 3 m and grows to tens of centimetres beyond 5 m.">
        {[0, 20, 40, 60, 80].map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} className="grid" />
            <text x={L - 8} y={y(v) + 4} textAnchor="end" className="tick">{v}</text>
          </g>
        ))}
        {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((d) => (
          <text key={d} x={x(d)} y={H - B + 18} textAnchor="middle" className="tick">{d}</text>
        ))}
        <rect x={x(0)} y={T} width={x(3) - x(0)} height={H - T - B} className="band" />
        <text x={x(1.5)} y={T + 16} textAnchor="middle" className="band-lbl">delivery stand-off ≤ 3 m</text>
        <text x={(L + W - R) / 2} y={H - 6} textAnchor="middle" className="axis">distance to marker (m)</text>
        <text x={14} y={(T + H - B) / 2} textAnchor="middle" className="axis" transform={`rotate(-90 14 ${(T + H - B) / 2})`}>range error (cm)</text>
        {arucoAccuracy.series.map((s, i) => {
          const pts = xs.map((d, j) => [d, s.values[j]]).filter(([, v]) => v != null)
          return (
            <g key={s.name} className={cls[i]}>
              <polyline points={pts.map(([d, v]) => `${x(d)},${y(v)}`).join(' ')} className="line" />
              {pts.map(([d, v]) => (
                <circle key={d} cx={x(d)} cy={y(v)} r="3.5" className="dot"><title>{`${s.name}, ${d} m: ${v} cm`}</title></circle>
              ))}
            </g>
          )
        })}
      </svg>
      <div className="legend">
        {arucoAccuracy.series.map((s, i) => (
          <span key={s.name} className={cls[i]}><i />{s.name}</span>
        ))}
      </div>
      <figcaption>A 0.30 m marker rendered through the exact mast-camera model. A few centimetres at the 2.3 m delivery stand-off, decimetres beyond 5 m, which is why far-away landmarks are 0.6 m and 1.0 m markers.</figcaption>
    </figure>
  )
}
