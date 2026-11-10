import { Link } from 'react-router-dom';

function AdminPage() {
  return (
    <div style={{ padding: '60px', textAlign: 'center' }}>
      <h1>Welcome Admin</h1>

      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          flexWrap: 'wrap',
          gap: '20px',
          marginTop: '30px',
        }}
      >
        <Link to="/operator" className="admin-box">
          Operator: Load &amp; Deliver
        </Link>

        <Link to="/admin/control-robot" className="admin-box">
          Control Robot
        </Link>

        <Link to="/admin/table-map" className="admin-box">
          Adjust Table Map
        </Link>

        <Link to="/admin/distance-monitoring" className="admin-box">
          Distance Sensor Monitoring
        </Link>

        <Link to="/admin/camera-streaming" className="admin-box">
          Camera Streaming &amp; Take Control
        </Link>

        <Link to="/admin/voice-order" className="admin-box">
          Voice Order
        </Link>

        <Link to="/admin/update-database" className="admin-box">
          Update Database
        </Link>

        <Link to="/admin/view-orders" className="admin-box">
          View Orders
        </Link>

        <Link to="/admin/control-elevator" className="admin-box">
          Control Elevator
        </Link>
        <Link to="/admin/robot-settings" className="admin-box">
          Robot Settings
        </Link>

        <Link to="/admin/users" className="admin-box">
          Manage Users
        </Link>
      </div>
    </div>
  );
}

export default AdminPage;