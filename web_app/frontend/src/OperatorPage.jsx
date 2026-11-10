import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { dispatchBatch, getLoggedInUser, getOrders, planRoute, sendRobotCommand } from './api';
import CampusMap, { useCampusMap, useRobotStatus } from './CampusMap';
import { prettyPoint } from './campusPoints';
import { itemsText, money, StatusBadge } from './orderStatus';

const WAITING = ['Preparing', 'Pending', 'Failed', 'Cancelled'];
const ON_ROBOT = ['Dispatched', 'Delivering'];

// Robot operator: sees the orders being prepared, ticks the ones put into the
// robot, previews the Dijkstra shortest route and starts the delivery.
function OperatorPage() {
  const navigate = useNavigate();
  const user = getLoggedInUser();
  const [orders, setOrders] = useState([]);
  const [checked, setChecked] = useState(new Set());
  const [plan, setPlan] = useState(null);
  const [planError, setPlanError] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const { info, error: mapError } = useCampusMap();
  const status = useRobotStatus(1000);
  const planSeq = useRef(0);

  useEffect(() => {
    if (!user || !['OPERATOR', 'ADMIN'].includes(user.role)) {
      navigate('/');
      return undefined;
    }
    const load = () => getOrders().then(setOrders).catch((e) => setError(e.message));
    load();
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const waiting = useMemo(
    () => orders.filter((o) => WAITING.includes(o.status) && o.deliveryPoint)
      .sort((a, b) => a.id - b.id),
    [orders],
  );
  const onRobot = orders.filter((o) => ON_ROBOT.includes(o.status));
  const delivered = orders.filter((o) => o.status === 'Delivered').sort((a, b) => b.id - a.id).slice(0, 15);

  // drop ticks of orders that are no longer waiting
  useEffect(() => {
    setChecked((c) => {
      const ids = new Set(waiting.map((o) => o.id));
      const next = new Set([...c].filter((id) => ids.has(id)));
      return next.size === c.size ? c : next;
    });
  }, [waiting]);

  const selectedOrders = waiting.filter((o) => checked.has(o.id));
  const stops = [...new Set(selectedOrders.map((o) => o.deliveryPoint))];
  const stopsKey = stops.slice().sort().join('|');

  // Dijkstra preview whenever the set of stops changes
  useEffect(() => {
    setPlanError('');
    if (!stops.length) {
      setPlan(null);
      return undefined;
    }
    const seq = ++planSeq.current;
    const t = setTimeout(() => {
      planRoute(stops)
        .then((p) => seq === planSeq.current && setPlan(p))
        .catch((e) => {
          if (seq === planSeq.current) {
            setPlan(null);
            setPlanError(e.message);
          }
        });
    }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stopsKey]);

  const toggle = (id) =>
    setChecked((c) => {
      const n = new Set(c);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  const togglePoint = (name) => {
    const ids = waiting.filter((o) => o.deliveryPoint === name).map((o) => o.id);
    if (!ids.length) return;
    setChecked((c) => {
      const n = new Set(c);
      const all = ids.every((id) => n.has(id));
      ids.forEach((id) => (all ? n.delete(id) : n.add(id)));
      return n;
    });
  };

  const start = async () => {
    setError('');
    setMessage('');
    setBusy(true);
    try {
      const res = await dispatchBatch(selectedOrders.map((o) => o.id));
      setMessage(res.robotResponse?.message || 'Delivery started.');
      setChecked(new Set());
      setOrders(await getOrders());
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const command = async (cmd) => {
    setError('');
    try {
      await sendRobotCommand(cmd);
      setMessage(`${cmd.replace('_', ' ').toLowerCase()} sent`);
    } catch (e) {
      setError(e.message);
    }
  };

  const badges = {};
  waiting.forEach((o) => {
    badges[o.deliveryPoint] = (badges[o.deliveryPoint] || 0) + 1;
  });

  const online = status && status.status !== 'offline';
  const robotBusy = online && ((status.currentOrders || []).length || (status.queue || []).length);

  if (!user) return null;

  return (
    <div className="operator-page">
      <div className="shop-header">
        <div>
          <h1>Robot Operator</h1>
          <p>Tick the orders you put into the robot. The robot drives the shortest route (Dijkstra) through their delivery points and comes back to base.</p>
        </div>
        <div className={`robot-pill ${online ? 'on' : 'off'}`}>
          {online ? `Robot: ${status.state}${status.manual ? ' (admin control)' : ''}` : 'Robot offline'}
        </div>
      </div>

      <div className="operator-layout">
        <section className="card operator-orders">
          <div className="operator-orders-head">
            <h2>Preparing ({waiting.length})</h2>
            <div>
              <button type="button" className="secondary-btn"
                      onClick={() => setChecked(new Set(waiting.map((o) => o.id)))}>All</button>
              <button type="button" className="secondary-btn" onClick={() => setChecked(new Set())}>None</button>
            </div>
          </div>
          {!waiting.length && <p>No orders waiting. New orders from users appear here.</p>}
          <ul className="operator-order-list">
            {waiting.map((o) => (
              <li key={o.id} className={checked.has(o.id) ? 'checked' : ''}>
                <label>
                  <input type="checkbox" checked={checked.has(o.id)} onChange={() => toggle(o.id)} />
                  <div>
                    <div className="op-line1">
                      <strong>{o.orderID}</strong> <StatusBadge status={o.status} />
                      <span className="op-point">{prettyPoint(o.deliveryPoint)}</span>
                    </div>
                    <div className="op-items">{itemsText(o) || `Table ${o.tableNumber ?? '-'}`}</div>
                    <div className="op-meta">
                      {o.customerName || 'Guest'} · {money(o.totalPrice)}
                      {o.note ? ` · “${o.note}”` : ''}
                    </div>
                    {['Failed', 'Cancelled'].includes(o.status) && o.robotMessage && (
                      <div className="op-meta error-text">{o.robotMessage}</div>
                    )}
                  </div>
                </label>
              </li>
            ))}
          </ul>
        </section>

        <section className="card operator-map">
          <h2>Route</h2>
          {mapError ? (
            <p className="error-text">Campus map not available: {mapError}</p>
          ) : (
            <CampusMap info={info} status={status} selected={stops} onSelect={togglePoint}
                       badges={badges} previewPath={plan?.path} order={plan?.order} />
          )}

          {plan && (
            <div className="route-plan">
              <div className="route-order">
                <span className="route-stop home">Robot</span>
                {plan.order.map((n, i) => (
                  <span key={n} className="route-stop">{i + 1}. {prettyPoint(n)}</span>
                ))}
                <span className="route-stop home">Base</span>
              </div>
              <div className="route-total">
                Shortest tour: <strong>{plan.total} m</strong>
                {plan.givenOrderTotal > plan.total + 0.05 && (
                  <> (in order of arrival it would be {plan.givenOrderTotal} m)</>
                )}
              </div>
              <table className="route-legs">
                <tbody>
                  {plan.legs.map((l, i) => (
                    <tr key={i}>
                      <td>{prettyPoint(l.from === 'current position' ? 'robot' : l.from) || 'Robot'}</td>
                      <td>→</td>
                      <td>{prettyPoint(l.to)}</td>
                      <td>{l.length} m</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {planError && <p className="error-text">{planError}</p>}

          <button type="button" className="place-order-btn" disabled={busy || !selectedOrders.length || !online}
                  onClick={start}>
            {busy ? 'Starting…' : selectedOrders.length
              ? `Robot is loaded: deliver ${selectedOrders.length} order${selectedOrders.length > 1 ? 's' : ''} to ${stops.length} point${stops.length > 1 ? 's' : ''}`
              : 'Select the orders in the robot'}
          </button>
          {robotBusy ? <p className="hint">The robot is busy; the new delivery starts after the current one.</p> : null}
          {message && <div className="success-text">{message}</div>}
          {error && <div className="error-text">{error}</div>}
          <div className="operator-commands">
            <button type="button" className="secondary-btn" onClick={() => command('STOP')}>Stop</button>
            <button type="button" className="secondary-btn" onClick={() => command('RETURN_BASE')}>Return to base</button>
          </div>
        </section>
      </div>

      <div className="operator-layout">
        <section className="card">
          <h2>On the robot ({onRobot.length})</h2>
          {!onRobot.length && <p>Nothing on the robot.</p>}
          <ul className="simple-order-list">
            {onRobot.map((o) => (
              <li key={o.id}>
                <strong>{o.orderID}</strong> <StatusBadge status={o.status} /> {prettyPoint(o.deliveryPoint)}
                <div className="op-meta">{o.robotMessage}</div>
              </li>
            ))}
          </ul>
        </section>
        <section className="card">
          <h2>Delivered</h2>
          {!delivered.length && <p>No deliveries yet.</p>}
          <ul className="simple-order-list">
            {delivered.map((o) => (
              <li key={o.id}>
                <strong>{o.orderID}</strong> <StatusBadge status={o.status} /> {prettyPoint(o.deliveryPoint)}
                <span className="op-meta"> · {o.customerName || ''} · {o.updatedAt ? new Date(o.updatedAt).toLocaleTimeString() : ''}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}

export default OperatorPage;
