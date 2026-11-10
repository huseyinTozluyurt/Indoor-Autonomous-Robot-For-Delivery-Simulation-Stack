const API_BASE_URL = 'http://localhost:8080/api';

// Best readable error message from a failed backend response
async function errorText(response, fallback) {
  try {
    const text = await response.text();
    try {
      const data = JSON.parse(text);
      let message = data.message || data.error || text;
      if (typeof message === 'string' && message.trim().startsWith('{')) {
        const inner = JSON.parse(message);
        message = inner.error || inner.message || message;
      }
      if (data.robotResponse && typeof data.robotResponse === 'string') {
        message = `${message}: ${data.robotResponse}`;
      }
      return message || fallback;
    } catch {
      return text || fallback;
    }
  } catch {
    return fallback;
  }
}


// =====================
// Auth
// =====================

export async function loginUser(email, password) {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ email, password })
  });

  if (!response.ok) {
    throw new Error('Login failed');
  }

  return response.json();
}

export async function registerUser(userData) {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(userData)
  });

  if (!response.ok) {
    throw new Error('Registration failed');
  }

  return response.json();
}

// =====================
// Tables
// =====================

export async function getTables() {
  const response = await fetch(`${API_BASE_URL}/tables`);

  if (!response.ok) {
    throw new Error('Failed to fetch tables');
  }

  return response.json();
}

export async function saveTables(tables) {
  const response = await fetch(`${API_BASE_URL}/tables/bulk`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(tables)
  });

  if (!response.ok) {
    throw new Error('Failed to save tables');
  }

  return response.json();
}

export async function updateTable(id, table) {
  const response = await fetch(`${API_BASE_URL}/tables/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(table)
  });

  if (!response.ok) {
    throw new Error('Failed to update table');
  }

  return response.json();
}

export async function deleteTable(id) {
  const response = await fetch(`${API_BASE_URL}/tables/${id}`, {
    method: 'DELETE'
  });

  if (!response.ok) {
    throw new Error('Failed to delete table');
  }
}

// =====================
// Orders
// =====================

export async function getOrders() {
  const response = await fetch(`${API_BASE_URL}/orders`);

  if (!response.ok) {
    throw new Error('Failed to fetch orders');
  }

  return response.json();
}




export async function createOrder(order) {
  const response = await fetch(`${API_BASE_URL}/orders`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(order)
  });

  if (!response.ok) {
    throw new Error(await errorText(response, 'Failed to create order'));
  }

  return response.json();
}


// Send an order to the robot (Raspberry Pi or the Gazebo simulation)
export async function dispatchOrder(id) {
  const response = await fetch(`${API_BASE_URL}/orders/${id}/dispatch`, {
    method: 'POST'
  });

  if (!response.ok) {
    throw new Error(await errorText(response, 'Failed to send order to robot'));
  }

  return response.json();
}

export async function updateOrderStatus(id, status) {
  const response = await fetch(`${API_BASE_URL}/orders/${id}/status`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ status })
  });

  if (!response.ok) {
    throw new Error('Failed to update order status');
  }

  return response.json();
}

export async function deleteOrder(id) {
  const response = await fetch(`${API_BASE_URL}/orders/${id}`, {
    method: 'DELETE'
  });

  if (!response.ok) {
    throw new Error('Failed to delete order');
  }
}

export async function clearOrders() {
  const response = await fetch(`${API_BASE_URL}/orders`, {
    method: 'DELETE'
  });

  if (!response.ok) {
    throw new Error('Failed to clear orders');
  }
}

// =====================
// Robot Commands
// =====================

export async function sendRobotCommand(command) {
  const response = await fetch(`${API_BASE_URL}/robot/commands`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ command })
  });

  if (!response.ok) {
    throw new Error(await errorText(response, 'Failed to send robot command'));
  }

  return response.json();
}

export async function sendDeliveryCommand(deliveryCommand) {
  const response = await fetch(`${API_BASE_URL}/robot/delivery`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(deliveryCommand)
  });

  if (!response.ok) {
    throw new Error('Failed to send delivery command');
  }

  return response.json();
}

// =====================
// Robot Sensors
// =====================

export async function getLatestRobotSensorData() {
  const response = await fetch(`${API_BASE_URL}/robot/sensors/latest`);

  if (!response.ok) {
    throw new Error('Failed to fetch latest robot sensor data');
  }

  return response.json();
}

// The stream comes straight from the robot server (Raspberry Pi or the Gazebo
// web_bridge), whose address is stored in Robot Settings.
export async function getRobotCameraStreamUrl() {
  const response = await fetch(`${API_BASE_URL}/robot/camera-url`);

  if (!response.ok) {
    throw new Error('Failed to fetch camera stream URL');
  }

  const data = await response.json();
  return data.url;
}

// Live robot state: {status: 'online'|'offline', state, pose, currentOrders, queue, lastMessage, log}
export async function getRobotStatus() {
  const response = await fetch(`${API_BASE_URL}/robot/status`);

  if (!response.ok) {
    throw new Error('Failed to fetch robot status');
  }

  return response.json();
}

// Delivery points known to the robot (simulation: from the SLAM map)
export async function getRobotPoints() {
  const response = await fetch(`${API_BASE_URL}/robot/points`);

  if (!response.ok) {
    throw new Error(await errorText(response, 'Failed to fetch delivery points'));
  }

  return response.json();
}

export async function getRobotConfig() {
  const response = await fetch(`${API_BASE_URL}/robot/config`);

  if (!response.ok) {
    throw new Error('Failed to fetch robot config');
  }

  return response.json();
}

export async function updateRobotConfig(config) {
  const response = await fetch(`${API_BASE_URL}/robot/config`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(config),
  });

  if (!response.ok) {
    throw new Error('Failed to update robot config');
  }

  return response.json();
}
export async function getMaps() {
  const response = await fetch(`${API_BASE_URL}/maps`);

  if (!response.ok) {
    throw new Error('Failed to fetch maps');
  }

  return response.json();
}



export async function getActiveMap() {
  const response = await fetch(`${API_BASE_URL}/maps/active`);

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error('Failed to fetch active map');
  }

  return response.json();
}


export async function createMap(mapData) {
  const response = await fetch(`${API_BASE_URL}/maps`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(mapData),
  });

  if (!response.ok) {
    throw new Error('Failed to create map');
  }

  return response.json();
}

export async function updateMap(id, mapData) {
  const response = await fetch(`${API_BASE_URL}/maps/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(mapData),
  });

  if (!response.ok) {
    throw new Error('Failed to update map');
  }

  return response.json();
}

export async function activateMap(id) {
  const response = await fetch(`${API_BASE_URL}/maps/${id}/activate`, {
    method: 'PUT',
  });

  if (!response.ok) {
    throw new Error('Failed to activate map');
  }

  return response.json();
}

export async function deleteMap(id) {
  const response = await fetch(`${API_BASE_URL}/maps/${id}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error('Failed to delete map');
  }
}

export async function getAdminUsers() {
  const response = await fetch(`${API_BASE_URL}/admin/users`);

  if (!response.ok) {
    throw new Error(await errorText(response, 'Failed to fetch users'));
  }

  return response.json();
}

export async function createAdminUser(userData) {
  const response = await fetch(`${API_BASE_URL}/admin/users`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(userData)
  });

  if (!response.ok) {
    throw new Error(await errorText(response, 'Failed to create user'));
  }

  return response.json();
}

export async function updateAdminUserRole(id, role) {
  const response = await fetch(`${API_BASE_URL}/admin/users/${id}/role`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ role })
  });

  if (!response.ok) {
    throw new Error(await errorText(response, 'Failed to update user role'));
  }

  return response.json();
}

export async function deleteAdminUser(id) {
  const response = await fetch(`${API_BASE_URL}/admin/users/${id}`, {
    method: 'DELETE'
  });

  if (!response.ok) {
    throw new Error(await errorText(response, 'Failed to delete user'));
  }
}
// =====================
// Shop: products and product orders
// =====================

export async function getProducts(all = false) {
  const response = await fetch(`${API_BASE_URL}/products${all ? '?all=true' : ''}`);

  if (!response.ok) {
    throw new Error(await errorText(response, 'Failed to fetch products'));
  }

  return response.json();
}

async function postJson(path, body, fallback) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(await errorText(response, fallback));
  }

  return response.json();
}

// {userId, deliveryPoint, note, items: [{productId, quantity}]} -> order (status "Preparing")
export function placeOrder(order) {
  return postJson('/orders/place', order, 'Failed to place the order');
}

export async function getMyOrders(userId) {
  const response = await fetch(`${API_BASE_URL}/orders/user/${userId}`);

  if (!response.ok) {
    throw new Error(await errorText(response, 'Failed to fetch your orders'));
  }

  return response.json();
}

// Operator: the selected orders are in the robot -> one shortest delivery tour
export function dispatchBatch(orderIds) {
  return postJson('/orders/dispatch-batch', { orderIds }, 'Failed to start the delivery');
}

// =====================
// Campus map (from the robot's SLAM map)
// =====================

export async function getMapInfo() {
  const response = await fetch(`${API_BASE_URL}/robot/map-info`);

  if (!response.ok) {
    throw new Error(await errorText(response, 'Campus map not available'));
  }

  return response.json();
}

export function mapImageUrl(refresh = false) {
  return `${API_BASE_URL}/robot/map.png${refresh ? '?refresh=true' : ''}`;
}

// Dijkstra shortest tour preview: {stops: [...point names], end: 'home'}
export function planRoute(stops, end = 'home') {
  return postJson('/robot/plan', { stops, end }, 'Could not plan the route');
}

// Logged-in user stored by the login page
export function getLoggedInUser() {
  try {
    return JSON.parse(localStorage.getItem('loggedInUser') || 'null');
  } catch {
    return null;
  }
}

// Manual driving (not stored in the command history): FORWARD/BACKWARD/LEFT/RIGHT/STOP,
// TAKEOVER (admin takes control, deliveries pause) and RELEASE (deliveries resume)
export function driveRobot(command) {
  return postJson('/robot/drive', { command }, 'Robot did not accept the command');
}
