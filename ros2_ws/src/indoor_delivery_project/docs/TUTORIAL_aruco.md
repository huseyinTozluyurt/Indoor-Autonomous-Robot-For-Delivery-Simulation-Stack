# Tutorial: launch the sim, drive the robot and use ArUco detection

Workspace: `~/ros2_jazzy_ws`, package `src/indoor_delivery_project`.
Each "Terminal" below is a new terminal window. Every terminal needs the two
`source` lines first (or add them to `~/.bashrc`):

```bash
source /opt/ros/jazzy/setup.bash
source ~/ros2_jazzy_ws/install/setup.bash
```

---

## 0. One-time setup

```bash
sudo apt update
sudo apt install -y ros-jazzy-ros-gz ros-jazzy-gz-ros2-control ros-jazzy-ros2-controllers \
    python3-pyqt5 ros-jazzy-rqt-image-view
bash ~/ros2_jazzy_ws/src/indoor_delivery_project/dev/setup_opencv_dev.sh   # OpenCV + cv_bridge
```

## 1. Build

```bash
cd ~/ros2_jazzy_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select indoor_delivery_robot_description indoor_delivery_project
source install/setup.bash
```

The build must end with `Summary: 2 packages finished` and no `failed`. If it
fails, Gazebo will start without the marker models (see Pitfalls 1).

Check the environment once:
```bash
python3 src/indoor_delivery_project/dev/check_opencv_env.py
```

Rebuild only when you change `setup.py`, `package.xml`, launch/config/world/model
files or the URDF. Python edits in `indoor_delivery_project/`, `examples/` and
`dev/` are picked up without rebuilding (thanks to `--symlink-install`).

## 2. Launch the simulation (Terminal 1)

```bash
ros2 launch indoor_delivery_project sim.launch.py
```

This starts Gazebo with the campus world, spawns the RB1 at x = -25 m, the
`ros_gz_bridge` (clock, laser, IMU, cameras), the diff drive controller,
`twist_to_stamped_bridge` (`/cmd_vel` -> controller) and the `aruco_detector`.
It is ready when the log shows `Configured and activated diff_drive_controller`.

Options:
| Argument | Default | Meaning |
|---|---|---|
| `aruco:=false` | `true` | don't start the ArUco detector |
| `record:=true` | `false` | record rosbag + camera video to `~/robot_recordings` |
| `x_pose:= y_pose:= yaw:=` | `-25 0 0` | spawn pose |

## 3. Drive by hand (Terminal 2)

```bash
ros2 run indoor_delivery_project pyqt_teleop
```
Hold W/S (or Up/Down) to drive, A/D (or Left/Right) to turn in place, Q/E to
curve forward-left/right. Sliders set the speed, EMERGENCY STOP latches a stop.
Odometry is shown live.

## 4. See what the detector sees (Terminal 3)

```bash
ros2 run rqt_image_view rqt_image_view /aruco_detector/annotated
```
Drive towards a marker: it gets a green outline, its id, name and distance.

Useful topics:
```bash
ros2 topic echo /aruco_detector/detections   # JSON: id, name, kind, room, distance_m
ros2 topic echo /robot/current_room          # last room marker seen
ros2 topic echo /aruco_detector/poses        # PoseArray, camera optical frame
ros2 topic hz /robot/aruco_camera/image_raw  # should be ~15 Hz
```

Marker map (DICT_4X4_50, details in `docs/aruco_and_camera.md`):
| ID | Where |
|---|---|
| 1-4 | left room delivery points (30 cm) |
| 5-8 | right room delivery points (30 cm) |
| 10 / 20 | far wall of left / right room (1 m) |
| 11 / 21 | inside the doorway of left / right room (60 cm) |

## 5. Use ArUco detection from your own Python file

Put your scripts in `src/indoor_delivery_project/examples/` and run them with
`python3` (sim running, workspace sourced). Two levels:

### 5a. Use the detector node's results (simplest)

```python
from indoor_delivery_project.robot_commands import Robot

with Robot() as robot:
    det = robot.search_marker(10)          # turn left in steps until id 10 is seen
    if det:
        print(det['name'], det.get('distance_m'))
        robot.forward(det['distance_m'] - 1.5)   # drive up to ~1.5 m in front

    print(robot.visible_markers())         # everything the detector sees now
    det = robot.wait_for_marker(3, timeout=5)    # None if not seen in 5 s
```

### 5b. Do the detection yourself (full control)

```python
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from indoor_delivery_project import aruco_utils
from indoor_delivery_project.image_utils import image_to_bgr
from indoor_delivery_project.robot_commands import Robot

detector = aruco_utils.MarkerDetector('DICT_4X4_50')
latest = {}

with Robot() as robot:
    # Robot.node is a normal rclpy node; its callbacks run during robot commands
    robot.node.create_subscription(Image, '/robot/aruco_camera/image_raw',
                                   lambda m: latest.update(img=m), qos_profile_sensor_data)
    robot.sleep(0.5)                       # wait for a frame
    corners, ids, _ = detector.detect(image_to_bgr(latest['img']))
    print('ids:', None if ids is None else ids.ravel().tolist())
```

A complete version that finds a marker, computes its distance and bearing with
`aruco_utils.estimate_pose`, turns to face it and drives up to it:
```bash
python3 src/indoor_delivery_project/examples/approach_marker.py 10 --stop 1.5
```

### Robot commands you can combine with detection
`forward(m)`, `backward(m)`, `turn_left(deg)`, `turn_right(deg)`, `turn(deg)`,
`turn_to(deg)`, `go_to(x, y)`, `forward_for(s)`, `stop()`, `get_pose()`,
`sleep(s)`. Full table: `docs/robot_commands_and_opencv_dev.md`.
Example mission: `examples/my_robot_mission.py`.

## 6. Experiment with detection settings

```bash
python3 src/indoor_delivery_project/dev/aruco_playground.py           # live sim camera
python3 src/indoor_delivery_project/dev/aruco_playground.py --source 0   # webcam
```
Edit `process()` at the top of the file and re-run. `s` saves the frame to
`dev/snapshots/` so you can tune on it later with `--source <file.png>`.
`dev/aruco_scratch.py` has the same steps as VS Code / Jupyter cells.

---

## Pitfalls (things we already hit)

1. **Gazebo exits with `Unable to find uri[model://aruco_marker_1]`.**
   The build failed earlier, so the models were never installed. Cause last
   time: a `__pycache__` folder inside `launch/` made colcon stop with
   `can't copy .../launch/__pycache__`. `setup.py` now installs only files and
   skips `__pycache__`, so just rebuild and check for `2 packages finished`.
   If it happens again: `rm -rf src/indoor_delivery_project/launch/__pycache__`
   and rebuild. The `KeyboardInterrupt` tracebacks after this error are only the
   other nodes shutting down.

2. **A marker is visible in Gazebo but never detected.** Its texture is
   probably mirrored. In `scripts/generate_aruco_models.py` swap the U texture
   coordinates in the DAE template (`0 0  1 0  1 1  0 1` -> `1 0  0 0  0 1  1 1`),
   run `python3 scripts/generate_aruco_models.py` from the package root, rebuild.
   Quick test: save a frame in the playground and check whether the marker
   looks like its PNG in `models/aruco_marker_<id>/meshes/` or a mirror image.

3. **TF frames are `robot/odom` and `robot/base_link`** (RViz shows no robot,
   SLAM drops every scan). Jazzy's diff drive controller prefixes TF frames with
   the namespace. Fix used in the SLAM workspace: in
   `config/rb1_diff_drive_controllers.yaml`, under
   `/robot/diff_drive_controller: ros__parameters:`, add
   ```yaml
       tf_frame_prefix_enable: false
   ```
   then rebuild. Driving, odometry and the ArUco scripts work without it; it
   matters for RViz, SLAM and Nav2.

4. **Robot does not move.** Check `ros2 topic echo /cmd_vel` while you press a
   key, and that the launch log says the diff drive controller is active.
   `ros2 control list_controllers -c /robot/controller_manager` should list
   both controllers as `active`.

5. **`No odometry` warning from `Robot()`.** The sim is not running or the
   controller is not up yet; commands then fall back to timed moves. Check
   `ros2 topic hz /robot/diff_drive_controller/odom`.

6. **`cv2` / `cv_bridge` import errors or numpy 2 errors.** A pip OpenCV or numpy
   in `~/.local` is shadowing the apt one. `check_opencv_env.py` tells you which
   `cv2` is loaded; remove the pip one with
   `pip uninstall opencv-python opencv-contrib-python`.

7. **Two workspaces.** `~/Desktop/indoor_autonomous_robot_slam` has the same
   package names. Never source both in the same terminal.

8. **Warnings you can ignore:** `ROS_LOCALHOST_ONLY is deprecated` and the
   `turtlesim_pathFinding` naming warning.
