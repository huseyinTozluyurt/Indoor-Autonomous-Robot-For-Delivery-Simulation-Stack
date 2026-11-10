import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getLoggedInUser, getMyOrders, getProducts, placeOrder } from './api';
import CampusMap, { useCampusMap, useRobotStatus } from './CampusMap';
import { prettyPoint } from './campusPoints';
import { itemsText, money, StatusBadge, StatusSteps } from './orderStatus';

// User page: choose products, choose the delivery point on the campus map, order,
// and follow the order (Preparing -> Delivering -> Delivered) live.
function ShopPage() {
  const navigate = useNavigate();
  const user = getLoggedInUser();
  const [products, setProducts] = useState([]);
  const [cart, setCart] = useState({});
  const [point, setPoint] = useState('');
  const [note, setNote] = useState('');
  const [orders, setOrders] = useState([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [category, setCategory] = useState('All');
  const { info, error: mapError } = useCampusMap();
  const status = useRobotStatus(1500);

  useEffect(() => {
    if (!user) {
      navigate('/');
      return;
    }
    getProducts().then(setProducts).catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!user) return undefined;
    const load = () => getMyOrders(user.id).then(setOrders).catch(() => {});
    load();
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const categories = useMemo(
    () => ['All', ...new Set(products.map((p) => p.category || 'Other'))],
    [products],
  );
  const shown = products.filter((p) => category === 'All' || (p.category || 'Other') === category);
  const cartLines = products.filter((p) => cart[p.id] > 0);
  const total = cartLines.reduce((s, p) => s + p.price * cart[p.id], 0);
  const points = (info?.points || []).filter((p) => p.name !== 'home');

  const change = (id, d) =>
    setCart((c) => {
      const q = Math.max(0, Math.min(20, (c[id] || 0) + d));
      return { ...c, [id]: q };
    });

  const submit = async () => {
    setError('');
    setMessage('');
    if (!cartLines.length) {
      setError('Add a product to the cart first.');
      return;
    }
    if (!point) {
      setError('Choose your delivery point on the campus map.');
      return;
    }
    setBusy(true);
    try {
      const order = await placeOrder({
        userId: user.id,
        deliveryPoint: point,
        arucoId: points.find((p) => p.name === point)?.markerId ?? null,
        note,
        items: cartLines.map((p) => ({ productId: p.id, quantity: cart[p.id] })),
      });
      setCart({});
      setNote('');
      setMessage(`Order ${order.orderID} received. It is being prepared; the robot brings it to ${prettyPoint(point)}.`);
      setOrders((o) => [order, ...o.filter((x) => x.id !== order.id)]);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!user) return null;

  const robotOn = status && status.status !== 'offline';

  return (
    <div className="shop-page">
      <div className="shop-header">
        <div>
          <h1>Order to your spot on campus</h1>
          <p>Hi {user.name}! Pick your products, choose where you are on the map, and the robot brings them.</p>
        </div>
        <div className={`robot-pill ${robotOn ? 'on' : 'off'}`}>
          Robot: {robotOn ? status.state || 'online' : 'offline'}
        </div>
      </div>

      <div className="shop-layout">
        <section className="shop-products">
          <div className="category-tabs">
            {categories.map((c) => (
              <button key={c} type="button" className={c === category ? 'active' : ''}
                      onClick={() => setCategory(c)}>{c}</button>
            ))}
          </div>
          <div className="product-grid">
            {shown.map((p) => (
              <div key={p.id} className={`product-card${cart[p.id] ? ' in-cart' : ''}`}>
                <div className="product-icon">{p.icon || '🛍️'}</div>
                <div className="product-name">{p.name}</div>
                <div className="product-desc">{p.description}</div>
                <div className="product-bottom">
                  <span className="product-price">{money(p.price)}</span>
                  {cart[p.id] ? (
                    <div className="qty">
                      <button type="button" onClick={() => change(p.id, -1)}>−</button>
                      <span>{cart[p.id]}</span>
                      <button type="button" onClick={() => change(p.id, 1)}>+</button>
                    </div>
                  ) : (
                    <button type="button" onClick={() => change(p.id, 1)}>Add</button>
                  )}
                </div>
              </div>
            ))}
            {!products.length && <p>No products yet.</p>}
          </div>
        </section>

        <aside className="shop-side">
          <div className="card">
            <h2>1. Your cart</h2>
            {cartLines.length ? (
              <ul className="cart-list">
                {cartLines.map((p) => (
                  <li key={p.id}>
                    <span>{p.icon} {cart[p.id]}× {p.name}</span>
                    <span>{money(p.price * cart[p.id])}</span>
                  </li>
                ))}
                <li className="cart-total"><span>Total</span><span>{money(total)}</span></li>
              </ul>
            ) : (
              <p>The cart is empty.</p>
            )}
          </div>

          <div className="card">
            <h2>2. Delivery point</h2>
            {mapError ? (
              <p className="error-text">Campus map not available: {mapError}. Is the robot / simulation running?</p>
            ) : (
              <CampusMap info={info} status={status} selected={point} onSelect={setPoint} />
            )}
            <select value={point} onChange={(e) => setPoint(e.target.value)}>
              <option value="">Click a point on the map or choose here…</option>
              {points.map((p) => (
                <option key={p.name} value={p.name}>{prettyPoint(p.name)}</option>
              ))}
            </select>
            <input type="text" placeholder="Note for the operator (optional)" value={note}
                   onChange={(e) => setNote(e.target.value)} maxLength={200} />
          </div>

          <button type="button" className="place-order-btn" disabled={busy} onClick={submit}>
            {busy ? 'Placing order…' : `Place order${cartLines.length ? ` · ${money(total)}` : ''}`}
          </button>
          {message && <div className="success-text">{message}</div>}
          {error && <div className="error-text">{error}</div>}
        </aside>
      </div>

      <section className="my-orders">
        <h2>My orders</h2>
        {!orders.length && <p>You have no orders yet.</p>}
        <div className="my-orders-list">
          {orders.map((o) => (
            <div key={o.id} className="my-order card">
              <div className="my-order-top">
                <strong>{o.orderID}</strong>
                <StatusBadge status={o.status} />
              </div>
              <div className="my-order-items">{itemsText(o) || '-'}</div>
              <div className="my-order-meta">
                {prettyPoint(o.deliveryPoint) || '-'} · {money(o.totalPrice)} ·{' '}
                {o.createdAt ? new Date(o.createdAt).toLocaleString() : ''}
              </div>
              <StatusSteps status={o.status} />
              {o.robotMessage && <div className="my-order-msg">{o.robotMessage}</div>}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export default ShopPage;
