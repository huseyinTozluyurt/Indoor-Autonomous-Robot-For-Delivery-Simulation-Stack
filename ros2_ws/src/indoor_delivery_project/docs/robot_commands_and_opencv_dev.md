# Robot commands and OpenCV/ArUco development

## 1. One-time setup
```
cd ~/ros2_jazzy_ws/src/indoor_delivery_project
bash dev/setup_opencv_dev.sh             # add --notebook for Jupyter + matplotlib
cd ~/ros2_jazzy_ws
colcon build --symlink-install --packages-select indoor_delivery_project
source install/setup.bash
python3 src/indoor_delivery_project/dev/check_opencv_env.py
```
Use the apt OpenCV (`python3-opencv`, 4.6, already has `cv2.aruco`). A pip
`opencv-contrib-python` next to ROS brings numpy 2 and breaks `cv_bridge`;
the check script warns if `cv2` comes from pip.

## 2. Built-in robot commands (`indoor_delivery_project.robot_commands`)
Start the sim first: `ros2 launch indoor_delivery_project sim.launch.py`.

```python
from indoor_delivery_project.robot_commands import Robot

with Robot() as robot:          # stops the robot on exit / Ctrl+C
    robot.forward(1.0)          # metres (odometry feedback)
    robot.turn_left(90)         # degrees
    robot.backward(0.5)
    robot.turn_right(45)
    robot.forward_for(2.0)      # seconds
    robot.go_to(0.0, 0.0)       # odom frame (start pose = 0, 0)
```
Short form: `from indoor_delivery_project.robot_commands import forward, turn_left, shutdown`.

| Command | What it does |
|---|---|
| `forward(m)`, `backward(m)`, `move(signed_m)` | Drive a distance, holding the heading, slowing near the goal |
| `turn_left(deg=90)`, `turn_right(deg=90)`, `turn(signed_deg)` | Turn in place (positive = left); >180 works |
| `turn_to(deg)` | Absolute heading in the odom frame |
| `go_to(x, y)` | Turn to face (x, y), then drive there |
| `forward_for(s)`, `backward_for(s)`, `turn_left_for(s)`, `turn_right_for(s)` | Timed moves (sim seconds) |
| `drive(v, w, s)` | Any velocity for s seconds |
| `stop()`, `sleep(s)`, `get_pose()` | Stop, wait while staying responsive, (x, y, yaw_deg) |
| `wait_for_marker(id, timeout)`, `search_marker(id)`, `visible_markers()` | Use `/aruco_detector/detections` |

Every motion takes an optional `speed=` (m/s or rad/s) and raises
`MotionTimeout` if the goal is not reached (robot blocked, sim paused).
Defaults: 0.3 m/s, 0.6 rad/s; controller limits 0.8 m/s and 1.5 rad/s.

Topics: publishes `geometry_msgs/Twist` on `/cmd_vel` (the launch file's
`twist_to_stamped_bridge` forwards it); reads `/robot/diff_drive_controller/odom`.
Without odometry it falls back to timed motion and logs a warning.
Real robot: `Robot(use_sim_time=False, cmd_vel_topic=..., odom_topic=...)`.

Full example: `examples/my_robot_mission.py` (square, timed moves, return
home, look for marker 10). Copy it anywhere; it only needs the workspace sourced.

## 3. Experimenting with ArUco detection
- `dev/aruco_playground.py`: live window. Edit `process()` at the top and re-run
  (no build needed). Sources: `--source ros` (sim mast camera, default),
  `--source 0` (webcam for real-world tests), an image or a video file.
  Keys: `s` save frame to `dev/snapshots/`, `space` pause, `r` rejected
  candidates, `t` threshold view, `q` quit.
- `dev/aruco_scratch.py`: `# %%` cells for VS Code "Run Cell" / Jupyter: grab one
  sim frame, detect, plot. Launch VS Code from a sourced terminal.
- `indoor_delivery_project/aruco_utils.py`: `MarkerDetector`, `estimate_pose`,
  `draw`, `generate_marker`, `grab_ros_frame`; same code on OpenCV 4.6 and 4.7+.

Typical loop: drive with the commands (or `pyqt_teleop`) to where detection is
flaky, press `s` in the playground, then tune on the saved frame with
`--source dev/snapshots/<file>.png`. Move what works into `aruco_detector.py`.
