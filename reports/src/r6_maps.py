import json, os
from common import fig, fig2, table, page, reset
D = os.path.join(os.path.dirname(__file__), 'data')

NOTES = {
    'campus': 'First full autonomous run. All 12 markers found, but heading from slipping wheels in in-place turns made each pass of a room come out rotated: overlapping copies of both rooms.',
    'campus2': 'Aborted after 14 s (test of the new scan recording, <code>scans.npz</code>).',
    'campus3': 'Aborted after 14 s (same test).',
    'campus4': 'Partial run (left room + corridor) after switching heading to the IMU gyro: first clean, straight geometry.',
    'campus5': 'Both rooms, 11/12 markers. Walls in the right room are doubled (small residual heading error). Live and post-corrected versions saved.',
    'campus6': '12/12 markers, single clean walls in both rooms. Reference map for campus_area.',
    'campus_full_map': 'First map of the larger two_buildings world (32 markers, tables, ring corridor). Shape good, but the whole map is rotated ≈9°.',
    'campus_full_map1': 'Aborted at start (no trajectory).',
    'campus_full_map3': 'Rotated ≈8° with ghost walls in building B: marker re-sightings were still allowed to turn the heading.',
    'campus_full_map4': 'After the "spin fix" (gyro trusted, markers correct position only): rotation gone (0.7°), all 32 markers, but local distortions remain (1.3 m after rigid fit).',
    'campus_full_map5': 'Building A only, used to develop the post-run pose-graph correction (online vs corrected path: mean 1.78 m apart).',
    'campus_full_map6': 'Aborted after 61 s.',
    'campus_full_map7': 'Final map: single sharp walls everywhere, 19 markers observed + 10 table markers added afterwards, shortest run (242 m). Used by the web app.',
}


def build():
    reset()
    met = json.load(open(f'{D}/metrics.json'))
    order = ['campus', 'campus2', 'campus3', 'campus4', 'campus5', 'campus6', 'campus_full_map', 'campus_full_map1',
             'campus_full_map3', 'campus_full_map4', 'campus_full_map5', 'campus_full_map6', 'campus_full_map7']
    f7, c1 = met['campus_full_map7'], met['campus']
    b = []
    b.append(f"""
<h2>1. What this report compares</h2>
<p>Between 4 and 8 November 2026 the ArUco SLAM mapper was run {len(order)} times (plus one empty folder,
<code>campus_full_map2</code>), first in the two-room <code>campus_area</code> world and then in the larger
<code>two_buildings</code> campus. Each run left a complete map folder in <code>~/ros2_jazzy_ws/maps</code>. Because the
mapper starts at the Gazebo spawn pose, map coordinates equal world coordinates, so every map can be scored objectively
against the marker positions in the world files (<code>aruco_markers.yaml</code>, <code>aruco_markers_two_buildings.yaml</code>).
This report measures each map the same way and explains which change in the software caused each step.</p>
<div class="kpi"><div><b>{c1['mean_err_obs']:.0f} m → {f7['mean_err_obs']:.1f} m</b><span>mean absolute marker error, first → final</span></div>
<div><b>{abs(c1['rot_deg']):.0f}° → {abs(f7['rot_deg']):.1f}°</b><span>global map rotation</span></div>
<div><b>{c1['aligned_mean']:.1f} m → {f7['aligned_mean']:.2f} m</b><span>shape error after rigid fit</span></div>
<div><b>{c1['len_m']:.0f} m → {f7['len_m']:.0f} m</b><span>path driven to finish the map</span></div></div>
<h2>2. Method</h2>
<ul>
<li><b>Absolute error</b> – distance between each observed marker in <code>aruco_landmarks.yaml</code> and its true pose
(markers added by hand with 0 observations are left out).</li>
<li><b>Shape error</b> – the same after the best 2-D rigid transform (rotation + translation, SVD/Kabsch). It shows whether the
map is <i>internally</i> right; this is what matters for navigation, because the robot localises on the same map.</li>
<li><b>Global rotation</b> – the angle of that best-fit transform.</li>
<li>Coverage (markers found), driven path length and simulated time from <code>trajectory.csv</code>. Script:
<code>reports/src/scripts/metrics.py</code> and <code>align.py</code>.</li>
</ul>
<h2>3. All runs</h2>""")
    rows = []
    for n in order:
        v = met[n]
        def f(x, d=2):
            return '–' if x is None else f'{x:.{d}f}'
        rows.append([f'<b>{n}</b>', v['created'][5:16].replace('T', ' '), 'campus_area' if v['world'] == 'campus' else 'two_buildings',
                     f"{v.get('obs_markers', 0)}/{v['gt']}", f(v.get('mean_err_obs')), f(v.get('aligned_mean')),
                     f(abs(v['rot_deg']), 1) if 'rot_deg' in v else '–', f(v['len_m'], 0), f(v['dur_s'] / 60, 1)])
    b.append(table(['Map', 'Created', 'World', 'Markers', 'Abs. err (m)', 'Shape err (m)', 'Rot. (°)', 'Path (m)', 'Sim min'], rows))
    b.append(fig('evo_metrics.png', 'Error, rotation and coverage of every complete or partial run (aborted runs left out). The dashed line separates the two worlds. Absolute error (log scale) is dominated by rotation; the shape error shows the internal quality.'))
    b.append(fig('evo_effort.png', 'Driven path and simulated time per run. The final map needed the least driving of all full two_buildings runs.', 'half'))
    b.append('<h2>4. Stage 1 – campus_area (4–5 November)</h2>')
    b.append(fig('evo_campus_area.png', 'campus_area maps in order. Green walls were seen by the camera, red dots are markers, stars delivery points, blue the driven path.'))
    for n in ['campus', 'campus2', 'campus3', 'campus4', 'campus5', 'campus6']:
        b.append(f'<p><b>{n}.</b> {NOTES[n]}</p>')
    b.append(fig('offline_test_15pct_slip_gyro.png', 'Offline replica test with 15 % rotational wheel slip: the same failure as the first <code>campus</code> map – each room is drawn several times at different angles. This test led to using the gyro for heading and to the slip correction tools.', 'half'))
    b.append(f"""<div class="box"><b>What changed:</b> heading from the IMU gyro instead of the wheels (<code>use_imu</code>), slower
turns while mapping (0.45 rad/s), and recording raw scans for offline correction. Result: from a shattered map
({c1['mean_err_obs']:.0f} m mean error) to campus6 with all markers and {met['campus6']['aligned_mean']:.2f} m shape error.</div>""")
    b.append('<h2>5. Stage 2 – two_buildings (5–8 November)</h2>')
    b.append(fig('evo_two_buildings.png', 'two_buildings maps in order: campus_full_map, 3, 4, 5 and the final 7.'))
    for n in ['campus_full_map', 'campus_full_map1', 'campus_full_map3', 'campus_full_map4', 'campus_full_map5', 'campus_full_map6', 'campus_full_map7']:
        b.append(f'<p><b>{n}.</b> {NOTES[n]}</p>')
    b.append(fig2('two_buildings_spin_fix.png', 'The "spin fix": previous mapper (top), live map while driving with the fix (middle), and after the final correction (bottom).',
                  'campus_full_map5_fix.png', 'campus_full_map5 live (top, bent building A) and re-processed with the fixed mapper (bottom) against the true walls (green).'))
    b.append(fig('aruco_slam_map_before_after.png', 'campus_full_map3: live map (top) and the same recorded data through the fixed mapper (bottom).', 'third'))
    b.append(f"""<div class="box"><b>What changed:</b> (1) the gyro is trusted strongly in the EKF (<code>gyro_noise 0.0003</code>) so a marker
seen again corrects the <i>position</i> but can no longer rotate the map; (2) marker bearings are down-weighted while turning and
ignored above 0.5 rad/s; (3) sensor time stamps are synchronised with the motion (<code>sync_sensors</code>) for runs faster than real
time; (4) exploration targets walls the camera has not yet seen from close range, so fewer passes are needed. The rotation fell
from {abs(met['campus_full_map']['rot_deg']):.0f}° to under 3°, and the final run drove {f7['len_m']:.0f} m instead of ≈470–490 m.</div>""")
    b.append(fig('campus_full_map7_preview.png', 'The final map campus_full_map7 used by the web application and the delivery navigator.'))
    b.append(f"""
<h2>6. First vs. last map</h2>""")
    b.append(table(['', 'campus (first)', 'campus6 (best campus_area)', 'campus_full_map (first two_buildings)', 'campus_full_map7 (final)'], [
        ['Markers observed', f"{c1['obs_markers']}/12", f"{met['campus6']['obs_markers']}/12", f"{met['campus_full_map']['obs_markers']}/32", f"{f7['obs_markers']}/32 (+10 added)"],
        ['Mean absolute error', f"{c1['mean_err_obs']:.1f} m", f"{met['campus6']['mean_err_obs']:.2f} m", f"{met['campus_full_map']['mean_err_obs']:.2f} m", f"{f7['mean_err_obs']:.2f} m"],
        ['Max absolute error', f"{c1['max_err_obs']:.1f} m", f"{met['campus6']['max_err_obs']:.2f} m", f"{met['campus_full_map']['max_err_obs']:.2f} m", f"{f7['max_err_obs']:.2f} m"],
        ['Shape error (rigid fit)', f"{c1['aligned_mean']:.1f} m", f"{met['campus6']['aligned_mean']:.2f} m", f"{met['campus_full_map']['aligned_mean']:.2f} m", f"{f7['aligned_mean']:.2f} m"],
        ['Global rotation', f"{abs(c1['rot_deg']):.0f}°", f"{abs(met['campus6']['rot_deg']):.1f}°", f"{abs(met['campus_full_map']['rot_deg']):.1f}°", f"{abs(f7['rot_deg']):.1f}°"],
        ['Walls', 'multiple rotated copies', 'single, straight', 'single, slightly doubled in B', 'single, sharp'],
        ['Path / sim time', f"{c1['len_m']:.0f} m / {c1['dur_s']/60:.0f} min", f"{met['campus6']['len_m']:.0f} m / {met['campus6']['dur_s']/60:.0f} min", f"{met['campus_full_map']['len_m']:.0f} m / {met['campus_full_map']['dur_s']/60:.0f} min", f"{f7['len_m']:.0f} m / {f7['dur_s']/60:.0f} min"],
        ['Usable for delivery', 'no', 'yes', 'yes, rotated', 'yes – in production'],
    ]))
    b.append(f"""
<h2>7. Observations</h2>
<ul>
<li><b>Heading was the dominant error source</b>, not marker detection. Every big improvement came from how heading is
estimated (gyro instead of wheels, gyro over marker bearings).</li>
<li><b>Absolute error and usefulness differ.</b> campus_full_map has a smaller shape error ({met['campus_full_map']['aligned_mean']:.2f} m)
than map7 ({f7['aligned_mean']:.2f} m) but is rotated 9°; map7 has sharper walls, which matters for lidar localisation and
planning through doors.</li>
<li><b>Coverage vs. marker count.</b> map7 observed 19 of 32 markers directly: the table markers face inward and were added
afterwards from the table layout (<code>aruco_landmarks_before_tables.yaml</code> holds the observed-only version). Markers 5,
44 and 49 were never detected and could be added in a short teleoperated top-up run.</li>
<li><b>Short aborted runs</b> (campus2/3, map1, map6) were start-up tests of new features and are not maps.</li>
</ul>
<div class="box"><b>Conclusion.</b> Over 13 runs the map went from unusable (rooms drawn several times, {c1['mean_err_obs']:.0f} m mean
error) to campus_full_map7, a clean map of a 70 × 45 m two-building campus with sub-0.4 m internal consistency, built
autonomously in 21 simulated minutes and now used for every delivery in the web application.</div>
<div class="box warn"><b>Next:</b> a top-up run for the three missing markers; run <code>optimize_map</code> on map7 and compare
the corrected version with the same metrics; repeat the protocol on the real robot with a tape-measured marker survey as ground
truth.</div>""")
    return page('Map Evolution: From the First Map to campus_full_map7', 6, 'Comparative, quantitative review of every ArUco SLAM mapping run in the simulation', ''.join(b))
