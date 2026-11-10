import { useState } from 'react';

function ControlElevator() {
  const [currentFloor, setCurrentFloor] = useState(null);

  const handleFloorPress = async (floor) => {
    setCurrentFloor(floor);
    try {
      await fetch(`http://192.168.1.113/move?floor=${floor}`);
    } catch (error) {
      console.error("Failed to send command: ", error);
    }
  };

  return (
    <div style={{ textAlign: 'center', paddingTop: '80px' }}>
      <h2>Control Elevator</h2>
      <p>Select a floor to send the elevator:</p>
      <div style={{ display: 'flex', justifyContent: 'center', gap: '20px', marginTop: '30px' }}>
        <button className="elevator-btn" onClick={() => handleFloorPress(1)}>Floor 1</button>
        <button className="elevator-btn" onClick={() => handleFloorPress(2)}>Floor 2</button>
        <button className="elevator-btn" onClick={() => handleFloorPress(3)}>Floor 3</button>
      </div>
      {currentFloor && <p style={{ marginTop: '20px' }}>Elevator is heading to floor {currentFloor}</p>}
    </div>
  );
}

export default ControlElevator;
