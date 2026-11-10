import { useEffect, useRef, useState } from 'react';

function VoiceOrder() {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [parsedCommand, setParsedCommand] = useState(null);
  const [statusMessage, setStatusMessage] = useState('');
  const [tableMap, setTableMap] = useState({
    rows: 0,
    columns: 0,
    tables: [],
  });

  const recognitionRef = useRef(null);

  useEffect(() => {
    const savedMap = JSON.parse(localStorage.getItem('tableMap'));

    if (savedMap) {
      setTableMap(savedMap);
    }

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setStatusMessage(
        'Speech recognition is not supported in this browser. Try Google Chrome.'
      );
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => {
      setIsListening(true);
      setStatusMessage('Listening...');
    };

    recognition.onresult = (event) => {
      const spokenText = event.results[0][0].transcript;
      setTranscript(spokenText);
      parseVoiceCommand(spokenText);
    };

    recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      setStatusMessage(`Speech recognition error: ${event.error}`);
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;
  }, []);

  const startListening = () => {
    if (!recognitionRef.current) {
      setStatusMessage('Speech recognition is not available.');
      return;
    }

    setTranscript('');
    setParsedCommand(null);
    setStatusMessage('');

    recognitionRef.current.start();
  };

  const stopListening = () => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }

    setIsListening(false);
  };

  const parseVoiceCommand = (text) => {
    const lowerText = text.toLowerCase();

    const tableMatch = lowerText.match(/table\s*(\d+)/);
    const orderMatch = lowerText.match(/order\s*(\d+)/);

    const tableNumber = tableMatch ? Number(tableMatch[1]) : null;
    const orderID = orderMatch ? orderMatch[1] : String(Date.now());

    if (!tableNumber) {
      setParsedCommand(null);
      setStatusMessage(
        'Could not find a table number. Try saying: Create order 123 for table 3.'
      );
      return;
    }

    const selectedTable = tableMap.tables.find(
      (table) => Number(table.tableNumber) === tableNumber
    );

    if (!selectedTable) {
      setParsedCommand(null);
      setStatusMessage(
        `Table ${tableNumber} was not found in the admin table map.`
      );
      return;
    }

    const command = {
      orderID,
      tableNumber: selectedTable.tableNumber,
      row: selectedTable.row,
      column: selectedTable.column,
      arucoId: selectedTable.arucoId || null,
      route: selectedTable.route || '',
      status: 'Pending',
      createdAt: new Date().toLocaleString(),
    };

    setParsedCommand(command);
    setStatusMessage('Voice command parsed successfully.');
  };

  const saveVoiceOrder = () => {
    if (!parsedCommand) {
      alert('No valid command to save.');
      return;
    }

    const newOrder = {
      id: Date.now(),
      ...parsedCommand,
    };

    const savedOrders = JSON.parse(localStorage.getItem('orders')) || [];
    const updatedOrders = [...savedOrders, newOrder];

    localStorage.setItem('orders', JSON.stringify(updatedOrders));

    setStatusMessage('Voice order saved successfully.');
    alert(`Order saved for Table ${newOrder.tableNumber}`);
  };

  const sendToRobot = async () => {
    if (!parsedCommand) {
      alert('No valid command to send.');
      return;
    }

    const robotBaseURL = 'http://192.168.1.113:5000';

    const deliveryCommand = {
      orderID: parsedCommand.orderID,
      tableNumber: parsedCommand.tableNumber,
      targetArucoId: parsedCommand.arucoId,
      route: parsedCommand.route,
    };

    try {
      const response = await fetch(`${robotBaseURL}/robot/delivery`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(deliveryCommand),
      });

      if (!response.ok) {
        throw new Error('Failed to send delivery command');
      }

      setStatusMessage('Delivery command sent to robot successfully.');
    } catch (error) {
      console.error('Robot delivery command error:', error);
      setStatusMessage('Failed to connect to robot server.');
    }
  };

  return (
    <div className="voice-order-page">
      <h1>Voice Order</h1>
      <p>
        Speak to the robot system through microphone and create delivery orders.
      </p>

      <div className="voice-instructions">
        <h2>Example Commands</h2>
        <p>Create order 12345 for table 3</p>
        <p>Send robot to table 5</p>
        <p>Deliver order 9876 to table 2</p>
      </div>

      <div className="voice-control-buttons">
        {!isListening ? (
          <button type="button" onClick={startListening}>
            Start Microphone
          </button>
        ) : (
          <button type="button" className="stop-listening-btn" onClick={stopListening}>
            Stop Listening
          </button>
        )}
      </div>

      <div className="voice-status-card">
        <p>
          <strong>Status:</strong> {statusMessage || 'Waiting for command'}
        </p>

        <p>
          <strong>Transcript:</strong> {transcript || 'No speech detected yet'}
        </p>
      </div>

      {parsedCommand && (
        <div className="parsed-command-card">
          <h2>Parsed Voice Order</h2>

          <p>
            <strong>Order ID:</strong> {parsedCommand.orderID}
          </p>

          <p>
            <strong>Table:</strong> Table {parsedCommand.tableNumber}
          </p>

          <p>
            <strong>Grid Location:</strong> Row {parsedCommand.row}, Column{' '}
            {parsedCommand.column}
          </p>

          <p>
            <strong>ArUco ID:</strong>{' '}
            {parsedCommand.arucoId ? parsedCommand.arucoId : 'Not assigned'}
          </p>

          <p>
            <strong>Route:</strong>{' '}
            {parsedCommand.route ? parsedCommand.route : 'Not assigned'}
          </p>

          <div className="voice-order-actions">
            <button type="button" onClick={saveVoiceOrder}>
              Save Order
            </button>

            <button type="button" onClick={sendToRobot}>
              Send to Robot
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default VoiceOrder;