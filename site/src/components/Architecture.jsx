// System architecture: browser → backend → robot API (web_bridge in sim or the Raspberry Pi) → Gazebo.
export default function Architecture() {
  const box = (x, y, w, h, cls, title, sub, port) => (
    <g className={`arch-node ${cls}`}>
      <rect x={x} y={y} width={w} height={h} rx="10" />
      <text x={x + 14} y={y + 26} className="arch-title">{title}</text>
      {sub.map((s, i) => (
        <text key={i} x={x + 14} y={y + 46 + i * 17} className="arch-sub">{s}</text>
      ))}
      {port && <text x={x + w - 12} y={y + 26} textAnchor="end" className="arch-port">{port}</text>}
    </g>
  )
  return (
    <figure className="diagram">
      <svg viewBox="0 0 960 400" role="img" aria-labelledby="arch-t arch-d">
        <title id="arch-t">System architecture</title>
        <desc id="arch-d">The React frontend talks to the Spring Boot backend, which stores orders in MySQL and calls the robot REST API on port 5000. In simulation that API is the web_bridge ROS 2 node driving the robot in Gazebo; on hardware it is the Raspberry Pi 4.</desc>
        <defs>
          <marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" className="arch-head" />
          </marker>
        </defs>

        <text x="20" y="28" className="arch-zone">Browser</text>
        <text x="270" y="28" className="arch-zone">Server</text>
        <text x="560" y="28" className="arch-zone">Robot side · same API in sim and on hardware</text>

        {box(20, 50, 200, 110, 'n-ui', 'React + Vite', ['Shop · Operator · Admin', 'CampusMap on the SLAM map', 'polls every 2 s'], ':5173')}
        {box(270, 50, 230, 110, 'n-be', 'Spring Boot 3.5', ['Auth, Orders, RobotApi …', 'RaspberryPiService', '2 s / 5 s timeouts'], ':8080')}
        {box(270, 250, 230, 80, 'n-db', 'MySQL 8', ['deliverybot_db', 'orders, users, robot config'])}
        {box(560, 50, 380, 110, 'n-wb', 'web_bridge (ROS 2 node)', ['HTTP API · mission worker · status reporter', 'delivery_navigator: EKF + Dijkstra + Held-Karp', 'MJPEG camera stream'], ':5000')}
        {box(560, 250, 180, 110, 'n-gz', 'Gazebo Harmonic', ['RB1 robot, two_buildings', 'lidar · IMU · cameras', 'diff drive'])}
        {box(760, 250, 180, 110, 'n-pi', 'Raspberry Pi 4', ['real robot', 'same endpoints', 'other IP in settings'])}

        <line x1="220" y1="95" x2="268" y2="95" className="arch-edge" markerEnd="url(#ah)" />
        <text x="244" y="85" textAnchor="middle" className="arch-lbl">REST</text>

        <line x1="385" y1="160" x2="385" y2="248" className="arch-edge" markerEnd="url(#ah)" />
        <text x="393" y="208" className="arch-lbl">JPA</text>

        <line x1="500" y1="85" x2="558" y2="85" className="arch-edge" markerEnd="url(#ah)" />
        <text x="529" y="75" textAnchor="middle" className="arch-lbl">mission</text>
        <line x1="558" y1="125" x2="502" y2="125" className="arch-edge" markerEnd="url(#ah)" />
        <text x="529" y="145" textAnchor="middle" className="arch-lbl">status</text>

        <line x1="650" y1="160" x2="650" y2="248" className="arch-edge" markerEnd="url(#ah)" />
        <text x="658" y="200" className="arch-lbl">ROS 2 topics</text>
        <text x="658" y="216" className="arch-lbl">via ros_gz_bridge</text>

        <line x1="850" y1="160" x2="850" y2="248" className="arch-edge dashed" markerEnd="url(#ah)" />
        <text x="858" y="200" className="arch-lbl">on hardware:</text>
        <text x="858" y="216" className="arch-lbl">same API</text>
      </svg>
      <figcaption>The backend is the only part that talks to the robot. Switching from Gazebo to the real robot is one setting in Admin → Robot Settings.</figcaption>
    </figure>
  )
}
