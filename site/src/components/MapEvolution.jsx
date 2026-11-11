import { useState } from 'react'
import { mapRuns, fig } from '../data.js'
import { Figure } from './Lightbox.jsx'

const metrics = {
  shape: { short: 'Shape error', label: 'Shape error after rigid fit', unit: 'm', log: true },
  rot: { short: 'Rotation', label: 'Global map rotation', unit: '°', log: true },
  path: { short: 'Path driven', label: 'Path driven to finish', unit: 'm', log: false },
}

// Bar list of every mapping run; click a run to see its notes and figure.
export default function MapEvolution() {
  const [metric, setMetric] = useState('shape')
  const [sel, setSel] = useState(mapRuns.length - 1)
  const m = metrics[metric]
  const vals = mapRuns.map((r) => r[metric])
  const max = Math.max(...vals)
  const min = Math.min(...vals)
  const scale = (v) =>
    m.log ? 0.04 + 0.96 * (Math.log10(v) - Math.log10(min * 0.8)) / (Math.log10(max) - Math.log10(min * 0.8)) : v / max
  const run = mapRuns[sel]
  return (
    <div className="evo">
      <div className="evo-left">
        <div className="seg" role="tablist" aria-label="Metric">
          {Object.entries(metrics).map(([k, v]) => (
            <button key={k} role="tab" aria-selected={metric === k} className={metric === k ? 'on' : ''} onClick={() => setMetric(k)}>
              {v.short}
            </button>
          ))}
        </div>
        <p className="evo-metric">{m.label}{m.log ? ' (log scale)' : ''}. Four aborted start-up tests are left out.</p>
        <ol className="bars">
          {mapRuns.map((r, i) => (
            <li key={r.name} className={`${i === sel ? 'sel' : ''} ${r.world === 'two_buildings' ? 'w2' : 'w1'}`}>
              <button onClick={() => setSel(i)} aria-pressed={i === sel}>
                <span className="bar-name">{r.name}</span>
                <span className="bar-track"><span className="bar-fill" style={{ width: `${scale(r[metric]) * 100}%` }} /></span>
                <span className="bar-val">{r[metric]}{m.unit}</span>
              </button>
            </li>
          ))}
        </ol>
        <p className="legend small">
          <span className="w1"><i />campus_area world</span>
          <span className="w2"><i />two_buildings world</span>
        </p>
      </div>
      <div className="evo-right" aria-live="polite">
        <h4><code>{run.name}</code> <span className="muted">· {run.world} · {run.date}</span></h4>
        <dl className="kv">
          <div><dt>Markers</dt><dd>{run.markers}</dd></div>
          <div><dt>Abs. error</dt><dd>{run.abs} m</dd></div>
          <div><dt>Shape error</dt><dd>{run.shape} m</dd></div>
          <div><dt>Rotation</dt><dd>{run.rot}°</dd></div>
          <div><dt>Path</dt><dd>{run.path} m</dd></div>
          <div><dt>Sim time</dt><dd>{run.min} min</dd></div>
        </dl>
        <p>{run.note}</p>
        <Figure src={fig(run.img)} caption={run.img === 'evo_campus_area.png' ? 'campus_area maps in order (green walls were seen by the camera).' : run.img === 'evo_two_buildings.png' ? 'two_buildings maps in order.' : run.name + ' map figure from Report 6.'} />
      </div>
    </div>
  )
}
