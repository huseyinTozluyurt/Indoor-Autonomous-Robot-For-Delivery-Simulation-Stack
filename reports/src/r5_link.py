from common import fig, fig2, table, page, reset

SEQ = """<figure><svg viewBox="0 0 760 360" width="100%" xmlns="http://www.w3.org/2000/svg">
<defs><marker id="b" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#334e68"/></marker></defs>
<g font-size="11">
<g font-weight="bold" text-anchor="middle">
<rect x="10" y="8" width="120" height="26" rx="5" fill="#e3f0fa" stroke="#1f5f8b"/><text x="70" y="26">Operator page</text>
<rect x="200" y="8" width="130" height="26" rx="5" fill="#e8f5e9" stroke="#2f855a"/><text x="265" y="26">Spring Boot</text>
<rect x="400" y="8" width="130" height="26" rx="5" fill="#f3e8ff" stroke="#6b46c1"/><text x="465" y="26">web_bridge :5000</text>
<rect x="610" y="8" width="140" height="26" rx="5" fill="#fff4e5" stroke="#c05621"/><text x="680" y="26">Gazebo robot</text></g>
<g stroke="#9fb3c8" stroke-dasharray="3,3"><line x1="70" y1="34" x2="70" y2="352"/><line x1="265" y1="34" x2="265" y2="352"/><line x1="465" y1="34" x2="465" y2="352"/><line x1="680" y1="34" x2="680" y2="352"/></g>
<g stroke="#334e68" stroke-width="1.5" marker-end="url(#b)">
<line x1="70" y1="60" x2="263" y2="60"/><line x1="265" y1="80" x2="463" y2="80"/><line x1="463" y1="104" x2="267" y2="104"/><line x1="263" y1="120" x2="72" y2="120"/>
<line x1="70" y1="150" x2="263" y2="150"/><line x1="265" y1="170" x2="463" y2="170"/>
<line x1="465" y1="196" x2="678" y2="196"/><line x1="678" y1="214" x2="467" y2="214"/>
<line x1="463" y1="240" x2="267" y2="240"/><line x1="463" y1="290" x2="267" y2="290"/>
<line x1="72" y1="320" x2="263" y2="320"/><line x1="263" y1="336" x2="72" y2="336"/></g>
<text x="80" y="55">POST /api/robot/plan (stops)</text><text x="275" y="75">POST /robot/plan</text>
<text x="275" y="100">order, legs (m), total, given order</text><text x="80" y="116">tour preview on the map</text>
<text x="80" y="145">POST /api/orders/dispatch-batch</text><text x="275" y="165">POST /robot/mission {orders}</text>
<text x="475" y="191">/cmd_vel (ROS 2)</text><text x="475" y="230">scan, imu, odom, camera</text>
<text x="275" y="235">robot-status: Delivering</text>
<text x="475" y="262" fill="#52606d">… drives the tour, checks markers …</text>
<text x="275" y="285">Delivered / Failed (per stop)</text>
<text x="80" y="315">GET /api/orders (every 2 s)</text><text x="80" y="350">live status in shop + operator pages</text>
</g></svg><figcaption><b>Figure 1.</b> Sequence of one multi-order mission from the operator page to the simulated robot and back.</figcaption></figure>"""


def build():
    reset()
    from common import FIGNUM
    FIGNUM['n'] = 1
    b = []
    b.append("""
<h2>1. Goal: one web app for simulation and hardware</h2>
<p>The DeliveryBot backend was first written for the physical robot: it called a small REST API on the Raspberry Pi
(port 5000). To test the whole service – ordering, dispatch, navigation, status – without hardware, the simulation had to
look exactly like that robot from the outside. The ROS 2 node <b><code>web_bridge</code></b> does this: it is the delivery
navigator (same map, same ArUco EKF localisation, same Dijkstra/Held-Karp planning, same marker check) wrapped in an
HTTP server that serves the Pi's API. Switching between Gazebo and the real robot is a single setting in
<i>Admin → Robot Settings</i> (<b>Use Gazebo Simulation</b> = <code>127.0.0.1:5000</code>).</p>
<pre>React :5173 → Spring Boot :8080 + MySQL → (HTTP) → web_bridge :5000 → (ROS 2) → Gazebo RB1 robot
web_bridge → POST /api/orders/robot-status → Spring Boot → (2 s polling) → every open page</pre>
<h2>2. Components</h2>""")
    b.append(table(['Part', 'What it does'], [
        ['Gazebo Harmonic, world <code>two_buildings</code>', 'RB1 robot with lidar, IMU, mast camera, diff drive; ArUco markers on walls and tables'],
        ['<code>ros_gz_bridge</code> (<code>config/gz_bridge.yaml</code>)', 'Gazebo → ROS: <code>/clock</code>, lidar scan, IMU, both cameras + camera_info'],
        ['<code>twist_to_stamped_bridge</code>', '<code>/cmd_vel</code> (Twist) → <code>/robot/diff_drive_controller/cmd_vel</code> (TwistStamped)'],
        ['<code>web_bridge</code> (ROS 2 node, Python)', 'HTTP API, job queue, mission worker thread, status reporter thread, MJPEG camera stream, map rendering'],
        ['Spring Boot <code>RobotApiController</code> + <code>RaspberryPiService</code>', 'Proxies every robot call, 2 s/5 s timeouts, robot URL from the database'],
        ['<code>run_web_sim.sh</code> / <code>web_sim.launch.py</code>', 'Starts Gazebo, web_bridge, backend and frontend with one command (web app delayed 20 s)'],
    ]))
    b.append("<h2>3. Robot REST API served by web_bridge</h2>")
    b.append(table(['Method and path', 'Body / result'], [
        ['<code>GET /robot/status</code>', 'state (idle, busy, manual control…), pose, current and queued orders, last messages'],
        ['<code>GET /robot/points</code>', 'delivery points of the loaded map: name, ArUco id, x, y'],
        ['<code>GET /robot/map.png</code>, <code>/robot/map-info</code>', 'the SLAM map as an image + origin/resolution, points, robot pose and route for the campus map'],
        ['<code>POST /robot/plan</code>', '<code>{"stops": [...]}</code> → shortest order, legs, total, and the arrival-order total'],
        ['<code>POST /robot/mission</code>', '<code>{"orders": [{"orderID", "orderDbId", "deliveryPoint"}, ...]}</code> → queued as one tour'],
        ['<code>POST /robot/delivery</code>', 'one order; point from <code>route</code> or from <code>targetArucoId</code> (legacy table flow)'],
        ['<code>POST /robot/command</code>', 'FORWARD/BACKWARD/LEFT/RIGHT, STOP, EMERGENCY_STOP, TAKEOVER, RELEASE, RETURN_BASE, RETURN_HOME_NOW, SET_HOME_POSE, RELOCALIZE'],
        ['<code>GET /robot/sensors/latest</code>', 'front/left/right/back lidar distance in cm (minus body radius)'],
        ['<code>GET /robot/camera-stream</code>, <code>/camera-snapshot</code>', 'MJPEG of <code>/robot/aruco_camera/image_raw</code> at 5 fps, JPEG quality 70'],
    ]))
    b.append(SEQ)
    b.append("""
<h2>4. Inside web_bridge</h2>
<ul>
<li><b>HTTP thread</b> – <code>ThreadingHTTPServer</code> on 0.0.0.0:5000 with CORS headers; requests only put jobs into a queue
or read state, so they answer immediately.</li>
<li><b>Mission worker</b> – waits for sensor data, sets the initial pose, then takes <i>all</i> waiting jobs as one batch:
marks them <i>Delivering</i>, runs <code>run_tour(stops → home)</code> with Held-Karp ordering, and sets each job to
<i>Delivered</i> or <i>Failed</i> as its stop is reached. Orders that arrive while driving form the next batch.</li>
<li><b>Status reporter</b> – a separate thread POSTs every job change to <code>{backend_url}/orders/robot-status</code>, so a
stopped backend never blocks the robot (warnings are rate-limited).</li>
<li><b>Camera stream</b> – subscribes to the mast camera, JPEG-encodes at most 5 frames/s and serves them as
<code>multipart/x-mixed-replace</code>.</li>
<li><b>Map rendering</b> – draws the SLAM map (and optionally the world layout from the <code>.sdf</code>) to PNG once and caches
it; the robot pose and route are sent as data so the browser can draw them on top.</li>
</ul>
<h2>5. Manual control and safety</h2>""")
    b.append(table(['Button (Admin → Camera Streaming &amp; Take Control)', 'Command', 'Effect'], [
        ['Take control', 'TAKEOVER', 'Aborts the running leg, keeps unfinished orders as <i>Delivering – Paused</i> and puts them back at the front of the queue'],
        ['Arrows / W A S D', 'FORWARD … RIGHT', '0.3 m/s or 0.6 rad/s for 0.6 s per press, only in manual mode'],
        ['Release robot', 'RELEASE', 'Leaves manual mode; the worker replans from the current pose and finishes the paused orders'],
        ['Emergency stop', 'EMERGENCY_STOP', 'Stops at once, cancels running and queued orders (<i>Cancelled</i>) – they return to the operator list'],
        ['Return to start', 'RETURN_HOME_NOW', 'Gives orders back and drives home'],
    ]))
    b.append(fig2('web_camera_take_control.png', 'Admin camera page: live MJPEG from Gazebo, the robot on its SLAM map, and the manual-control pad.',
                  'web_control_return_start.png', 'Control page while the robot is sent back to its start point.'))
    b.append(fig2('web_robot_settings.png', 'Robot Settings: <i>Use Gazebo Simulation</i> stores 127.0.0.1:5000, tests the connection and lists the map\'s delivery points with their ArUco IDs.',
                  'web_shop_page.png', 'The shop\'s campus map is the robot\'s own SLAM map served by web_bridge – a customer clicks exactly the point the robot drives to.'))
    b.append("""
<h2>6. Running the full stack</h2>
<pre>cd ~/indoor-delivery-robot/ros2_ws
./run_web_sim.sh --build          # first time
./run_web_sim.sh                  # Gazebo + web_bridge (campus_full_map7) + backend + frontend
./run_web_sim.sh gui:=false rtf:=3.0      # headless, 3x real time
curl localhost:5000/robot/status          # test the robot API without the web app</pre>
<p>The world must match the map: <code>campus_full_map7</code> was built in <code>two_buildings</code> (start −17, −17);
<code>campus6</code> in <code>campus_area</code> (start −25, 0). The backend and frontend start 20 s after Gazebo because Maven,
Java and Vite starting together can starve Gazebo and make the controller activation time out.</p>
<h2>7. Problems met and how they were solved</h2>""")
    b.append(table(['Problem', 'Fix'], [
        ['Robot controllers timed out at start (<i>Switch controller timed out</i>)', 'Delay web app start (<code>webapp_delay:=20</code>), <code>gui:=false</code>, or render on the GPU'],
        ['Backend crashed on null values in robot status (<code>Map.of</code>)', 'Null-safe maps; robot unreachable → status <i>offline</i> instead of HTTP 500'],
        ['Orders only in browser localStorage', 'Orders in MySQL with <code>delivery_point</code> and <code>robot_message</code> columns'],
        ['Hard-coded Pi IP in the frontend', 'All robot calls go through the backend; URL stored in <code>RobotConfig</code>'],
        ['Table numbers did not match map points', 'Tables carry the ArUco ID of their delivery point, or the point name in <i>route</i>'],
        ['A stopped backend could block the robot', 'Status reports sent from their own thread with a 5 s timeout'],
    ]))
    b.append("""
<h2>8. From simulation to the real robot</h2>
<p>Because the contract is the HTTP API, moving to hardware means running a service with the same endpoints on the
Raspberry Pi 4 and entering its IP in Robot Settings; the web app does not change. The cleanest route is to run
<code>web_bridge</code> itself on the robot with <code>sim:=false</code> and the real sensor topics, so the robot keeps the same
map, planner and status reporting that were tested in Gazebo.</p>
<div class="box"><b>Summary.</b> web_bridge makes the Gazebo robot indistinguishable from the real one for the web
application. The full flow – order on the campus map, operator loads the robot, shortest tour, marker-checked delivery, live
status for every user, manual take-over and emergency stop – runs end-to-end in simulation with one command.</div>
<div class="box warn"><b>Open points:</b> the robot API and the status callback have no authentication; add a shared token
before the robot is on a shared network. Status reaches the browser by 2 s polling; Server-Sent Events would make it instant.</div>""")
    return page('Web Application ↔ Gazebo Connection', 5, 'web_bridge: serving the robot REST API from the ROS 2 simulation, missions, live status and manual control', ''.join(b))
