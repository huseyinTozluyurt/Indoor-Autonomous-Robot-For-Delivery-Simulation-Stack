import { useEffect, useState } from 'react';
import {
  getMaps,
  createMap,
  updateMap,
  activateMap,
  deleteMap,
} from './api';

function AdjustTableMap() {
  const [maps, setMaps] = useState([]);
  const [editingMapId, setEditingMapId] = useState(null);

  const [mapName, setMapName] = useState('');
  const [description, setDescription] = useState('');
  const [rowsCount, setRowsCount] = useState(5);
  const [columnsCount, setColumnsCount] = useState(5);
  const [active, setActive] = useState(false);
  const [selectedTables, setSelectedTables] = useState([]);
  const [statusMessage, setStatusMessage] = useState('');

  useEffect(() => {
    loadMaps();
  }, []);

  const loadMaps = async () => {
    try {
      const data = await getMaps();
      setMaps(data);
    } catch (error) {
      console.error('Failed to load maps:', error);
      setStatusMessage('Failed to load maps from database.');
    }
  };

  const resetForm = () => {
    setEditingMapId(null);
    setMapName('');
    setDescription('');
    setRowsCount(5);
    setColumnsCount(5);
    setActive(false);
    setSelectedTables([]);
  };

  const toggleTableBox = (rowNumber, columnNumber) => {
    const boxId = `${rowNumber}-${columnNumber}`;

    const existingTable = selectedTables.find((table) => table.boxId === boxId);

    if (existingTable) {
      const updatedTables = selectedTables
        .filter((table) => table.boxId !== boxId)
        .map((table, index) => ({
          ...table,
          tableNumber: index + 1,
        }));

      setSelectedTables(updatedTables);
      return;
    }

    const newTable = {
      boxId,
      tableNumber: selectedTables.length + 1,
      rowNumber,
      columnNumber,
      arucoId: '',
      route: '',
      status: 'Available',
      notes: '',
    };

    setSelectedTables([...selectedTables, newTable]);
  };

  const updateTableField = (boxId, field, value) => {
    const updatedTables = selectedTables.map((table) =>
      table.boxId === boxId
        ? {
            ...table,
            [field]: value,
          }
        : table
    );

    setSelectedTables(updatedTables);
  };

  const handleSaveMap = async () => {
    if (!mapName.trim()) {
      alert('Please enter a map name.');
      return;
    }


    const mapData = {
    mapName,
    description,
    rowsCount: Number(rowsCount),
    columnsCount: Number(columnsCount),
    active: Boolean(active),
    tables: selectedTables.map((table) => ({
        tableNumber: Number(table.tableNumber),
        rowNumber: Number(table.rowNumber),
        columnNumber: Number(table.columnNumber),
        arucoId: table.arucoId ? Number(table.arucoId) : null,
        route: table.route,
        status: table.status || 'Available',
        notes: table.notes,
    })),
    };



    try {
      if (editingMapId) {
        await updateMap(editingMapId, mapData);
        setStatusMessage('Map updated successfully.');
      } else {
        await createMap(mapData);
        setStatusMessage('Map created successfully.');
      }

      resetForm();
      loadMaps();
    } catch (error) {
      console.error('Failed to save map:', error);
      setStatusMessage('Failed to save map.');
    }
  };

  const handleEditMap = (map) => {
    setEditingMapId(map.id);
    setMapName(map.mapName || '');
    setDescription(map.description || '');
    setRowsCount(map.rowsCount || 5);
    setColumnsCount(map.columnsCount || 5);
    setActive(Boolean(map.active));

    const loadedTables = (map.tables || []).map((table) => ({
      boxId: `${table.rowNumber}-${table.columnNumber}`,
      tableNumber: table.tableNumber,
      rowNumber: table.rowNumber,
      columnNumber: table.columnNumber,
      arucoId: table.arucoId || '',
      route: table.route || '',
      status: table.status || 'Available',
      notes: table.notes || '',
    }));

    setSelectedTables(loadedTables);
  };

  const handleActivateMap = async (id) => {
    try {
      await activateMap(id);
      setStatusMessage('Map activated successfully.');
      loadMaps();
    } catch (error) {
      console.error('Failed to activate map:', error);
      setStatusMessage('Failed to activate map.');
    }
  };

  const handleDeleteMap = async (id) => {
    const confirmed = window.confirm('Are you sure you want to delete this map?');

    if (!confirmed) {
      return;
    }

    try {
      await deleteMap(id);
      setStatusMessage('Map deleted successfully.');
      loadMaps();

      if (editingMapId === id) {
        resetForm();
      }
    } catch (error) {
      console.error('Failed to delete map:', error);
      setStatusMessage('Failed to delete map.');
    }
  };

  const findTableAt = (rowNumber, columnNumber) => {
    return selectedTables.find(
      (table) =>
        Number(table.rowNumber) === Number(rowNumber) &&
        Number(table.columnNumber) === Number(columnNumber)
    );
  };

  return (
    <div className="table-map-page">
      <h1>Adjust Table Maps</h1>
      <p>Create, edit, activate, or remove different table map configurations.</p>

      <div className="map-editor-card">
        <h2>{editingMapId ? 'Edit Map' : 'Create New Map'}</h2>

        <div className="map-form-grid">
          <div>
            <label>Map Name</label>
            <input
              type="text"
              placeholder="Example: Starbucks Main Area"
              value={mapName}
              onChange={(e) => setMapName(e.target.value)}
            />
          </div>

          <div>
            <label>Description</label>
            <input
              type="text"
              placeholder="Example: Ground floor table layout"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div>
            <label>Rows</label>
            <input
              type="number"
              min="1"
              max="20"
              value={rowsCount}
              onChange={(e) => {
                setRowsCount(Number(e.target.value));
                setSelectedTables([]);
              }}
            />
          </div>

          <div>
            <label>Columns</label>
            <input
              type="number"
              min="1"
              max="20"
              value={columnsCount}
              onChange={(e) => {
                setColumnsCount(Number(e.target.value));
                setSelectedTables([]);
              }}
            />
          </div>

          <div className="active-map-check">
            <label>
              <input
                type="checkbox"
                checked={active}
                onChange={(e) => setActive(e.target.checked)}
              />
              Set as active user order map
            </label>
          </div>
        </div>

        <div
          className="seat-grid"
          style={{
            gridTemplateColumns: `repeat(${columnsCount}, 72px)`,
          }}
        >
          {Array.from({ length: rowsCount }).map((_, rowIndex) =>
            Array.from({ length: columnsCount }).map((_, columnIndex) => {
              const rowNumber = rowIndex + 1;
              const columnNumber = columnIndex + 1;
              const table = findTableAt(rowNumber, columnNumber);

              return (
                <button
                  key={`${rowNumber}-${columnNumber}`}
                  type="button"
                  className={`seat-box ${table ? 'selected-seat-box' : ''}`}
                  onClick={() => toggleTableBox(rowNumber, columnNumber)}
                >
                  {table ? `T${table.tableNumber}` : '+'}
                </button>
              );
            })
          )}
        </div>

        {selectedTables.length > 0 && (
          <div className="map-table-editor">
            <h3>Selected Tables</h3>

            <div className="database-table-wrapper">
              <table className="database-table">
                <thead>
                  <tr>
                    <th>Table</th>
                    <th>Location</th>
                    <th>ArUco ID</th>
                    <th>Route</th>
                    <th>Status</th>
                    <th>Notes</th>
                  </tr>
                </thead>

                <tbody>
                  {selectedTables.map((table) => (
                    <tr key={table.boxId}>
                      <td>T{table.tableNumber}</td>
                      <td>
                        Row {table.rowNumber}, Column {table.columnNumber}
                      </td>
                      <td>
                        <input
                          type="number"
                          value={table.arucoId}
                          onChange={(e) =>
                            updateTableField(table.boxId, 'arucoId', e.target.value)
                          }
                          placeholder="13"
                        />
                      </td>
                      <td>
                        <input
                          type="text"
                          value={table.route}
                          onChange={(e) =>
                            updateTableField(table.boxId, 'route', e.target.value)
                          }
                          placeholder="1,2,13"
                        />
                      </td>
                      <td>
                        <select
                          value={table.status}
                          onChange={(e) =>
                            updateTableField(table.boxId, 'status', e.target.value)
                          }
                        >
                          <option value="Available">Available</option>
                          <option value="Reserved">Reserved</option>
                          <option value="Unavailable">Unavailable</option>
                        </select>
                      </td>
                      <td>
                        <input
                          type="text"
                          value={table.notes}
                          onChange={(e) =>
                            updateTableField(table.boxId, 'notes', e.target.value)
                          }
                          placeholder="Optional notes"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="map-actions">
          <button type="button" onClick={handleSaveMap}>
            {editingMapId ? 'Update Map' : 'Create Map'}
          </button>

          <button type="button" className="clear-map-btn" onClick={resetForm}>
            Clear Form
          </button>
        </div>

        {statusMessage && <p className="robot-settings-status">{statusMessage}</p>}
      </div>

      <div className="saved-maps-section">
        <h2>Saved Maps</h2>

        {maps.length === 0 ? (
          <div className="empty-database-box">
            <h3>No maps found</h3>
            <p>Create your first map configuration above.</p>
          </div>
        ) : (
          <div className="database-table-wrapper">
            <table className="database-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Size</th>
                  <th>Tables</th>
                  <th>Active</th>
                  <th>Edit</th>
                  <th>Activate</th>
                  <th>Delete</th>
                </tr>
              </thead>

              <tbody>
                {maps.map((map) => (
                  <tr key={map.id}>
                    <td>{map.mapName}</td>
                    <td>
                      {map.rowsCount} × {map.columnsCount}
                    </td>
                    <td>{map.tables ? map.tables.length : 0}</td>
                    <td>{map.active ? 'Yes' : 'No'}</td>
                    <td>
                      <button type="button" onClick={() => handleEditMap(map)}>
                        Edit
                      </button>
                    </td>
                    <td>
                      <button
                        type="button"
                        onClick={() => handleActivateMap(map.id)}
                        disabled={map.active}
                      >
                        {map.active ? 'Active' : 'Activate'}
                      </button>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="delete-table-btn"
                        onClick={() => handleDeleteMap(map.id)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default AdjustTableMap;