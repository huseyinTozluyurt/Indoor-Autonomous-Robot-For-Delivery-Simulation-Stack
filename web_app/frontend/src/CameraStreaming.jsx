import { useCallback, useEffect, useRef, useState } from 'react';
import { driveRobot, getRobotCameraStreamUrl } from './api';
import CampusMap, { useCampusMap, useRobotStatus } from './CampusMap';
import { prettyPoint } from './campusPoints';

const KEYS = { ArrowUp: 'FORWARD', ArrowDown: 'BACKWARD', ArrowLeft: 'LEFT', ArrowRight: 'RIGHT',
               w: 'FORWARD', s: 'BACKWARD', a: 'LEFT', d: 'RIGHT' };

// Admin: live robot camera (Gazebo simulation or the real robot), live position on
// the campus map, and manual control. "Take control" pauses the running delivery;
// "Release" gives the robot back and it continues its deliveries.
function CameraStreaming() {
  const [cameraStreamURL, setCameraStreamURL] = useState('');
  const [streamError, setStreamError] = useState(false);
  const [streamKey, setStreamKey] = useState(0);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [held, setHeld] = useState(null);
  const status = useRobotStatus(700);
  const { info } = useCampusMap();
  const timer = useRef(null);

  useEffect(() => {
    getRobotCameraStreamUrl()
      .then(setCameraStreamURL)
      .catch(() => setStreamError(true));
  }, []);

  const online = status && status.status !== 'offline';
  const manual = !!(status && status.manual);
  const onDelivery = online && ((status.currentOrders || []).length > 0 || (status.queue || []).length > 0);
  const canDrive = online && (manual || !onDelivery);

  const send = useCallback(async (cmd) => {
    try {
      await driveRobot(cmd);
      setError('');
    } catch (e) {
      setError(e.message);
    }
  }, []);

  const startDrive = useCallback((cmd) => {
    if (!canDrive) return;
    clearInterval(timer.current);
    setHeld(cmd);
    send(cmd);
    timer.current = setInterval(() => send(cmd), 350);   // keep moving while held
  }, [canDrive, send]);

  const stopDrive = useCallback(() => {
    if (!timer.current) return;
    clearInterval(timer.current);
    timer.current = null;
    setHeld(null);
    send('STOP');
  }, [send]);

  // keyboard: arrows / WASD while held, space = stop
  useEffect(() => {
    const down = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      const cmd = KEYS[e.key];
      if (cmd) {
        e.preventDefault();
        if (!e.repeat) startDrive(cmd);
      } else if (e.key === ' ') {
        e.preventDefault();
        stopDrive();
        send('STOP');
      }
    };
    const up = (e) => {
      if (KEYS[e.key]) stopDrive();
    };
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    window.addEventListener('blur', stopDrive);
    return () => {
      window.removeEventListener('keydown', down);
      window.removeEventListener('keyup', up);
      window.removeEventListener('blur', stopDrive);
    };
  }, [startDrive, stopDrive, send]);

  useEffect(() => () => clearInterval(timer.current), []);

  const takeControl = async () => {
    setMessage('');
    try {
      await driveRobot('TAKEOVER');
      setMessage(onDelivery
        ? 'You have control. The delivery is paused and continues when you release the robot.'
        : 'You have control of the robot.');
    } catch (e) {
      setError(e.message);
    }
  };

  const release = async () => {
    stopDrive();
    try {
      const res = await driveRobot('RELEASE');
      setMessage(res.resuming ? `Released: the robot continues ${res.resuming} deliveries.` : 'Released the robot.');
    } catch (e) {
      setError(e.message);
    }
  };

  const pad = (cmd, label) => (
    <button type="button" className={`pad-btn${held === cmd ? ' held' : ''}`} disabled={!canDrive}
            onPointerDown={(e) => { e.preventDefault(); startDrive(cmd); }}
            onPointerUp={stopDrive} onPointerLeave={stopDrive} onPointerCancel={stopDrive}>
      {label}
    </button>
  );

  const current = (status?.currentOrders || []).map((o) => `${o.orderID} → ${prettyPoint(o.deliveryPoint)}`);

  return (
    <div className="camera-streaming-page">
      <h1>Camera Streaming</h1>
      <p>Live camera of the robot, its position on the campus map, and manual control.</p>

      <div className="camera-layout">
        <div className="card camera-card">
          <div className="camera-stream-box">
            {cameraStreamURL && !streamError ? (
              <img key={streamKey} src={cameraStreamURL} alt="Robot camera" className="camera-stream"
                   onError={() => setStreamError(true)} />
            ) : (
              <div className="camera-error-box">
                <h2>Camera stream unavailable</h2>
                <p>Start the simulation (or the robot) and check the address in Robot Settings.</p>
                <code>{cameraStreamURL || 'No camera URL configured yet'}</code>
                <br />
                <button type="button" className="secondary-btn"
                        onClick={() => { setStreamError(false); setStreamKey((k) => k + 1); }}>
                  Retry
                </button>
              </div>
            )}
          </div>
          <div className="camera-caption">
            {online ? (
              <>
                <strong>{status.state}</strong>
                {status.pose && ` · x ${status.pose.x.toFixed(1)} m, y ${status.pose.y.toFixed(1)} m, ${Math.round(status.pose.yawDeg)}°`}
                {current.length > 0 && ` · ${current.join(', ')}`}
              </>
            ) : 'Robot offline'}
          </div>
        </div>

        <div className="card control-card">
          <h2>Manual control</h2>
          <div className={`control-mode ${manual ? 'manual' : 'auto'}`}>
            {manual ? 'You are driving the robot' : onDelivery ? 'Robot is delivering (autonomous)' : 'Robot is idle'}
          </div>
          {manual ? (
            <button type="button" className="release-btn" onClick={release}>Release robot (resume deliveries)</button>
          ) : (
            <button type="button" className="takeover-btn" disabled={!online} onClick={takeControl}>
              Take control
            </button>
          )}

          <div className="dpad">
            <span />{pad('FORWARD', '▲')}<span />
            {pad('LEFT', '◀')}
            <button type="button" className="pad-btn stop" disabled={!online} onClick={() => { stopDrive(); send('STOP'); }}>■</button>
            {pad('RIGHT', '▶')}
            <span />{pad('BACKWARD', '▼')}<span />
          </div>
          <p className="hint">
            Hold a button, or the arrow keys / W A S D, to drive. Space stops.
            {!canDrive && online && ' Take control first: the robot is on a delivery.'}
          </p>
          <button type="button" className="danger-btn" disabled={!online}
                  onClick={() => { stopDrive(); send('EMERGENCY_STOP'); }}>
            Emergency stop
          </button>
          {message && <div className="success-text">{message}</div>}
          {error && <div className="error-text">{error}</div>}
        </div>
      </div>

      <div className="card">
        <h2>Robot on the campus map</h2>
        <CampusMap info={info} status={status} />
      </div>
    </div>
  );
}

export default CameraStreaming;
