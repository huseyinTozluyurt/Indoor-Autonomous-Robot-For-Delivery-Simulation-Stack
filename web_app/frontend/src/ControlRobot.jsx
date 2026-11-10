import { useEffect, useState } from 'react';
import { getRobotPoints, sendDeliveryCommand, sendRobotCommand } from './api';
import RobotLiveStatus from './RobotLiveStatus';
import CampusMap, { useCampusMap, useRobotStatus } from './CampusMap';

// All commands go through the Spring Boot backend, which forwards them to the
// robot server set in Robot Settings (Raspberry Pi or the Gazebo web_bridge).
function ControlRobot() {
  const [lastCommand, setLastCommand] = useState('');
  const [connectionStatus, setConnectionStatus] = useState('Not connected');
  const [points, setPoints] = useState([]);

  useEffect(() => {
    getRobotPoints()
      .then((data) => setPoints(Array.isArray(data) ? data : []))
      .catch(() => setPoints([]));
  }, []);

  const runCommand = async (command) => {
    setLastCommand(command);

    try {
      await sendRobotCommand(command);
      setConnectionStatus('Command sent successfully');
    } catch (error) {
      console.error('Failed to send robot command:', error);
      setConnectionStatus(`Command failed: ${error.message}`);
    }
  };

  const sendDeliveryTarget = async (point) => {
    try {
      await sendDeliveryCommand({
        orderID: null,
        tableNumber: null,
        targetArucoId: point.markerId,
        route: point.name,
      });

      setLastCommand(`Go to ${point.name}`);
      setConnectionStatus('Delivery target sent successfully');
    } catch (error) {
      console.error('Failed to send delivery target:', error);
      setConnectionStatus(`Failed to send delivery target: ${error.message}`);
    }
  };

  const deliveryPoints = points.filter((p) => p.name !== 'home');
  const { info: mapInfo } = useCampusMap();
  const robot = useRobotStatus(1000);
  const homePoint = points.find((p) => p.name === 'home');
  const start = mapInfo?.home || (homePoint ? { x: homePoint.x, y: homePoint.y } : null);
  const online = robot && robot.status !== 'offline';
  const busy = online && ((robot.currentOrders || []).length > 0 || (robot.queue || []).length > 0);
  const returning = online && String(robot.state || '').startsWith('returning');
  const distance = online && robot.pose && start
    ? Math.hypot(robot.pose.x - start.x, robot.pose.y - start.y)
    : null;

  const returnNow = () => {
    if (busy && !window.confirm('Stop the current delivery and drive back to the starting point now? '
      + 'The orders on the robot go back to the operator as Cancelled.')) {
      return;
    }
    runCommand('RETURN_HOME_NOW');
  };

  return (
    <div className="robot-control-page">
      <h1>Robot Control Panel</h1>
      <p>Manual control and delivery commands for the indoor delivery robot (real or Gazebo).</p>

      <RobotLiveStatus />

      <div className="robot-status-card">
        <p>
          <strong>Status:</strong> {connectionStatus}
        </p>
        <p>
          <strong>Last Command:</strong> {lastCommand || 'No command sent yet'}
        </p>
      </div>

      <div className="manual-control-section">
        <h2>Manual Movement Control</h2>

        <div className="control-grid">
          <div></div>

          <button type="button" className="control-btn" onClick={() => runCommand('FORWARD')}>
            Forward
          </button>

          <div></div>

          <button type="button" className="control-btn" onClick={() => runCommand('LEFT')}>
            Left
          </button>

          <button
            type="button"
            className="control-btn stop-btn"
            onClick={() => runCommand('STOP')}
          >
            Stop
          </button>

          <button type="button" className="control-btn" onClick={() => runCommand('RIGHT')}>
            Right
          </button>

          <div></div>

          <button type="button" className="control-btn" onClick={() => runCommand('BACKWARD')}>
            Backward
          </button>

          <div></div>
        </div>
      </div>

      <div className="start-point-section card">
        <div className="start-point-info">
          <h2>Starting point</h2>
          <p>
            The robot's initial position on the campus
            {start ? <> at <strong>x {start.x.toFixed(1)} m, y {start.y.toFixed(1)} m</strong></> : ''}
            {' '}(the <strong>H</strong> on the map).
          </p>
          <p>
            {!online ? 'Robot offline.'
              : returning ? 'The robot is driving back to the starting point…'
              : distance != null && distance < 0.6 ? 'The robot is at the starting point.'
              : distance != null ? `The robot is ${distance.toFixed(1)} m away from it${busy ? ' and on a delivery' : ''}.`
              : ''}
          </p>
          <div className="start-point-buttons">
            <button type="button" className="return-start-btn" disabled={!online} onClick={returnNow}>
              {busy ? 'Return to Starting Point now' : 'Return to Starting Point'}
            </button>
            {busy && (
              <button type="button" className="secondary-btn" onClick={() => runCommand('RETURN_BASE')}>
                After the current deliveries
              </button>
            )}
          </div>
          {busy && (
            <p className="hint">“Now” stops the delivery; its orders go back to the operator as Cancelled.</p>
          )}
        </div>
        <div className="start-point-map">
          <CampusMap info={mapInfo} status={robot} selected="home" />
        </div>
      </div>

      <div className="delivery-control-section">
        <h2>Delivery Test Commands</h2>
        <p>
          {deliveryPoints.length
            ? 'Delivery points reported by the robot (ArUco marker ID in brackets).'
            : 'No delivery points: the robot / simulation bridge is not reachable.'}
        </p>

        <div className="delivery-button-container">
          {deliveryPoints.map((point) => (
            <button key={point.name} type="button" onClick={() => sendDeliveryTarget(point)}>
              {point.name}
              {point.markerId != null ? ` (${point.markerId})` : ''}
            </button>
          ))}

          <button type="button" onClick={() => runCommand('SET_HOME_POSE')}>
            Pose = Home
          </button>

          <button type="button" onClick={() => runCommand('RELOCALIZE')}>
            Find Pose (markers)
          </button>
        </div>
      </div>

      <div className="emergency-section">
        <button
          type="button"
          className="emergency-stop-btn"
          onClick={() => runCommand('EMERGENCY_STOP')}
        >
          Emergency Stop
        </button>
      </div>
    </div>
  );
}

export default ControlRobot;
