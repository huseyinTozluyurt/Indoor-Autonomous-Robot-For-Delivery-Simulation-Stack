import { useEffect, useState } from 'react';
import { getRobotConfig, getRobotPoints, getRobotStatus, updateRobotConfig } from './api';

function RobotSettings() {
  const [raspberryPiIp, setRaspberryPiIp] = useState('');
  const [raspberryPiPort, setRaspberryPiPort] = useState(5000);
  const [baseUrl, setBaseUrl] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [points, setPoints] = useState([]);

  useEffect(() => {
    loadRobotConfig();
  }, []);

  const loadRobotConfig = async () => {
    try {
      const config = await getRobotConfig();

      setRaspberryPiIp(config.raspberryPiIp || '');
      setRaspberryPiPort(config.raspberryPiPort || 5000);
      setBaseUrl(config.baseUrl || '');

      setStatusMessage('Robot configuration loaded.');
    } catch (error) {
      console.error('Failed to load robot config:', error);
      setStatusMessage('Failed to load robot configuration.');
    }
  };

  const handleSaveConfig = async (e) => {
    e.preventDefault();

    if (!raspberryPiIp.trim()) {
      alert('Please enter Raspberry Pi IP address');
      return;
    }

    try {
      const updatedConfig = await updateRobotConfig({
        raspberryPiIp,
        raspberryPiPort: Number(raspberryPiPort),
      });

      setBaseUrl(updatedConfig.baseUrl);
      setStatusMessage('Raspberry Pi IP address saved successfully.');
    } catch (error) {
      console.error('Failed to save robot config:', error);
      setStatusMessage('Failed to save Raspberry Pi IP address.');
    }
  };

  // The Gazebo web_bridge runs on this PC and serves the same API as the Pi
  const switchToSimulation = async () => {
    try {
      const updatedConfig = await updateRobotConfig({
        raspberryPiIp: '127.0.0.1',
        raspberryPiPort: 5000,
      });

      setRaspberryPiIp(updatedConfig.raspberryPiIp);
      setRaspberryPiPort(updatedConfig.raspberryPiPort);
      setBaseUrl(updatedConfig.baseUrl);
      setStatusMessage('Robot set to the Gazebo simulation (web_bridge on this PC). Testing...');
      await testRobotConnection();
    } catch (error) {
      console.error('Failed to save simulation config:', error);
      setStatusMessage('Failed to save the simulation address.');
    }
  };

  const testRobotConnection = async () => {
    try {
      const data = await getRobotStatus();

      if (data.status !== 'online') {
        setPoints([]);
        setStatusMessage(
          'Robot connection failed. Check that the Raspberry Pi server or the Gazebo web_bridge is running and the IP/port are right.'
        );
        return;
      }

      setStatusMessage(
        `Robot connection successful: ${data.simulation ? 'Gazebo simulation, ' : ''}${data.state || 'online'}`
      );

      try {
        setPoints(await getRobotPoints());
      } catch {
        setPoints([]);
      }
    } catch (error) {
      console.error('Robot connection test failed:', error);
      setStatusMessage('Robot connection failed. Check Raspberry Pi server and IP address.');
    }
  };

  return (
    <div className="robot-settings-page">
      <h1>Robot Settings</h1>
      <p>Configure Raspberry Pi connection settings for DeliveryBot.</p>

      <form className="robot-settings-card" onSubmit={handleSaveConfig}>
        <div className="robot-settings-group">
          <label>Raspberry Pi IP Address</label>
          <input
            type="text"
            placeholder="Example: 192.168.1.113"
            value={raspberryPiIp}
            onChange={(e) => setRaspberryPiIp(e.target.value)}
            required
          />
        </div>

        <div className="robot-settings-group">
          <label>Raspberry Pi Server Port</label>
          <input
            type="number"
            placeholder="5000"
            value={raspberryPiPort}
            onChange={(e) => setRaspberryPiPort(e.target.value)}
            required
          />
        </div>

        <div className="robot-current-url">
          <strong>Current Robot Base URL:</strong>
          <p>{baseUrl || 'Not configured yet'}</p>
        </div>

        <div className="robot-settings-actions">
          <button type="submit">Save Robot IP</button>

          <button type="button" onClick={testRobotConnection}>
            Test Connection
          </button>

          <button type="button" onClick={switchToSimulation}>
            Use Gazebo Simulation
          </button>
        </div>

        {statusMessage && (
          <p className="robot-settings-status">{statusMessage}</p>
        )}

        {points.length > 0 && (
          <div>
            <h3>Delivery points of the robot map</h3>
            <p>
              Give each table in the table map the ArUco ID of the point it should be
              delivered to.
            </p>
            <table className="robot-points-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Name</th>
                  <th>ArUco ID</th>
                  <th>x, y (m)</th>
                </tr>
              </thead>
              <tbody>
                {points.map((p) => (
                  <tr key={p.name}>
                    <td>{p.number}</td>
                    <td>{p.name}</td>
                    <td>{p.markerIds ? p.markerIds.join(', ') : p.markerId ?? '-'}</td>
                    <td>
                      {p.x}, {p.y}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </form>
    </div>
  );
}

export default RobotSettings;