import { useEffect, useState } from 'react';

function TableMapEditor() {
  const [rows, setRows] = useState(5);
  const [columns, setColumns] = useState(5);
  const [selectedSeats, setSelectedSeats] = useState([]);

  useEffect(() => {
    const savedMap = localStorage.getItem('tableMap');

    if (savedMap) {
      const parsedMap = JSON.parse(savedMap);
      setRows(parsedMap.rows);
      setColumns(parsedMap.columns);
      setSelectedSeats(parsedMap.tables);
    }
  }, []);

  const toggleSeat = (row, column) => {
    const seatId = `${row}-${column}`;

    const alreadySelected = selectedSeats.find((seat) => seat.id === seatId);

    if (alreadySelected) {
      const updatedSeats = selectedSeats
        .filter((seat) => seat.id !== seatId)
        .map((seat, index) => ({
          ...seat,
          tableNumber: index + 1,
        }));

      setSelectedSeats(updatedSeats);
    } else {
      setSelectedSeats([
        ...selectedSeats,
        {
          id: seatId,
          row,
          column,
          tableNumber: selectedSeats.length + 1,
        },
      ]);
    }
  };

  const clearMap = () => {
    setSelectedSeats([]);
    localStorage.removeItem('tableMap');
  };

  const saveMap = () => {
    const tableMap = {
      rows,
      columns,
      tables: selectedSeats,
    };

    localStorage.setItem('tableMap', JSON.stringify(tableMap));
    alert('Table map saved successfully.');
  };

  return (
    <div className="table-map-page">
      <h1>Adjust Table Map</h1>
      <p>Select boxes to define table locations for robot delivery.</p>

      <div className="map-settings">
        <div>
          <label>Rows: </label>
          <input
            type="number"
            min="1"
            max="20"
            value={rows}
            onChange={(e) => {
              setRows(Number(e.target.value));
              setSelectedSeats([]);
            }}
          />
        </div>

        <div>
          <label>Columns: </label>
          <input
            type="number"
            min="1"
            max="20"
            value={columns}
            onChange={(e) => {
              setColumns(Number(e.target.value));
              setSelectedSeats([]);
            }}
          />
        </div>
      </div>

      <div
        className="seat-grid"
        style={{
          gridTemplateColumns: `repeat(${columns}, 70px)`,
        }}
      >
        {Array.from({ length: rows }).map((_, rowIndex) =>
          Array.from({ length: columns }).map((_, columnIndex) => {
            const row = rowIndex + 1;
            const column = columnIndex + 1;
            const seatId = `${row}-${column}`;

            const selectedSeat = selectedSeats.find(
              (seat) => seat.id === seatId
            );

            return (
              <button
                key={seatId}
                type="button"
                className={`seat-box ${
                  selectedSeat ? 'selected-seat-box' : ''
                }`}
                onClick={() => toggleSeat(row, column)}
              >
                {selectedSeat ? `T${selectedSeat.tableNumber}` : '+'}
              </button>
            );
          })
        )}
      </div>

      <div className="map-actions">
        <button type="button" onClick={saveMap}>
          Save Map
        </button>

        <button type="button" onClick={clearMap} className="clear-map-btn">
          Clear Map
        </button>
      </div>

      <div className="selected-table-info">
        <h2>Selected Tables</h2>

        {selectedSeats.length === 0 ? (
          <p>No table selected yet.</p>
        ) : (
          <ul>
            {selectedSeats.map((seat) => (
              <li key={seat.id}>
                Table {seat.tableNumber} — Row {seat.row}, Column {seat.column}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default TableMapEditor;