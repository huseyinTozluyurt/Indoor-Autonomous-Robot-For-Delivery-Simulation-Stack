import { useEffect, useState } from 'react';
import { getLatestRobotSensorData } from './api';

function DistanceMonitoring() {
  const [sensorData, setSensorData] = useState({
    front: null,
    left: null,
    right: null,
    back: null,
    error: null,
  });

  const [connectionStatus, setConnectionStatus] = useState('Not connected');

  const robotBaseURL = 'http://192.168.1.113:5000';
  const fetchDistanceData = async () => {
    try {
      const data = await getLatestRobotSensorData();

      setSensorData({
        front: data.front,
        left: data.left,
        right: data.right,
        back: data.back,
        error: data.error,
      });

      setConnectionStatus('Connected');
    } catch (error) {
      console.error('Distance sensor fetch error:', error);
      setConnectionStatus('Failed to get data from backend / Raspberry Pi');
    }
  };

  useEffect(() => {
    fetchDistanceData();

    const interval = setInterval(() => {
      fetchDistanceData();
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const getSensorClass = (value) => {
    if (value === null || value === undefined) {
      return 'sensor-card';
    }

    if (value <= 15) {
      return 'sensor-card danger-distance';
    }

    if (value <= 35) {
      return 'sensor-card warning-distance';
    }

    return 'sensor-card safe-distance';
  };

  return (
    <div className="distance-monitoring-page">
      <h1>Distance Sensor Monitoring</h1>
      <p>Live distance data from the robot ultrasonic / ToF sensors.</p>

      <div className="robot-status-card">
        <p>
          <strong>Status:</strong> {connectionStatus}
        </p>
      </div>

      <div className="sensor-grid">
        <div className={getSensorClass(sensorData.front)}>
          <h2>Front</h2>
          <p>{sensorData.front !== null ? `${sensorData.front} cm` : '---'}</p>
        </div>

        <div className={getSensorClass(sensorData.left)}>
          <h2>Left</h2>
          <p>{sensorData.left !== null ? `${sensorData.left} cm` : '---'}</p>
        </div>

        <div className={getSensorClass(sensorData.right)}>
          <h2>Right</h2>
          <p>{sensorData.right !== null ? `${sensorData.right} cm` : '---'}</p>
        </div>

        <div className={getSensorClass(sensorData.back)}>
          <h2>Back</h2>
          <p>{sensorData.back !== null ? `${sensorData.back} cm` : '---'}</p>
        </div>
      </div>

      <div className="sensor-error-box">
        <strong>Error Code:</strong>{' '}
        {sensorData.error !== null ? sensorData.error : '---'}
      </div>
    </div>
  );
}

export default DistanceMonitoring;