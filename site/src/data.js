// Numbers below are taken from the six project reports (reports/*.pdf, November 2026).
export const fig = (name) => `${import.meta.env.BASE_URL}figures/${name}`
export const pdf = (name) => `${import.meta.env.BASE_URL}reports/${name}`

export const heroStats = [
  { value: '−39 %', label: 'driving saved by the Held-Karp tour (6 stops)' },
  { value: '0.39 m', label: 'internal map error of the final SLAM map' },
  { value: '242 m', label: 'driven to map a 70 × 45 m campus on its own' },
  { value: '0.08–0.16 m', label: 'stop error at the delivery pads' },
]

export const reports = [
  { n: 1, file: '01_Web_Application.pdf', title: 'Web Application', blurb: 'React + Spring Boot + MySQL shop, operator and admin app: architecture, data model, roles, REST API, order life cycle.' },
  { n: 2, file: '02_Object_Detection_ArUco.pdf', title: 'Object Detection with ArUco', blurb: 'Marker design, OpenCV detection and solvePnP pose, measured accuracy, use at the delivery stop.' },
  { n: 3, file: '03_Indoor_Navigation_SLAM.pdf', title: 'Indoor Navigation: SLAM', blurb: 'Landmark EKF-SLAM, autonomous exploration, pose-graph correction and localisation during delivery.' },
  { n: 4, file: '04_Dijkstra_Shortest_Path.pdf', title: 'Dijkstra Shortest Path', blurb: 'Clearance-weighted grid Dijkstra, Held-Karp ordering of multi-stop tours, measured results.' },
  { n: 5, file: '05_WebApp_Gazebo_Connection.pdf', title: 'Web App ↔ Gazebo', blurb: 'web_bridge: the robot REST API served from the simulation, missions, live status, manual control.' },
  { n: 6, file: '06_Map_Evolution_Comparison.pdf', title: 'Map Evolution', blurb: 'Quantitative review of all 13 mapping runs, from the first shattered map to campus_full_map7.' },
]

// Report 2, section 4: range error (cm) of a 0.30 m marker through the mast-camera model.
export const arucoAccuracy = {
  distances: [1, 2, 3, 4, 5, 6, 8, 9],
  series: [
    { name: 'face-on (0°)', values: [1.0, 3.3, 7.6, 12.8, 19.8, 37.9, 26.5, 36.4] },
    { name: 'turned 30°', values: [0.4, 2.3, 5.4, 13.0, 19.9, 38.0, 77.2, null] },
    { name: 'turned 50°', values: [0.9, 2.6, 5.6, 7.2, 29.8, 23.7, 77.2, 66.7] },
  ],
}

export const markerKinds = [
  { kind: 'Delivery', size: '0.30 m', count: 22, where: 'Behind every delivery pad and on tables, 0.4–0.6 m high' },
  { kind: 'Room', size: '1.00 m / 0.60 m', count: 4, where: 'Far wall of each building and inside the doorways' },
  { kind: 'Corridor', size: '0.60 m / 0.40 m', count: 6, where: 'Corridor walls, so a landmark is in view in long corridors' },
]

// Report 6, section 3. shape = error after best rigid fit, rot = global rotation.
export const mapRuns = [
  { name: 'campus', world: 'campus_area', date: '4 Nov', markers: '12/12', abs: 53.41, shape: 10.17, rot: 100.4, path: 1007, min: 62.5, note: 'First full autonomous run. All 12 markers found, but wheel heading in in-place turns rotated each pass of a room: overlapping copies of both rooms.', img: 'evo_campus_area.png' },
  { name: 'campus4', world: 'campus_area', date: '4 Nov', markers: '5/12', abs: 0.34, shape: 0.18, rot: 1.3, path: 221, min: 14.5, note: 'Partial run (left room and corridor) after switching heading to the IMU gyro: first clean, straight geometry.', img: 'evo_campus_area.png' },
  { name: 'campus5', world: 'campus_area', date: '5 Nov', markers: '11/12', abs: 0.63, shape: 0.32, rot: 0.8, path: 742, min: 44.1, note: 'Both rooms, 11/12 markers. Walls in the right room are doubled by a small residual heading error.', img: 'evo_campus_area.png' },
  { name: 'campus6', world: 'campus_area', date: '5 Nov', markers: '12/12', abs: 1.61, shape: 0.37, rot: 2.4, path: 491, min: 29.6, note: 'All 12 markers, single clean walls in both rooms. The reference map for campus_area.', img: 'evo_campus_area.png' },
  { name: 'campus_full_map', world: 'two_buildings', date: '5 Nov', markers: '31/32', abs: 4.81, shape: 0.24, rot: 9.1, path: 467, min: 32.6, note: 'First map of the larger two-building world (32 markers, tables, ring corridor). Good shape, but the whole map is rotated about 9°.', img: 'evo_two_buildings.png' },
  { name: 'campus_full_map3', world: 'two_buildings', date: '7 Nov', markers: '30/32', abs: 4.25, shape: 0.66, rot: 7.7, path: 464, min: 30.9, note: 'Rotated about 8° with ghost walls in building B: marker re-sightings were still allowed to turn the heading.', img: 'aruco_slam_map_before_after.png' },
  { name: 'campus_full_map4', world: 'two_buildings', date: '7 Nov', markers: '32/32', abs: 1.81, shape: 1.34, rot: 0.7, path: 489, min: 32.8, note: 'After the "spin fix" (gyro trusted, markers correct position only): rotation gone, all 32 markers, but local distortions remain.', img: 'two_buildings_spin_fix.png' },
  { name: 'campus_full_map5', world: 'two_buildings', date: '7 Nov', markers: '11/32', abs: 2.20, shape: 0.59, rot: 1.9, path: 129, min: 10.2, note: 'Building A only, used to develop the post-run pose-graph correction.', img: 'campus_full_map5_fix.png' },
  { name: 'campus_full_map7', world: 'two_buildings', date: '8 Nov', markers: '19/32', abs: 1.35, shape: 0.39, rot: 2.6, path: 242, min: 20.9, note: 'Final map: single sharp walls everywhere, 19 markers observed plus 10 table markers added afterwards, shortest run of all. Used by the web app.', img: 'campus_full_map7_preview.png' },
]

// Report 4, section 5.
export const tour = {
  arrival: { label: 'Order of arrival', cost: 290.7, stops: ['home', 'a_delivery_point_2', 'b_delivery_point_3', 'r_delivery_point_1', 'b_delivery_point_2', 'a_delivery_point_7', 'c_table_north', 'home'] },
  optimal: { label: 'Held-Karp (used)', cost: 176.0, stops: ['home', 'a_delivery_point_2', 'a_delivery_point_7', 'c_table_north', 'r_delivery_point_1', 'b_delivery_point_3', 'b_delivery_point_2', 'home'] },
  methods: [
    { name: 'Order of arrival', cost: 290.7, delta: '+65 %' },
    { name: 'Nearest neighbour', cost: 176.5, delta: '+0.3 %' },
    { name: 'Nearest neighbour + 2-opt', cost: 176.0, delta: '+0.0 %' },
    { name: 'Held-Karp (used)', cost: 176.0, delta: 'optimal' },
    { name: 'Brute force, 720 orders', cost: 176.0, delta: 'same' },
  ],
  detour: [
    { to: 'a_delivery_point_2', dij: 29.5, line: 27.6 },
    { to: 'b_delivery_point_3', dij: 71.9, line: 58.8 },
    { to: 'r_delivery_point_1', dij: 50.2, line: 41.2 },
    { to: 'b_delivery_point_2', dij: 62.9, line: 55.8 },
    { to: 'a_delivery_point_7', dij: 27.8, line: 26.6 },
    { to: 'c_table_north', dij: 34.8, line: 28.7 },
  ],
}

// Report 5, section 3.
export const robotApi = [
  ['GET', '/robot/status', 'State (idle, busy, manual control…), pose, current and queued orders'],
  ['GET', '/robot/points', 'Delivery points of the loaded map: name, ArUco id, x, y'],
  ['GET', '/robot/map.png', 'The SLAM map as an image, plus /robot/map-info for origin, points and route'],
  ['POST', '/robot/plan', '{"stops": [...]} → shortest order, legs, total and the arrival-order total'],
  ['POST', '/robot/mission', '{"orders": [...]} → queued as one tour'],
  ['POST', '/robot/command', 'FORWARD … RIGHT, STOP, EMERGENCY_STOP, TAKEOVER, RELEASE, RETURN_HOME_NOW, RELOCALIZE'],
  ['GET', '/robot/sensors/latest', 'Front/left/right/back lidar distance in cm'],
  ['GET', '/robot/camera-stream', 'MJPEG of the mast camera at 5 fps'],
]

export const webPages = [
  { img: 'web_shop_page.png', title: 'Shop (user)', text: 'Products, cart, and the delivery point picked on the robot’s own SLAM map.' },
  { img: 'web_operator_route.png', title: 'Operator', text: 'Preparing orders, the shortest tour preview, and “Robot is loaded: deliver”.' },
  { img: 'web_view_orders.png', title: 'Admin · orders', text: 'Every order with live status and the robot’s last message.' },
  { img: 'web_camera_take_control.png', src: 'screens/camera_stream.jpg', title: 'Admin · camera streaming', text: 'Live MJPEG from the robot’s mast camera in Gazebo, with take control, the drive pad and emergency stop.' },
  { img: 'web_robot_settings.png', title: 'Admin · robot settings', text: 'Real robot IP, or one click for the Gazebo simulation, with a connection test.' },
  { img: 'web_manage_users.png', title: 'Admin · users', text: 'Search, add and change roles. The last admin cannot be demoted.' },
]

// Gazebo screenshots (site/public/gazebo/, cropped from the original screen captures).
export const gazebo = (name) => `${import.meta.env.BASE_URL}gazebo/${name}`
export const gazeboShots = [
  { img: 'world_gui_view.jpg', title: 'two_buildings world in Gazebo Sim', text: 'Building walls in colour, corridors in green, tables and ArUco markers on the walls. The small robot is in the right corridor.' },
  { img: 'campus_area_overview.jpg', title: 'campus_area world', text: 'The first world: two rooms joined by a corridor. Yellow discs are the delivery pads.' },
  { img: 'corridor_between_buildings.jpg', title: 'Driving the corridor', text: 'The robot crossing the corridor between the two rooms, with markers on the far walls.' },
  { img: 'rb1_robot_closeup.jpg', title: 'The RB1 robot', text: 'Robotnik RB1 base with the cargo box and the mast camera that reads the markers.' },
]

// Simulation video. Leave both empty to show the "coming soon" panel.
// Either put a file at site/public/video/simulation.mp4 and set src: 'video/simulation.mp4',
// or upload to YouTube and set youtube to the video id (the part after v=).
export const simVideo = {
  src: 'video/simulation.mp4',
  youtube: '',
  poster: 'video/poster.jpg',
}
