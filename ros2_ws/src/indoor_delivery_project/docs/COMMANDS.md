# Command list: ArUco SLAM, delivery and map correction

Every new terminal first:

```bash
cd ~/ros2_jazzy_ws && source install/setup.bash
```

## Build (after any code change)

```bash
cd ~/ros2_jazzy_ws
colcon build --symlink-install --packages-select indoor_delivery_project
source install/setup.bash
```

## Simulation (terminal 1)

```bash
ros2 launch indoor_delivery_project sim.launch.py                          # normal speed
ros2 launch indoor_delivery_project sim.launch.py rtf:=10.0                # 10x faster
ros2 launch indoor_delivery_project sim.launch.py rtf:=10.0 gui:=false     # 10x, no Gazebo window (fastest)
ros2 launch indoor_delivery_project sim.launch.py rtf:=10.0 gui:=false aruco:=false   # also without the extra detector node
```

Start with `rtf:=3.0` to `5.0`. If Gazebo cannot keep up (for example `libEGL warning: egl: failed to create dri2 screen`, which means it renders on the CPU instead of the NVIDIA GPU), a high value like 50 does not run faster; it can even make controllers time out at start (`Switch controller timed out`, `Failed to activate controller: joint_state_broadcaster`).

Check the speed actually reached (real_time_factor):

```bash
gz topic -e -t /world/bridge_rooms_world/stats | grep real_time_factor
```

Change the speed while it runs:

```bash
gz service -s /world/bridge_rooms_world/set_physics --reqtype gz.msgs.Physics \
    --reptype gz.msgs.Boolean --timeout 2000 --req 'max_step_size: 0.001, real_time_factor: 10.0'
```

## Mapping (terminal 2)

```bash
# Automatic exploration of the whole area, saved to maps/campus2
ros2 run indoor_delivery_project aruco_slam_mapper --ros-args \
    -p initial_pose:="[-25.0, 0.0, 0.0]" \
    -p output_dir:=~/ros2_jazzy_ws/maps/campus2

# Manual mode: after the 360 deg turn the robot WAITS for you to drive it
# (pyqt_teleop or teleop). It does not move on its own. Ctrl+C saves.
ros2 run indoor_delivery_project aruco_slam_mapper --ros-args \
    -p initial_pose:="[-25.0, 0.0, 0.0]" -p explore:=false \
    -p output_dir:=~/ros2_jazzy_ws/maps/campus2
```

The same mapper command works at any simulation speed. Ctrl+C stops and saves.

Check the log for `Gyro yaw rate in use for heading prediction`. If you see `No gyro data on /robot/imu/data` instead, the world is missing the IMU system (it is in `worlds/campus_area.sdf` now; rebuild).

While driving, the mapper only uses the markers, the wheels and the gyro, and the heading follows the gyro closely. The map it draws (`map.pgm` / `map.yaml`, `aruco_landmarks.yaml`) is the final map: nothing rewrites it afterwards. An optional correction of the whole trajectory can be run afterwards; it writes into a `corrected/` sub-folder of the map folder and leaves the live map alone (to navigate on it: `-p map_dir:=<map_dir>/corrected`):

```bash
ros2 run indoor_delivery_project optimize_map ~/ros2_jazzy_ws/maps/campus2
```

To run it automatically at the end of mapping: `-p post_correction:=true` (default off).

Camera and lidar are lined up with the odometry by their time stamps (`sync_sensors`, default on).

Look at the result:

```bash
ls ~/ros2_jazzy_ws/maps/campus2
xdg-open ~/ros2_jazzy_ws/maps/campus2/map_preview.png
```

RViz (Fixed Frame `map`): add `/map`, `/aruco_slam_mapper/landmarks`, `/aruco_slam_mapper/plan`, RobotModel.

```bash
rviz2
```

## Correct a later map with the first good map as the base

```bash
ros2 run indoor_delivery_project correct_map \
    --base ~/ros2_jazzy_ws/maps/<first_good_map> \
    --run  ~/ros2_jazzy_ws/maps/<later_run> \
    --out  ~/ros2_jazzy_ws/maps/campus_corrected

xdg-open ~/ros2_jazzy_ws/maps/campus_corrected/correction_preview.png
cat ~/ros2_jazzy_ws/maps/campus_corrected/correction_report.txt
```

Options: `--accept-changes` (take changed cells from the later run), `--initial-pose x y yaw` (if the later run started elsewhere), `--slip-yaw-deg 3`, `--slip-dist 0.2`.

## Delivery app (PyQt5)

Restart the simulation first, so the robot is at home. Then:

```bash
ros2 run indoor_delivery_project delivery_gui --ros-args -p map_dir:=~/ros2_jazzy_ws/maps/campus6
```

* Type a mission in **Quick** as point numbers: start, stops, end. `3 4 6 7 5` means go to 3, deliver at 4, 6 and 7, finish at 5. You can also pick Start/End in the lists, type the stops, or click points on the map to add stops.
* **Plan route**: Dijkstra on the map gives the real driving distance between every pair of points, then the shortest order of the stops is found exactly. The route is drawn (dashed: robot to the start) and every leg is listed with its length, next to the length of the stops in the typed order.
* **Start mission** drives it and delivers at each point (turns to the marker, checks the ID, waits `dwell_time`). **STOP** halts the robot at once.
* Untick **Shortest order** to visit the stops exactly as typed; untick **Deliver at the start point** to only drive there.
* **Pose = home** / **Find pose (markers)** if the robot is not at the start pose.

Numbers: 1-4 = left_delivery_point_1-4, 5-8 = right_delivery_point_1-4, H = home (as shown on the map).

## Robot vision (camera stream with detection and navigation)

The delivery app shows the robot camera under the map. For SLAM mapping (or next to any other program) open the separate window:

```bash
ros2 run indoor_delivery_project robot_vision
```

On the camera image:

* **green outline**: ArUco marker with ID, name, distance and bearing;
* **orange box**: obstacle found by the lidar that is not a wall on the map (**red** when it is in the robot's path), with its distance;
* **blue line on the floor**: the planned path; **yellow pin**: the goal with its distance (an arrow when it is off screen);
* **top bar**: pose, speed, number of detections and the navigator status.

The robot_vision window also shows the live map (`/map`) with the robot and its path, so you can watch SLAM build the map.

Optional object detection with YOLO (people, boxes, chairs, ...): `pip install ultralytics`, then it switches on by itself (`-p detector:=yolo` to insist, `-p detector:=none` to turn it off). The first start downloads `yolov8n.pt`; use `-p yolo_model:=/path/to/model.pt` for your own. The distance of each object comes from the lidar. The campus world has no such objects, so in Gazebo you will mostly see markers and lidar obstacles unless you add models.

## Delivery from the terminal (restart the simulation first, so the robot is at home)

```bash
# Fixed route, then back home
ros2 run indoor_delivery_project delivery_navigator --ros-args \
    -p map_dir:=~/ros2_jazzy_ws/maps/campus2 \
    -p deliveries:="['left_delivery_point_1', 'right_delivery_point_3', 'left_delivery_point_4']"

# Interactive: type a point name or number, or: route home 5 4 7 1 8
ros2 run indoor_delivery_project delivery_navigator --ros-args \
    -p map_dir:=~/ros2_jazzy_ws/maps/campus2

# Multipoint: start A, best order through the stops (Dijkstra + exact order), finish B
ros2 run indoor_delivery_project delivery_navigator --ros-args \
    -p map_dir:=~/ros2_jazzy_ws/maps/campus2 \
    -p route_start:=home \
    -p stops:="['right_delivery_point_1', 'left_delivery_point_4', 'right_delivery_point_3']" \
    -p route_end:=right_delivery_point_4

# Start somewhere else: let it find itself from a visible marker
ros2 run indoor_delivery_project delivery_navigator --ros-args \
    -p map_dir:=~/ros2_jazzy_ws/maps/campus2 -p initial_pose:=auto
```

Send goals and watch the status from another terminal:

```bash
ros2 topic pub --once /delivery_navigator/goal std_msgs/msg/String "{data: right_delivery_point_2}"
ros2 topic echo /delivery_navigator/status
```

## Manual driving and camera

```bash
ros2 run indoor_delivery_project pyqt_teleop
ros2 run rqt_image_view rqt_image_view /aruco_detector/annotated
```

## Two-building world (world:=two_buildings)

Layout (clear inside sizes, top view in `docs/two_buildings_top_view.png`):
building A 15 x 40 m (x -28..-13) -> two short corridors 3 x 7 m (y 7.5..10.5 and -10.5..-7.5)
-> cross corridor 10 x 28 m (x -6..4, y -14..14) -> two right corridors 6 x 28 m
(x 4..32, y 6..12 and -12..-6) -> building B, a thin 7.5 x 40 m hall (x 32..39.5). The robot spawns in A at (-17, -17) facing +x.

Delivery points (`config/aruco_markers_two_buildings.yaml`):
- `a_delivery_point_1..10`: 10 table groups (desk + 2 chairs) in A, two columns of 5.
  1-5 = left (west) column north to south, delivery side facing east;
  6-10 = right column north to south, delivery side facing west (left), so both
  columns are served from the aisle between them. Marker on the desk front (ids 40-49);
  the robot stops 1.2 m in front of the desk.
- `c_delivery_point_1..4`: two small desks against the right (east) wall of the cross
  corridor at y = +3.5 and -3.5 (its long middle section, between the right corridors), two markers each on the
  west face: 1, 2 = north desk, 3, 4 = south desk (ids 36-39), stop 1.2 m away.
- `r_delivery_point_1..4`: desks in the right corridors at x = 13.3 and 22.7, against the
  outer wall: 1, 2 = upper (north) corridor, 3, 4 = lower (south) corridor (ids 12-15),
  stop 1.2 m away.
- `b_delivery_point_1..4`: B east wall with yellow pads (ids 5-8), default 2.3 m stop.
- Room markers 10/11 (A) and 20/21 (B), corridor landmarks 30-35.
The 1.2 m comes from `standoff:` in the marker YAML (per-marker; markers without it use
the mapper's `delivery_standoff`, 2.3 m). The world and YAML are generated by
`scripts/generate_two_buildings_world.py` (edit it and rerun, then rebuild).

```bash
# Rebuild once so the new world/config/models are installed
colcon build --symlink-install --packages-select indoor_delivery_project && source install/setup.bash

# Simulation (spawn pose and detector markers follow the world automatically)
ros2 launch indoor_delivery_project sim.launch.py world:=two_buildings rtf:=5.0

# Mapping: give the mapper the same marker file and the spawn pose
MK=$(ros2 pkg prefix indoor_delivery_project)/share/indoor_delivery_project/config/aruco_markers_two_buildings.yaml
ros2 run indoor_delivery_project aruco_slam_mapper --ros-args \
    -p initial_pose:="[-17.0, -17.0, 0.0]" -p markers_file:=$MK \
    -p output_dir:=~/ros2_jazzy_ws/maps/two_buildings1

# Delivery GUI / navigator on that map. Marker names and sizes are read from the
# map folder itself (aruco_landmarks.yaml), so map_dir is all they need.
ros2 run indoor_delivery_project delivery_gui --ros-args \
    -p map_dir:=~/ros2_jazzy_ws/maps/campus_full_map7
ros2 run indoor_delivery_project delivery_navigator --ros-args \
    -p map_dir:=~/ros2_jazzy_ws/maps/two_buildings1 -p markers_file:=$MK \
    -p deliveries:="['a_delivery_point_7', 'c_delivery_point_2', 'b_delivery_point_3', 'home']"
ros2 run indoor_delivery_project robot_vision --ros-args -p markers_file:=$MK
```

Gazebo topics use the world name: `/world/two_buildings_world/stats`, `/world/two_buildings_world/set_physics`.
The default (no world:=) is still the campus world, unchanged.

Snapshot of the working campus setup before this change: `~/ros2_jazzy_ws/backups/campus_working_2026-11-04/`
(+ `.tar.gz`): package source, robot description and `maps/campus6`.
