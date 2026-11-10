import { useEffect, useState } from 'react';
import { getRobotStatus } from './api';

// Live state of the robot / Gazebo simulation, polled through the backend.
function RobotLiveStatus({ intervalMs = 1000 }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;

    const load = async () => {
      try {
        const data = await getRobotStatus();
        if (active) {
          setStatus(data);
          setError('');
        }
      } catch (err) {
        if (active) {
          setError(err.message || 'Backend not reachable');
        }
      }
    };

    load();
    const timer = setInterval(load, intervalMs);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [intervalMs]);

  const online = status && status.status === 'online';
  const current = status?.currentOrders || [];
  const waiting = status?.queue || [];

  return (
    <div className="robot-status-card robot-live-status">
      <p>
        <strong>Robot:</strong>{' '}
        {error
          ? `backend error (${error})`
          : !status
            ? 'loading...'
            : online
              ? `${status.simulation ? 'Gazebo simulation' : 'online'}, ${status.state || 'ready'}`
              : 'offline (check Robot Settings and that the robot / web_bridge is running)'}
      </p>

      {online && status.pose && (
        <p>
          <strong>Pose:</strong> x {status.pose.x.toFixed(2)} m, y {status.pose.y.toFixed(2)} m,{' '}
          {status.pose.yawDeg.toFixed(0)}&deg;
        </p>
      )}

      {online && (
        <p>
          <strong>Current:</strong>{' '}
          {current.length
            ? current
                .map((j) => `${j.orderID ? `#${j.orderID}` : 'job'} → ${j.deliveryPoint} (${j.status})`)
                .join(', ')
            : 'none'}
          {waiting.length > 0 && (
            <>
              <br />
              <strong>Waiting:</strong>{' '}
              {waiting.map((j) => `${j.orderID ? `#${j.orderID}` : 'job'} → ${j.deliveryPoint}`).join(', ')}
            </>
          )}
        </p>
      )}

      {online && status.lastMessage && (
        <p className="robot-last-message">
          <strong>Last message:</strong> {status.lastMessage}
        </p>
      )}
    </div>
  );
}

export default RobotLiveStatus;
