import json, os
from common import fig, fig2, table, page, reset
D = os.path.join(os.path.dirname(__file__), 'data')


def build():
    reset()
    st = json.load(open(f'{D}/aruco_stats.json'))
    rows = json.load(open(f'{D}/aruco_synth.json'))

    def err(a, z):
        for r in rows:
            if r[0] == a and abs(r[1] - z) < 1e-6:
                return '–' if r[2] is None else f'{r[2]*100:.1f} cm / {r[3]:.0f} px'
        return '–'
    b = []
    b.append(f"""
<h2>1. Role of ArUco markers in the robot</h2>
<p>The robot recognises places with square fiducial markers from the OpenCV <b>ArUco DICT_4X4_50</b> dictionary
(4×4 bits, 50 IDs). Each marker has a known ID, size and purpose, so a detection gives three things at once:
<i>which</i> landmark is in view (no data-association problem), <i>where</i> it is relative to the robot (range and
bearing from the camera pose), and <i>which way</i> it faces (used to place the delivery point in front of it). The
markers are used by every part of the stack: the EKF-SLAM mapper adds them as landmarks, the delivery navigator uses
them as beacons for localisation, and at every stop the robot turns to the marker and checks that the camera sees the
correct ID before it reports <i>Delivered</i>.</p>
<div class="kpi"><div><b>32</b><span>markers in the two_buildings world</span></div><div><b>{st['n']}</b><span>detections logged while mapping campus_full_map7</span></div>
<div><b>{st['rng_max']:.1f} m</b><span>longest detection (1.0 m marker)</span></div><div><b>≈ 5–8 cm</b><span>range error at 3 m, 0.30 m marker (synthetic test)</span></div></div>
<h2>2. Markers and camera</h2>""")
    b.append(table(['Kind', 'Size (black square)', 'Count', 'Where'], [
        ['delivery', '0.30 m', '22', 'Behind every delivery pad / on tables (room A, room B, corridor rooms), 0.4–0.6 m high'],
        ['room', '1.00 m and 0.60 m', '2 + 2', 'Far wall of each building (seen on entry) and inside the doorways'],
        ['corridor', '0.60 m and 0.40 m', '4 + 2', 'Corridor walls, so the robot sees a landmark in long corridors'],
    ]))
    b.append(fig('aruco_markers.png', 'Examples of the DICT_4X4_50 markers used in the world (generated with the project\'s <code>aruco_utils.generate_marker</code>). Printable PNGs for the real robot are in <code>models/aruco_marker_&lt;id&gt;/meshes/</code>.'))
    b.append("""
<p>The markers are seen by a dedicated <b>mast camera</b> (<code>aruco_camera</code>): RGB 640×480 at 15 Hz with a
horizontal field of view of 1.2 rad (69°), mounted above the cargo box at base_link +0.15 m in x and +0.55 m in z,
looking forward. Topics: <code>/robot/aruco_camera/image_raw</code> and <code>/camera_info</code>. Marker poses come from
<code>config/aruco_markers.yaml</code> (campus_area) and <code>config/aruco_markers_two_buildings.yaml</code>, both
generated together with the Gazebo models by the scripts in <code>scripts/</code>.</p>
<h2>3. Detection pipeline</h2>
<ol>
<li><b>Detect</b> – the image is converted to grey and passed to <code>cv2.aruco</code> (the <code>ArucoDetector</code> class on
OpenCV ≥ 4.7, <code>detectMarkers</code> on the Ubuntu 24.04 OpenCV 4.6; <code>aruco_utils.MarkerDetector</code> hides the
difference). Result: four corner points and the ID of each marker.</li>
<li><b>Filter</b> – markers whose mean edge is smaller than <code>min_pixels = 12</code> are dropped, and IDs that are not in
the marker config are ignored (<code>known_markers_only</code>), which removes misreads.</li>
<li><b>Pose</b> – <code>cv2.solvePnP</code> with <code>SOLVEPNP_IPPE_SQUARE</code> and the marker's real size gives the
rotation <code>rvec</code> and translation <code>tvec</code> in the camera optical frame.</li>
<li><b>Robot frame</b> – the translation is moved into base_link (<code>bx = 0.15 + t_z</code>, <code>by = −t_x</code>), giving
<b>range</b> = √(bx²+by²) and <b>bearing</b> = atan2(by, bx). The marker normal (third column of the rotation matrix)
gives the <b>facing</b> angle. Detections farther than 25 × marker size, or whose facing is more than 80° away from
"towards the robot" (a pose flip of the planar PnP), are rejected.</li>
<li><b>Noise model</b> – each observation carries σ<sub>r</sub> = max(0.03, 0.8·range/pixels) and
σ<sub>b</sub> = 0.012 + 0.05/pixels rad, so far, small markers count less in the EKF. While the robot turns, the bearing
noise grows with the turn rate (camera timing error), and above 0.5 rad/s marker bearings are not used.</li>
</ol>
<p>The standalone ROS node <code>aruco_detector</code> publishes an annotated image, a <code>PoseArray</code>, a JSON list of
detections and the current room; the mapper and navigator run the same code internally (<code>ArucoObserver</code>) so they
do not depend on that node.</p>""")
    b.append(fig2('aruco_synth_detect.png', 'Synthetic test frame: ID 40 rendered through the mast-camera model at 3 m and turned 30°, detected and posed by OpenCV (axes drawn with <code>drawFrameAxes</code>).',
                  'robot_vision_overlay.png', 'Robot vision overlay (<code>robot_vision</code>) in Gazebo: marker ID, name, range and bearing on the live camera, together with other detected objects.'))
    b.append(f"""
<h2>4. Accuracy test with the real camera model</h2>
<p>To measure the range error without the influence of SLAM, a 0.30 m marker was rendered with a perspective warp
through the exact mast-camera intrinsics (f = 320/tan(0.6) = 468 px, 640×480), with light image noise, at distances
from 1 to 9 m and turned 0°, 30° and 50° away from the camera. Each frame went through the same detection and
<code>solvePnP(IPPE_SQUARE)</code> code. (Synthetic frames, not Gazebo renders; script: <code>reports/src/scripts/figs.py</code>.)</p>""")
    b.append(table(['Distance', '0° (face-on)', '30°', '50°'],
                   [[f'{z:.0f} m', err(0, z), err(30, z), err(50, z)] for z in (1, 2, 3, 4, 5, 6, 8, 9)]))
    b.append(fig('aruco_synth_accuracy.png', 'Left: range error of the PnP estimate grows roughly with the square of the distance and is always positive – most likely because the detected corners sit slightly inside the black border, so the marker looks smaller and farther away. Right: apparent marker edge in pixels; the 12 px limit is reached near 9 m for a 0.30 m marker.'))
    b.append("""<p>Two results matter for the rest of the system. First, a 0.30 m delivery marker is accurate to a few
centimetres within 3 m, which is exactly where the robot stands when it confirms a delivery (2.3 m stand-off). Second,
beyond ~5 m the error reaches decimetres; this is why the EKF noise is scaled by range/pixels, and why large 0.6 m and
1.0 m markers are placed where the robot must localise from far away (room far walls, corridors).</p>""")
    b.append(f"""
<h2>5. Detections during a real mapping run</h2>
<p>The mapper logs every accepted detection to <code>observations.csv</code>. For the final map <code>campus_full_map7</code>
(two_buildings world) there are <b>{st['n']}</b> detections of <b>{st['markers']}</b> different markers. The median range
is {st['rng_med']:.1f} m and the longest {st['rng_max']:.1f} m (a 1.0 m room marker).</p>""")
    b.append(fig('aruco_real_stats.png', 'campus_full_map7 detections. Left: range distribution. Middle: pixel size against range for the three marker sizes – the big markers are what make 10–25 m detections possible. Right: detections per marker; room/corridor markers are seen most because they are visible from many places.'))
    b.append(fig('aruco_range_residual.png', f'Measured range minus the distance from the SLAM pose to the true marker position (world file). The spread (median |residual| {st["res_med_abs"]:.2f} m, 90th percentile {st["res_p90"]:.2f} m) is dominated by the robot-pose and map-frame error of the SLAM run, not by the detector – compare with the centimetre-level error of the isolated test above.', 'half'))
    b.append("""
<h2>6. Use at the delivery stop</h2>
<p>When the navigator reaches a delivery point it turns to the stored facing of that point's marker and looks for the
expected ID (or any marker of that table) for up to 2 s. The log line then says <i>marker N confirmed at d m</i>, or carries a
<i>WARNING marker N not in view</i>; after the dwell time the order is reported <i>Delivered</i>. If the point cannot be
reached, the navigator recovers its pose from markers and lidar, tries once more, and otherwise reports <i>Failed</i>.
A stricter mode that refuses to deliver without the marker would be a one-line change. In the offline replica the robot stopped 0.08–0.16 m
from the real floor pads with the right marker confirmed at every stop.</p>
<h2>7. Moving to the real robot</h2>
<ul>
<li>Print the markers from <code>models/aruco_marker_&lt;id&gt;/meshes/aruco_&lt;id&gt;.png</code> and measure the black square;
put the measured size into the marker YAML – range scales directly with it.</li>
<li>Calibrate the real camera (<code>camera_info</code>), set <code>camera_offset</code> to its true mount position, and keep
the 0.30 m markers at the same height as in the simulation.</li>
<li>Lighting and motion blur are the main real-world risks; the <code>dev/aruco_playground.py</code> tool lets you tune
<code>DetectorParameters</code> (adaptive threshold windows, corner refinement) on recorded frames.</li>
</ul>
<div class="box"><b>Summary.</b> ID-based fiducials remove the hardest SLAM problem (data association) and give a reliable
"am I at the right door?" check. The measured accuracy – a few cm at the delivery stand-off, decimetres at 5–8 m –
matches the noise model the EKF uses.</div>""")
    return page('Object Detection with ArUco Markers', 2, 'Marker design, OpenCV detection and pose estimation, accuracy, and use in mapping and delivery', ''.join(b))
