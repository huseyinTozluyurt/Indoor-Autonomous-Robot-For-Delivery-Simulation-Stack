# indoor_autonomous_robot_slam

SLAM-only copy of `~/ros2_jazzy_ws` (ROS 2 Jazzy + Gazebo Harmonic). The robot
keeps the lidar (Hokuyo UST-20LX, `/robot/front_laser/scan`), the IMU
(`/robot/imu/data`), wheel odometry and the diff drive; all cameras and ArUco
parts are removed.

## Build

```bash
cd ~/Desktop/indoor_autonomous_robot_slam
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

Don't source `~/ros2_jazzy_ws/install` in the same terminal: both workspaces
have packages named `indoor_delivery_project`.

## Run mapping

```bash
ros2 launch indoor_delivery_project slam.launch.py      # Gazebo + slam_toolbox + RViz
ros2 run indoor_delivery_project pyqt_teleop            # second terminal: drive around
mkdir -p ~/maps && ros2 run nav2_map_server map_saver_cli -f ~/maps/campus_area --ros-args -p use_sim_time:=true
```

Launch arguments of `slam.launch.py`: `sim:=false` (slam_toolbox + RViz only),
`rviz:=false`, `use_sim_time`, `slam_params_file`. `sim.launch.py` alone still
starts just Gazebo + robot.

## Differences from ~/ros2_jazzy_ws

- Removed: ArUco marker models and world entries, `config/aruco_markers.yaml`,
  `scripts/`, `aruco_detector`, `aruco_utils`, `image_utils`, `video_recorder`,
  `record.launch.py`, `dev/`, `examples/`, `docs/`, the `.backup_*` folders,
  the RealSense D435 front camera and the mast camera in the URDF, the camera
  topics in `gz_bridge.yaml`, the marker helpers in `robot_commands.py`, and
  the OpenCV/cv_bridge/rosbag dependencies.
- Added: `launch/slam.launch.py`, `config/slam_toolbox_mapping.yaml`,
  `config/slam.rviz`.
- `rb1_diff_drive_controllers.yaml`: `tf_frame_prefix_enable: false`, so the
  controller publishes `odom -> base_link` instead of `robot/odom -> robot/base_link`.
- `robotnik_description/.../rb1_control.urdf.xacro` finds the controller YAML
  with `$(find indoor_delivery_project)` instead of an absolute path into
  `~/ros2_jazzy_ws`.
- `ros_gz_project_template` has a `COLCON_IGNORE` (unused here and it fails to
  configure without `GZ_VERSION` set).
