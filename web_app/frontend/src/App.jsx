import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './LoginPage';
import MainPage from './MainPage';
import Register from './Register';
import AdminPage from './AdminPage';
import ControlRobot from './ControlRobot';
import UpdateDatabase from './UpdateDatabase';
import ViewOrders from './ViewOrders';
import ControlElevator from './ControlElevator';
import Navbar from './Navbar';
import DistanceMonitoring from './DistanceMonitoring';
import CameraStreaming from './CameraStreaming';
import VoiceOrder from './VoiceOrder';
import RobotSettings from './RobotSettings';
import AdjustTableMap from './AdjustTableMap';
import Products from './Products';
import AboutUs from './AboutUs';
import ManageUsers from './ManageUsers';
import ShopPage from './ShopPage';
import OperatorPage from './OperatorPage';

function App() {
  return (
    <Router>
      <Navbar />

      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path="/main" element={<ShopPage />} />
        <Route path="/table-order" element={<MainPage />} />
        <Route path="/operator" element={<OperatorPage />} />

        <Route path="/admin" element={<AdminPage />} />
        <Route path="/admin/control-robot" element={<ControlRobot />} />
        <Route path="/admin/update-database" element={<UpdateDatabase />} />
        <Route path="/admin/view-orders" element={<ViewOrders />} />
        <Route path="/admin/control-elevator" element={<ControlElevator />} />

        <Route path="/register" element={<Register />} />

        <Route path="/admin/distance-monitoring" element={<DistanceMonitoring />} />
        <Route path="/admin/camera-streaming" element={<CameraStreaming />} />
        <Route path="/admin/voice-order" element={<VoiceOrder />} />
        <Route path="/admin/robot-settings" element={<RobotSettings />} />
        <Route path="/admin/table-map" element={<AdjustTableMap />} />
        <Route path="/admin/users" element={<ManageUsers />} />

        <Route path="/products" element={<Products />} />
        <Route path="/about" element={<AboutUs />} />

        <Route path="*" element={<Navigate to="/" replace />} />
        
      </Routes>
    </Router>
  );
}

export default App;