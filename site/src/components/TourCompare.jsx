import { useState } from 'react'
import { tour } from '../data.js'

const short = (s) => s.replace('_delivery_point_', ' · pt ').replace('c_table_north', 'c · table N').replace(/^([abr]) /, (m) => m.toUpperCase())

export default function TourCompare() {
  const [k, setK] = useState('optimal')
  const t = tour[k]
  const max = tour.arrival.cost
  return (
    <div className="tour">
      <div className="seg" role="tablist" aria-label="Visiting order">
        <button role="tab" aria-selected={k === 'arrival'} className={k === 'arrival' ? 'on' : ''} onClick={() => setK('arrival')}>Order of arrival</button>
        <button role="tab" aria-selected={k === 'optimal'} className={k === 'optimal' ? 'on' : ''} onClick={() => setK('optimal')}>Held-Karp optimum</button>
      </div>
      <ol className="chain" aria-label={`${t.label} visiting order`}>
        {t.stops.map((s, i) => (
          <li key={i}>
            {i > 0 && <span className="chain-arr" aria-hidden="true">→</span>}
            <span className={`chip ${s === 'home' ? 'home' : ''}`}>{s === 'home' ? 'home' : short(s)}</span>
          </li>
        ))}
      </ol>
      <div className="cost">
        <div className="cost-row">
          <span>Order of arrival</span>
          <span className="cost-track"><span className="cost-fill a" style={{ width: '100%' }} /></span>
          <span className="num">290.7</span>
        </div>
        <div className="cost-row">
          <span>Held-Karp</span>
          <span className="cost-track"><span className={`cost-fill b ${k === 'optimal' ? 'hl' : ''}`} style={{ width: `${(tour.optimal.cost / max) * 100}%` }} /></span>
          <span className="num">176.0</span>
        </div>
        <p className="muted small">Tour cost in cost-weighted metres, start and end at home, six stops on campus_full_map7.</p>
      </div>
    </div>
  )
}
