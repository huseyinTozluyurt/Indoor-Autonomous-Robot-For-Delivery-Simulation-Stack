import { useEffect, useState } from 'react';
import { getActiveMap, createOrder } from './api';

function MainPage() {
  const [orderID, setOrderID] = useState('');
  const [orderConfirmed, setOrderConfirmed] = useState(false);
  const [selectedTable, setSelectedTable] = useState(null);
  const [finalOrderConfirmed, setFinalOrderConfirmed] = useState(false);
  const [activeMap, setActiveMap] = useState(null);
  const [statusMessage, setStatusMessage] = useState('');

  useEffect(() => {
    loadActiveMap();
  }, []);



  const loadActiveMap = async () => {
    try {
      const map = await getActiveMap();

      if (!map) {
        setActiveMap(null);
        setStatusMessage('No active map found. Please ask admin to activate a table map.');
        return;
      }

      setActiveMap(map);
      setStatusMessage('');
    } catch (error) {
      console.error('Failed to load active map:', error);
      setActiveMap(null);
      setStatusMessage('Failed to load active map from backend.');
    }
  };


  const handleConfirmOrderID = () => {
    if (orderID.trim() !== '') {
      setOrderConfirmed(true);
      setFinalOrderConfirmed(false);
    } else {
      alert('Please enter a valid Order ID');
    }
  };

  const findTableAtPosition = (rowNumber, columnNumber) => {
    if (!activeMap || !activeMap.tables) {
      return null;
    }

    return activeMap.tables.find(
      (table) =>
        Number(table.rowNumber) === Number(rowNumber) &&
        Number(table.columnNumber) === Number(columnNumber)
    );
  };

  const handleFinalConfirmOrder = async () => {
    if (!selectedTable) {
      alert('Please select a table');
      return;
    }

    const newOrder = {
      orderID,
      tableNumber: selectedTable.tableNumber,
      rowNumber: selectedTable.rowNumber,
      columnNumber: selectedTable.columnNumber,
      arucoId: selectedTable.arucoId || null,
      route: selectedTable.route || '',
      status: 'Pending',
    };

    try {
      await createOrder(newOrder);
      setFinalOrderConfirmed(true);
      setStatusMessage('Order created successfully.');
    } catch (error) {
      console.error('Failed to create order:', error);
      setStatusMessage('Failed to create order.');
    }
  };

  return (
    <div className="main-page">
      <h1>Welcome to DeliveryBot</h1>
      <p>Create a delivery order by selecting a table from the active map.</p>

      <div className="order-id">
        <label>Enter Order ID:</label>
        <input
          type="number"
          placeholder="123456789"
          value={orderID}
          onChange={(e) => {
            setOrderID(e.target.value);
            setFinalOrderConfirmed(false);
          }}
          required
        />
      </div>

      <br />

      <button type="button" onClick={handleConfirmOrderID}>
        Confirm Order ID
      </button>

      {orderConfirmed && (
        <>
          <div className="table-map-order-section">
            <h2>Select Delivery Table</h2>

            {!activeMap ? (
              <div className="empty-database-box">
                <h3>No active map available</h3>
                <p>{statusMessage || 'Admin must activate a map first.'}</p>
              </div>
            ) : (
              <>
                <p>
                  Active Map: <strong>{activeMap.mapName}</strong>
                </p>

                <div
                  className="order-seat-grid"
                  style={{
                    gridTemplateColumns: `repeat(${activeMap.columnsCount}, 72px)`,
                  }}
                >
                  {Array.from({ length: activeMap.rowsCount }).map((_, rowIndex) =>
                    Array.from({ length: activeMap.columnsCount }).map(
                      (_, columnIndex) => {
                        const rowNumber = rowIndex + 1;
                        const columnNumber = columnIndex + 1;
                        const table = findTableAtPosition(rowNumber, columnNumber);

                        if (!table) {
                          return (
                            <div
                              key={`${rowNumber}-${columnNumber}`}
                              className="empty-map-box"
                            />
                          );
                        }

                        const unavailable = table.status === 'Unavailable';

                        return (
                          <button
                            key={table.id}
                            type="button"
                            disabled={unavailable}
                            className={`order-table-box ${
                              selectedTable?.id === table.id
                                ? 'selected-order-table-box'
                                : ''
                            }`}
                            onClick={() => {
                              setSelectedTable(table);
                              setFinalOrderConfirmed(false);
                            }}
                          >
                            T{table.tableNumber}
                          </button>
                        );
                      }
                    )
                  )}
                </div>
              </>
            )}
          </div>

          <br />

          <button type="button" onClick={handleFinalConfirmOrder}>
            Confirm Order
          </button>

          {statusMessage && (
            <p className="robot-settings-status">{statusMessage}</p>
          )}

          {finalOrderConfirmed && selectedTable && (
            <div className="order-summary">
              <h2>Order Confirmed</h2>

              <p>
                <strong>Order ID:</strong> {orderID}
              </p>

              <p>
                <strong>Selected Table:</strong> Table {selectedTable.tableNumber}
              </p>

              <p>
                <strong>Location:</strong> Row {selectedTable.rowNumber}, Column{' '}
                {selectedTable.columnNumber}
              </p>

              <p>
                <strong>ArUco ID:</strong>{' '}
                {selectedTable.arucoId || 'Not assigned'}
              </p>

              <p>
                <strong>Route:</strong> {selectedTable.route || 'Not assigned'}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default MainPage;