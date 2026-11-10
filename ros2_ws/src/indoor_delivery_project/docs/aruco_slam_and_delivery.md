# ArUco visual SLAM mapping and point-to-point delivery

Two programs in `indoor_delivery_project`:

| File | What it does |
|---|---|
| `aruco_slam_mapper.py` | **One file** that drives the robot through the whole area, records every ArUco detection (distance, bearing, marker orientation) with odometry, runs EKF-SLAM and saves the map. |
| `delivery_navigator.py` | Loads that map, localizes on the ArUco markers, plans with A* and drives point to point between the delivery points. |

## 1. Build once

```bash
cd ~/ros2_jazzy_ws
colcon build --symlink-install --packages-select indoor_delivery_project
source install/setup.bash
```

## 2. Make the map (SLAM)

Terminal 1, the simulation (robot spawns at world x=-25, y=0):

```bash
ros2 launch indoor_delivery_project sim.launch.py
```

Terminal 2, the mapper:

```bash
ros2 run indoor_delivery_project aruco_slam_mapper --ros-args \
    -p initial_pose:="[-25.0, 0.0, 0.0]" \
    -p output_dir:=~/ros2_jazzy_ws/maps/campus
```

The robot then runs on its own:

1. It turns 360° to start the map.
2. Then it keeps choosing the nearest of two kinds of goal:
   * a **frontier**: free space next to space that is not mapped yet;
   * a **viewpoint** 2.5 to 4 m in front of a wall stretch that the camera has not yet seen from up to 6 m away. Every wall is covered this way, so every marker on it gets detected from close range.
3. When nothing is left, it drives back to the start and saves. In the offline test of the campus world this took 20 to 30 min of sim time.

### Mapping faster than real time

```bash
ros2 launch indoor_delivery_project sim.launch.py rtf:=10.0              # 10x, with the Gazebo window
ros2 launch indoor_delivery_project sim.launch.py rtf:=10.0 gui:=false   # 10x, no window (fastest)
```

Then start the mapper exactly as above; nothing changes there. `rtf` is Gazebo's real_time_factor: the launch writes a copy of the world with that physics setting (in `/tmp`). The mapper and the navigator time every wait, timeout, turn and `max_duration` in simulation seconds (`/clock`), so they behave the same at any speed. 10x is a target: Gazebo runs as fast as your PC allows. The achieved factor is shown at the bottom right of the Gazebo window, or with `gz topic -e -t /world/bridge_rooms_world/stats` (look at real_time_factor). The camera and the lidar have to be rendered for every frame, so `gui:=false` and `aruco:=false` (stops the separate detector node; the mapper does its own detection, you only lose the `/aruco_detector/annotated` view) help most. To change the speed while it runs:

```bash
gz service -s /world/bridge_rooms_world/set_physics --reqtype gz.msgs.Physics \
    --reptype gz.msgs.Boolean --timeout 2000 --req 'max_step_size: 0.001, real_time_factor: 10.0'
```

To protect the CPU, the mapper processes at most `max_scan_rate` (40) lidar scans per wall second; at 10x that is 4 per simulated second, which is still plenty at 0.45 m/s. Offline test at 10x: it ran at 9.9x with no collisions, and the map quality was the same as at normal speed.

Watch it in RViz with Fixed Frame `map`: add `/map` (OccupancyGrid), `/aruco_slam_mapper/landmarks` (MarkerArray), `/aruco_slam_mapper/plan` (Path) and the RobotModel. The camera view with markers drawn is still on `/aruco_detector/annotated`.

**Ctrl+C at any time** stops the robot and saves what has been mapped so far. The map is also saved automatically every 60 s.

Useful parameters (add as `-p name:=value`):

| Parameter | Default | Meaning |
|---|---|---|
| `initial_pose` | `[0.0, 0.0, 0.0]` | Start pose in the map frame. The Gazebo spawn pose makes map coordinates equal world coordinates, and then the report shows each marker's error against `config/aruco_markers.yaml`. Use decimals (`-25.0`). |
| `output_dir` | `~/ros2_jazzy_ws/maps/aruco_slam_map` | Where the map is written. |
| `explore` | `true` | `false` = it only maps while **you** drive (pyqt_teleop / teleop); Ctrl+C saves. |
| `max_duration` | `3600.0` | Sim seconds before it stops exploring. |
| `scan_matching` | `false` | Live lidar correction while driving. Off by default: the map is drawn from gyro heading, wheel distance and markers. |
| `post_correction` | `false` | Also correct the whole trajectory at the end and write the result to `<map_dir>/corrected/` (see below). The live map is never overwritten. |
| `sync_sensors` | `true` | Uses each sensor's time stamp: camera images and scans are moved by the robot motion (gyro + wheels) between their stamp and the latest odometry. Matters at `rtf` > 1, where the topics arrive with different delays while the robot turns. |
| `max_turn_rate_for_markers` / `camera_time_error` | `0.5` / `0.1` | While the robot spins, camera timing error becomes bearing error, so marker bearings count less with the turn rate and are not used above 0.5 rad/s (also in the final correction). |
| `angular_speed` (mapper) | `0.45` | Turn speed while mapping (the navigator keeps 0.8). Slower turns give sharper scans and marker views. |
| `gyro_noise` / `gyro_alpha` | mapper `0.0003` / `[0.005, 0.0002]`, navigator `0.0015` / `[0.005, 0.001]` | How much the EKF distrusts the gyro heading (random walk per sqrt(s); per rad turned and per m driven). Very small in the mapper, so markers correct the position but cannot turn the map. |
| `use_imu` | `true` | Heading from the gyro rate on `/robot/imu/data` instead of the wheels. Wheels slip in in-place turns, which rotates the map. If no IMU data arrives, it falls back to the wheels. |
| `known_markers_only` | `true` | Ignores marker IDs that are not in `config/aruco_markers.yaml` (misreads). |
| `odom_alpha` | `[0.05, 0.05, 0.06, 0.1]` | How much the EKF distrusts odometry (x per m, y per m, yaw per rad, yaw per m). Raise it if the odometry drifts a lot. |
| `delivery_standoff` | `2.3` | How far in front of each delivery marker the delivery point is (the floor pads are 2.34 m from the wall markers). |
| `linear_speed` / `angular_speed` | `0.45` / `0.8` | Driving speeds. |
| `max_scan_rate` | `40.0` | Most lidar scans processed per wall second (CPU guard for fast simulation). `0` = all. |
| `save_scans` | `true` | Also save the raw scans (`scans.npz`) for `correct_map`. |

### What is saved in `output_dir`

| File | Content |
|---|---|
| `aruco_landmarks.yaml` | The landmark map: for each marker its id, name, x, y, the direction it faces (yaw), its uncertainty and number of observations. Also `delivery_points` (name → x, y, yaw) and `start_pose`. You can edit it or add your own points. |
| `map.pgm` + `map.yaml` | Occupancy grid in the Nav2 map_server format, so Nav2 can use it too. |
| `observations.csv` | The recorded detections: time, marker id, 3D distance, 2D range, bearing, marker facing, pixel size, SLAM pose and raw odometry pose. |
| `trajectory.csv` | The robot path (SLAM and odometry). |
| `scans.npz` | Raw lidar scans with their poses, for `correct_map` (section 5). |
| `map_preview.png` | Picture of the map: walls the camera has seen in green, markers in red, delivery points as stars, and the driven path in blue. |

### Trajectory correction after mapping

While the robot drives, the map is built from the EKF (markers + wheel distance + gyro heading); live lidar correction is off by default (`scan_matching:=false`). The heading follows the gyro closely, so a marker re-sighting can no longer turn the map, and nothing redraws the map after it is drawn. Optionally, `map_optimizer` corrects the whole trajectory afterwards (`post_correction:=true`, or `ros2 run indoor_delivery_project optimize_map <map_dir>`):

* a pose graph of keyframes every 0.3 m / 10°, with odometry edges (wheel distance + gyro heading), an edge for every marker detection, and lidar loop edges (each keyframe scan matched against the map drawn by the other parts of the run);
* solved with robust Gauss-Newton (numpy only), in 3 rounds of draw map → match scans → optimize;
* the map, markers and delivery points are then redrawn from the corrected trajectory.

It writes into `<map_dir>/corrected/` and never touches the live map: `map.pgm`/`map.yaml`, `aruco_landmarks.yaml`, `map_preview.png` (blue: corrected path, pink: live path), `trajectory_corrected.csv` and `correction_report.txt`. To navigate on the corrected version: `-p map_dir:=<map_dir>/corrected`.

The gyro needs `<plugin filename="gz-sim-imu-system" name="gz::sim::systems::Imu"/>` in the world; without it Gazebo never publishes `/robot/imu/data`, the heading comes from slipping wheels, and the mapper prints a warning.

### How the SLAM works

* **State**: EKF over the robot pose plus the x, y of every marker. The marker ID handles data association, so there are no wrong matches.
* **Prediction**: wheel odometry for distance and the gyro for heading. The lidar matcher corrects x and y but leaves the heading to the gyro.
* **Correction**: each detection's range and bearing, in the base frame, from `solvePnP` (IPPE_SQUARE) with the marker size from `config/aruco_markers.yaml`. The noise grows with distance and shrinks with the marker's size in pixels. A marker seen for the first time is added to the state.
* **Marker orientation**: a weighted average of the marker normal, used for the delivery points and for relocalization.
* **Lidar**: correlative scan-to-map matching adds a pose correction between marker sightings. It is most useful in the 30 m corridor, where no marker is visible. The occupancy grid is drawn at the corrected pose.

## 3. Deliver between the delivery points

Restart the simulation so the robot is back at the start, then run:

```bash
# A fixed route, then back home:
ros2 run indoor_delivery_project delivery_navigator --ros-args \
    -p map_dir:=~/ros2_jazzy_ws/maps/campus \
    -p deliveries:="['left_delivery_point_1', 'right_delivery_point_3', 'left_delivery_point_4']"

# Interactive: it lists the points, and you type a name or a number:
ros2 run indoor_delivery_project delivery_navigator --ros-args \
    -p map_dir:=~/ros2_jazzy_ws/maps/campus
```

You can also send goals from another terminal or program while it runs:

```bash
ros2 topic pub --once /delivery_navigator/goal std_msgs/msg/String "{data: right_delivery_point_2}"
ros2 topic echo /delivery_navigator/status
```

For each delivery the navigator:

1. Plans the shortest path with Dijkstra on a clearance map of the saved grid: every 0.2 m cell knows its distance to the nearest wall (measured on the 0.1 m map), cells closer than `robot_radius` are not driven through, and cells near walls cost more, so the path keeps to the middle of doors and corridors. To stay robust:
   * it plans again from the current pose every `replan_period` (15 s) and after every pose correction, so it never keeps following a stale path;
   * a delivery point that lies too close to a wall or table is replaced by the closest reachable spot with room around it (the log says how far before the point it stopped);
   * obstacles the lidar finds are kept for `obstacle_memory` (30 s) only and are dropped when the pose is corrected, so an old detour or a wall seen from a wrong pose can never close a corridor the robot already drove;
   * if no path is found it relaxes step by step (without the remembered obstacles, then 0.1 m less safety margin, then unknown cells allowed) instead of stopping;
   * stopping for something in front within 0.7 m of the goal counts as arrived.
2. Drives the path with pure pursuit. If the lidar sees something in front, it stops. If the obstacle stays more than 2 s, it adds it to the map and replans around it.
3. At the point, turns to face the delivery marker, checks that the camera sees the right marker ID, waits `dwell_time` (3 s) and reports `Delivered`.

Localization combines odometry with every marker in `aruco_landmarks.yaml` (as known beacons) and lidar matching against the saved map.

| Parameter | Default | Meaning |
|---|---|---|
| `map_dir` | `~/ros2_jazzy_ws/maps/aruco_slam_map` | The folder the mapper wrote. |
| `initial_pose` | `home` | `home` = the mapping start pose. `auto` = the robot turns until it sees a marker and computes its pose from that one marker (works anywhere a marker is in view, which is not the case in the middle of the corridor). You can also give `"[x, y, yaw]"` or a delivery point name. |
| `deliveries` | none | The route. Leave it empty for interactive mode, or for topic goals only. |
| `return_home` | `true` | Go back to `home` after the route. |
| `dwell_time` | `3.0` | Seconds to wait at each delivery point. |
| `goal_tolerance` | `0.15` | Metres. |

## 4. Multipoint delivery: start at A, visit x, y, z, finish at B

```bash
ros2 run indoor_delivery_project delivery_navigator --ros-args \
    -p map_dir:=~/ros2_jazzy_ws/maps/campus \
    -p route_start:=home \
    -p stops:="['right_delivery_point_1', 'left_delivery_point_4', 'right_delivery_point_3', 'left_delivery_point_1']" \
    -p route_end:=right_delivery_point_4
```

In interactive mode you can type the same route as one line, with the start first and the end last (names or list numbers both work): `route home 5 4 7 1 8`.

How the route is planned:

1. **Dijkstra on the SLAM map.** The saved occupancy grid is turned into a 0.2 m planning grid. Walls are inflated by the robot radius, and cells near walls cost extra. One full Dijkstra run from the start and from each stop gives the real driving distance between every pair of points (a distance matrix).
2. **Best visiting order.** For up to 12 stops it checks every order exactly (Held-Karp dynamic programming). For more stops it uses nearest neighbour plus 2-opt. The start and end stay fixed.
3. **Driving.** It prints each leg with its length, publishes the whole route on `/delivery_navigator/route` (a Path to show in RViz), then drives leg by leg. Each leg is planned again with Dijkstra from the robot's current pose, so obstacles are still avoided. At every stop it delivers (turns to the marker, checks the ID, waits `dwell_time`).

| Parameter | Default | Meaning |
|---|---|---|
| `route_start` | empty = where the robot is now | Start point A. If the robot is somewhere else, it drives there first. |
| `stops` | none | Delivery points x, y, z, in any order. |
| `route_end` | empty = back to the start | Finish point B (any delivery point or `home`). |
| `optimize_order` | `true` | `false` = visit the stops in the given order. |

Offline example from home, with stops right 1, left 4, right 3, left 1 and end at right 4: the shortest order is left 4, left 1, right 1, right 3, then right 4. It is 173.8 m long, against 377.5 m in the given order. The robot drove 173 m and delivered at all 4 stops, 0.11 to 0.15 m from the pads.

## 5. Correct a later map with the first map as the base

When the first map is good and a later mapping run is spoiled by wheel slip, `correct_map` re-processes the later run offline and fixes it with the first map. The first map has priority.

The later run must be made with the current mapper, which also saves the raw lidar scans in `scans.npz` (parameter `save_scans`, default `true`). The first map does not need `scans.npz`, so your existing `campus` map can be the base.

```bash
# 1. Make the new run as usual (new folder):
ros2 run indoor_delivery_project aruco_slam_mapper --ros-args \
    -p initial_pose:="[-25.0, 0.0, 0.0]" -p output_dir:=~/ros2_jazzy_ws/maps/campus2

# 2. Correct it with the first map as the base (no simulation needed):
ros2 run indoor_delivery_project correct_map \
    --base ~/ros2_jazzy_ws/maps/campus \
    --run  ~/ros2_jazzy_ws/maps/campus2 \
    --out  ~/ros2_jazzy_ws/maps/campus_corrected
```

What it does:

1. **Re-aligns every scan on the base map.** It starts from the run's start pose (a coarse search fixes small offsets; use `--initial-pose x y yaw` if the run started somewhere else), predicts each next pose from the run's own wheel odometry, then matches the scan against the base occupancy grid. The match and the odometry are fused with a Kalman filter, so a long corridor only corrects across the corridor. Where the base map knows nothing, the scan is matched against what the run itself has mapped so far.
2. **Detects slips.** Over a window of 10 scans it compares the motion from the wheels with the corrected motion. Where heading differs by more than `--slip-yaw-deg` (3°) or position by more than `--slip-dist` (0.2 m), it records a slip event with time, place and size.
3. **Merges, base first.** Cells the base map knows keep the base value. Cells only the run has seen are added. Cells where the run clearly disagrees with the base (for example a moved box) are counted and drawn in red; `--accept-changes` applies them. Base markers keep their positions. Markers the base does not have are added from the corrected run, with their delivery points.

Output folder (a normal map folder, so `delivery_navigator -p map_dir:=...` works with it):

| File | Content |
|---|---|
| `map.pgm` + `map.yaml`, `aruco_landmarks.yaml` | The corrected, merged map. |
| `run_corrected.pgm` + `.yaml` | The later run alone, redrawn at the corrected poses. |
| `slip_events.csv` | Each slip: start and end time, x, y, heading error, position error. |
| `corrected_trajectory.csv` | Per scan: corrected pose, wheel odometry, the run's own SLAM pose, and what it was matched on. |
| `correction_report.txt` | Summary, marker differences against the base, the largest slips. |
| `correction_preview.png` | Green: corrected path. Red line: the run's own SLAM path. Orange circles: slips. Blue: added from the run. Red cells: disagreements. |

Offline test: a run with 15% rotational wheel slip and no gyro had marker errors up to 72.7 m. Corrected on the first map, every marker of the run was within 0.07 m of the base, and 148 slip events were found (the 360° start turn alone slipped 50°). Areas the base map does not cover are only as good as the run itself: with half the base map removed, the new half came out up to 2.4 m off. So keep the base map complete, and keep `use_imu` on.

## Offline test results (2D replica of campus_area.sdf)

Both programs were run unchanged against a Python replica of the world: the same walls and markers, a lidar mounted upside down like in the URDF, marker corners projected through the real camera model into the real `solvePnP` code, and noisy odometry. Gazebo itself was not run.

* **Mapping**, with odometry noise at Gazebo level (0.5%): the whole area was explored in 20 to 31 min of sim time with no collisions. All 12 markers were found, each within 0.14 m of its true world position, and 100% of the walls were seen by the camera.
* **Mapping with heavy odometry drift (2%)**: still complete, but marker errors grow to as much as 1.4 m. On the real robot, calibrate the wheel odometry or turn on `use_imu`.
* **Delivery**: a route of left 1, right 3, left 4, right 1, then home ended 0.08 to 0.16 m from the real floor pads, with the right marker confirmed each time. The navigator also went around a box placed in the corridor, and relocalized with `initial_pose:=auto` from two places where a marker was in view.

## Notes for the real robot later

* Use `-p sim:=false`, and point `odom_topic`, `scan_topic`, `image_topic`, `camera_info_topic` and `cmd_vel_topic` at the real robot's topics.
* Set `camera_offset` to the real camera position in base_link, and use a calibrated `camera_info`.
* The marker sizes in `config/aruco_markers.yaml` must match the printed markers (black square edge, in metres). Distance accuracy depends directly on them.
* Markers that are not in the config are still mapped, with a default size of 0.30 m.
