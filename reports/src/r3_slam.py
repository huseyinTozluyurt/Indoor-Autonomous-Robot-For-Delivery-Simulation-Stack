import json, os
from common import fig, fig2, table, page, reset
D = os.path.join(os.path.dirname(__file__), 'data')


def build():
    reset()
    s = json.load(open(f'{D}/slam_stats.json'))
    m = json.load(open(f'{D}/metrics.json'))['campus_full_map7']
    b = []
    b.append(f"""
<h2>1. Problem</h2>
<p>A delivery robot has to answer two questions all the time: <i>what does the building look like</i> (mapping) and
<i>where am I in it</i> (localisation). Indoors there is no GPS, wheels slip, and long corridors look the same to a
lidar. This project solves both with an <b>ArUco landmark EKF-SLAM</b>: wheel odometry and the IMU gyro predict the
motion, the mast camera's ArUco detections correct it, and the 2D lidar draws the occupancy grid. The map is built once by
an autonomous exploration run and then reused by the delivery navigator, which localises against the same markers.</p>
<div class="kpi"><div><b>{m['obs_markers']}</b><span>markers mapped by observation (campus_full_map7)</span></div><div><b>{m['len_m']:.0f} m</b><span>driven in {m['dur_s']/60:.0f} sim-min, fully autonomous</span></div>
<div><b>{m['aligned_mean']:.2f} m</b><span>mean marker error after rigid fit (map shape)</span></div><div><b>{s['odom_end']:.1f} m → {s['dr_end']:.1f} m</b><span>end drift: wheels only → wheels + gyro</span></div></div>
<h2>2. Sensors and frames</h2>""")
    b.append(table(['Sensor (Gazebo, RB1 base)', 'Topic', 'Used for'], [
        ['Diff-drive wheel odometry', 'diff_drive_controller', 'Distance travelled (EKF prediction)'],
        ['IMU gyro', '<code>/robot/imu/data</code>', 'Heading (wheels slip in in-place turns)'],
        ['Mast RGB camera 640×480, 69° HFOV', '<code>/robot/aruco_camera/image_raw</code>', 'ArUco range/bearing/facing (EKF update)'],
        ['Front 2D lidar', '<code>/robot/front_laser/scan</code>', 'Occupancy grid, obstacle stop, scan matching'],
    ]))
    b.append("""<p>The mapper's <code>initial_pose</code> is set to the Gazebo spawn pose ((−17, −17, 0) in two_buildings,
(−25, 0, 0) in campus_area), so map coordinates equal world coordinates and every saved marker can be compared with the
world file. All waits and time-outs run on simulation time (<code>/clock</code>), so mapping at 3–10× real time
(<code>rtf:=</code>) behaves the same as at 1×.</p>
<h2>3. EKF-SLAM</h2>
<p><b>State.</b> Robot pose (x, y, θ) plus (x, y) of every marker seen so far; the covariance grows by two rows and
columns when a new ID appears. Because the marker ID is decoded from the image, data association is exact – there are
no wrong matches, the main failure mode of feature-based SLAM.</p>
<p><b>Prediction.</b> Distance from the wheels, heading change from the gyro. The process noise is
<code>odom_alpha = [0.05, 0.05, 0.06, 0.1]</code> (x and y per metre, yaw per radian turned and per metre). In the mapper the
gyro is trusted strongly (<code>gyro_noise = 0.0003</code>), so a marker re-sighting can correct the position but cannot
rotate the whole map – this was the key fix for the rotated maps of the first runs (see Report 6).</p>
<p><b>Update.</b> Each detection gives range and bearing in base_link (Report 2). The innovation is gated
(χ² = 13.8) and the noise scales with range/pixels. A marker seen for the first time is initialised from the current pose.
Bearings are down-weighted while the robot turns and ignored above 0.5 rad/s because camera latency turns into heading
error. With <code>sync_sensors</code> on, each image and scan is shifted by the robot motion between its time stamp and the
latest odometry.</p>
<p><b>Marker facing and delivery points.</b> A weighted average of the measured marker normal gives the direction each
marker faces. For delivery markers the mapper places a delivery point 2.3 m (or the marker's <code>standoff</code>) in front
of the marker, facing it – this is the pose the robot drives to.</p>
<p><b>Occupancy grid.</b> A 0.1 m log-odds grid (+0.85 hit / −0.4 free, clamped ±4) is ray-cast from every lidar scan at
the EKF pose; a second layer records which walls the camera has looked at from close range. An optional correlative
scan-to-map matcher (<code>scan_matching</code>) corrects x/y in marker-free corridors; it is off by default in the mapper.</p>
<h2>4. Autonomous exploration</h2>
<p>After a 360° start turn the robot repeatedly drives to the cheapest of two goal types, using Dijkstra distances on the
current map: a <b>frontier</b> (reachable free cell next to unknown space) or a <b>viewpoint</b> 2–3.5 m in front of a wall
stretch the camera has not yet seen from close range. The second type makes sure every wall – and therefore every marker on
it – is seen from near, not only mapped by the lidar. Unreachable goals are blacklisted. When nothing is left the robot
drives home and saves; it also saves every 60 s and on Ctrl+C.</p>""")
    b.append(fig('slam_traj_markers.png', f'campus_full_map7. Left: the same run from three pose sources. Wheel odometry alone ends {s["odom_end"]:.1f} m and {abs(s["yaw_odom_vs_slam_deg"]):.0f}° away from the SLAM pose and leaves the building; wheels + gyro stays within {s["dr_end"]:.1f} m; the EKF adds the marker corrections. Right: SLAM marker estimates (red) against the world-file positions (green); markers 5, 44 and 49 were never detected.'))
    b.append(fig('slam_marker_err.png', 'Per-marker position error of campus_full_map7 against the world file, with the EKF\'s own σ. Markers with σ = 0.3 and no observations were added afterwards for the table delivery points (aruco_landmarks_before_tables.yaml has 19 markers).'))
    b.append(f"""
<p>The errors are similar for all markers (1.0–1.9 m) because most of the absolute error is one small rigid
rotation of the whole map (≈{m['rot_deg']:.1f}°) about the start point. After removing the best-fit rotation and shift, the
mean error is {m['aligned_mean']:.2f} m (max {m['aligned_max']:.2f} m). For delivery this is what counts: the robot
localises on the <i>same</i> map it was built with, so a global rotation does not move it away from the delivery points.</p>
<h2>5. Saved map</h2>""")
    b.append(table(['File', 'Content'], [
        ['<code>map.pgm</code>, <code>map.yaml</code>', 'Occupancy grid in Nav2 map_server format (0.1 m)'],
        ['<code>aruco_landmarks.yaml</code>', 'Markers (id, name, x, y, yaw, σ, observations), delivery points, start pose'],
        ['<code>observations.csv</code>, <code>trajectory.csv</code>', 'Every detection; SLAM, wheel and dead-reckoning poses'],
        ['<code>scans.npz</code>', 'Raw scans with poses, for offline correction'],
        ['<code>map_preview.png</code>', 'Walls (green = seen by camera), markers, delivery points, path'],
    ]))
    b.append("""
<h2>6. Offline correction: pose graph</h2>
<p>For runs spoiled by slip, two offline tools rebuild the map from <code>scans.npz</code>:</p>
<ul>
<li><b>optimize_map</b> (<code>map_optimizer.py</code>) – graph SLAM: keyframes every 0.3 m / 10°, odometry edges
(wheels + gyro), one edge per marker detection, and lidar loop edges from matching each keyframe scan against the map of
all other parts of the run; solved by robust (Cauchy) Gauss-Newton in three rounds of draw → match → optimise, numpy only.
Writes into <code>&lt;map&gt;/corrected/</code>.</li>
<li><b>correct_map</b> – re-aligns a later run on an earlier good map (base first), detects slip events (&gt;3° or
&gt;0.2 m over 10 scans) and merges. In a 15 % wheel-slip test without gyro, marker errors went from up to 72.7 m to
within 0.07 m of the base, with 148 slip events found.</li>
</ul>""")
    b.append(fig2('map_correction_slip15.png', 'correct_map on a run with 15 % rotational wheel slip: green corrected path, red the run\'s own SLAM path, orange circles slip events.',
                  'aruco_slam_map_before_after.png', 'campus_full_map3: live map (top) and the same recorded data replayed through the fixed mapper (bottom). Green lines are the real walls.'))
    b.append("""
<h2>7. Localisation during delivery</h2>
<p>The delivery navigator runs the same EKF with the saved markers as <b>fixed beacons</b> (σ 0.05 m) and corrects with
lidar matching against the saved grid. It starts from <code>home</code>, a named point, an explicit pose, or
<code>auto</code> (turn until a marker is in view and compute the pose from it). Every few seconds it checks that the scan
fits the map; if not, <code>recover_pose</code> searches around the current estimate. Obstacles seen by the lidar are kept
for 30 s only and forgotten after each pose correction, so a pose error cannot permanently close a corridor.</p>
<h2>8. Lidar-only alternative: slam_toolbox</h2>
<p>The repository also contains <code>slam_toolbox_ws</code>: the same robot and world mapped with
<code>slam_toolbox</code> (graph-based lidar SLAM) and saved with <code>map_saver_cli</code>. It produces a clean grid but no
landmark map or delivery points, and in the 30 m corridor it relies only on scan matching. The ArUco approach was chosen
for delivery because each delivery point is tied to a physical marker the robot can verify.</p>
<h2>9. Results and lessons</h2>""")
    b.append(table(['Test', 'Result'], [
        ['Offline replica of campus_area, 0.5 % odometry noise', 'All 12 markers within 0.14 m; 100 % of walls seen by the camera; 20–31 min sim time; no collisions'],
        ['Offline replica, 2 % odometry drift', 'Complete, marker errors up to 1.4 m'],
        ['Gazebo, campus6 (campus_area)', '12/12 markers, 0.37 m after rigid fit'],
        ['Gazebo, campus_full_map7 (two_buildings)', f'{m["obs_markers"]} markers observed, {m["aligned_mean"]:.2f} m after rigid fit, {m["len_m"]:.0f} m path'],
        ['Mapping at 10× real time', '9.9× achieved, same map quality, no collisions (scan processing capped at 40 Hz wall time)'],
    ]))
    b.append("""<div class="box"><b>Lessons.</b> (1) Heading is everything: wheel heading in in-place turns rotated whole rooms;
the gyro fixed it. (2) Do not let a single landmark re-sighting rotate the map – trust the gyro, let markers correct
position. (3) Exploration must target what the <i>camera</i> has not seen, not only unknown lidar cells. (4) Keep raw scans
so a bad run can be repaired offline.</div>
<div class="box warn"><b>For the real robot:</b> calibrate wheel radius/track and camera, set <code>sim:=false</code> and the
real topics, keep <code>use_imu</code> on, and add markers in long featureless corridors.</div>""")
    return page('Indoor Navigation: SLAM and Localisation', 3, 'ArUco landmark EKF-SLAM, autonomous exploration, offline pose-graph correction and map-based localisation', ''.join(b))
