// Shared order status helpers (shop, operator and admin pages)
export const STEPS = ['Preparing', 'Delivering', 'Delivered'];

export function StatusBadge({ status }) {
  const s = status || 'Pending';
  return <span className={`order-status ${s.toLowerCase()}`}>{s}</span>;
}

// Preparing -> Delivering -> Delivered progress line
export function StatusSteps({ status }) {
  const failed = ['Failed', 'Cancelled'].includes(status);
  let index = STEPS.indexOf(status);
  if (status === 'Dispatched') index = 1;
  if (status === 'Pending') index = 0;
  return (
    <div className={`status-steps${failed ? ' failed' : ''}`}>
      {STEPS.map((step, i) => (
        <div key={step} className={`status-step${i <= index ? ' done' : ''}${i === index ? ' current' : ''}`}>
          <span className="status-step-dot" />
          <span className="status-step-label">{step}</span>
        </div>
      ))}
      {failed && <div className="status-step-failed">{status}</div>}
    </div>
  );
}

export function itemsText(order) {
  return (order.items || []).map((i) => `${i.quantity}× ${i.productName}`).join(', ');
}

export function money(v) {
  return `₺${Number(v || 0).toFixed(2)}`;
}
