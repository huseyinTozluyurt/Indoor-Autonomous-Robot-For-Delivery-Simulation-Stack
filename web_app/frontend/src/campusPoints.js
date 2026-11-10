// Readable names for the delivery points of the map:
// "r_delivery_point_1" -> "R · Delivery Point 1", "c_table_north" -> "C · Table North"
export function prettyPoint(name) {
  if (!name) return '';
  if (name === 'home') return 'Starting Point (Home)';
  const parts = String(name).split('_').filter(Boolean);
  let prefix = '';
  if (parts.length > 1 && parts[0].length === 1) {
    prefix = parts.shift().toUpperCase() + ' · ';
  }
  return prefix + parts.map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(' ');
}

// Group letter of a point ("r_delivery_point_1" -> "R"), used for colours
export function pointGroup(name) {
  const first = String(name || '').split('_')[0];
  return first.length === 1 ? first.toUpperCase() : '';
}

const GROUP_COLORS = ['#00754a', '#1f6feb', '#b7410e', '#8250df', '#bf8700', '#0a7e8c'];

export function groupColor(name) {
  const g = pointGroup(name);
  if (!g) return '#00754a';
  return GROUP_COLORS[(g.charCodeAt(0) - 65 + GROUP_COLORS.length * 10) % GROUP_COLORS.length];
}
