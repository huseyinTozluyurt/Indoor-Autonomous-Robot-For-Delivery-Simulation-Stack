import { useCallback, useEffect, useState } from 'react';
import {
  clearOrders,
  deleteOrder,
  dispatchOrder,
  getOrders,
  updateOrderStatus,
} from './api';
import RobotLiveStatus from './RobotLiveStatus';
import { prettyPoint } from './campusPoints';
import { itemsText, money } from './orderStatus';

const STATUSES = [
  'Pending',
  'Preparing',
  'Dispatched',
  'Delivering',
  'Delivered',
  'Failed',
  'Cancelled',
];

// Orders that can be (re)sent to the robot
const SENDABLE = ['Pending', 'Preparing', 'Failed', 'Cancelled'];

function ViewOrders() {
  const [orders, setOrders] = useState([]);
  const [statusMessage, setStatusMessage] = useState('');
  const [sendingId, setSendingId] = useState(null);

  const loadOrders = useCallback(async () => {
    try {
      const data = await getOrders();
      data.sort((a, b) => b.id - a.id);
      setOrders(data);
    } catch (error) {
      console.error('Failed to load orders:', error);
      setStatusMessage('Failed to load orders from the backend.');
    }
  }, []);

  // Orders change while the robot drives (Delivering -> Delivered), so refresh often
  useEffect(() => {
    loadOrders();
    const timer = setInterval(loadOrders, 2000);
    return () => clearInterval(timer);
  }, [loadOrders]);

  const handleStatusChange = async (id, newStatus) => {
    try {
      await updateOrderStatus(id, newStatus);
      loadOrders();
    } catch (error) {
      console.error(error);
      setStatusMessage('Failed to update order status.');
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteOrder(id);
      loadOrders();
    } catch (error) {
      console.error(error);
      setStatusMessage('Failed to delete order.');
    }
  };

  const handleClearAll = async () => {
    if (!window.confirm('Are you sure you want to delete all orders?')) {
      return;
    }

    try {
      await clearOrders();
      loadOrders();
    } catch (error) {
      console.error(error);
      setStatusMessage('Failed to clear orders.');
    }
  };

  const sendToRobot = async (order) => {
    setSendingId(order.id);
    try {
      const result = await dispatchOrder(order.id);
      const point = result?.robotResponse?.deliveryPoint;
      setStatusMessage(
        `Order ${order.orderID} sent to the robot${point ? ` (delivery point ${point})` : ''}.`
      );
    } catch (error) {
      console.error('Robot delivery command error:', error);
      setStatusMessage(`Order ${order.orderID} not sent: ${error.message}`);
    } finally {
      setSendingId(null);
      loadOrders();
    }
  };

  const sendAllPending = async () => {
    const pending = orders.filter((o) => o.status === 'Pending').reverse();
    for (const order of pending) {
      // one by one: the robot plans one shortest tour over all of them
      await sendToRobot(order);
    }
  };

  return (
    <div className="view-orders-page">
      <h1>View Orders</h1>
      <p>Monitor delivery orders and send them to the robot (real robot or Gazebo simulation).</p>

      <RobotLiveStatus />

      {statusMessage && <p className="robot-settings-status">{statusMessage}</p>}

      {orders.length === 0 ? (
        <div className="empty-orders-box">
          <h2>No orders found</h2>
          <p>Orders created from the Main Page will appear here.</p>
        </div>
      ) : (
        <>
          <div className="orders-actions">
            <button type="button" onClick={sendAllPending}>
              Send All Pending to Robot
            </button>
            <button type="button" className="clear-orders-btn" onClick={handleClearAll}>
              Clear All Orders
            </button>
          </div>

          <div className="orders-table-wrapper">
            <table className="orders-table">
              <thead>
                <tr>
                  <th>Order ID</th>
                  <th>Customer</th>
                  <th>Products</th>
                  <th>Delivery Point</th>
                  <th>ArUco ID</th>
                  <th>Status</th>
                  <th>Robot</th>
                  <th>Created At</th>
                  <th>Update Status</th>
                  <th>Send</th>
                  <th>Delete</th>
                </tr>
              </thead>

              <tbody>
                {orders.map((order) => {
                  const status = order.status || 'Pending';
                  return (
                    <tr key={order.id}>
                      <td>{order.orderID}</td>
                      <td>{order.customerName || '-'}</td>
                      <td>
                        {itemsText(order) || '-'}
                        {order.totalPrice != null && <><br /><small>{money(order.totalPrice)}</small></>}
                      </td>
                      <td>
                        {order.deliveryPoint
                          ? prettyPoint(order.deliveryPoint)
                          : order.tableNumber != null
                            ? `Table ${order.tableNumber}${order.rowNumber ? ` (row ${order.rowNumber}, col ${order.columnNumber})` : ''}`
                            : '-'}
                      </td>
                      <td>{order.arucoId ?? 'Not assigned'}</td>
                      <td>
                        <span className={`order-status ${status.toLowerCase()}`}>{status}</span>
                      </td>
                      <td className="order-robot-cell">
                        {order.robotMessage || '-'}
                      </td>
                      <td>{order.createdAt ? new Date(order.createdAt).toLocaleString() : '-'}</td>
                      <td>
                        <select
                          value={STATUSES.includes(status) ? status : 'Pending'}
                          onChange={(e) => handleStatusChange(order.id, e.target.value)}
                        >
                          {STATUSES.map((s) => (
                            <option key={s} value={s}>
                              {s}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <button
                          type="button"
                          disabled={sendingId === order.id || !SENDABLE.includes(status)}
                          onClick={() => sendToRobot(order)}
                        >
                          {sendingId === order.id ? 'Sending...' : 'Send to Robot'}
                        </button>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="delete-order-btn"
                          onClick={() => handleDelete(order.id)}
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

export default ViewOrders;
