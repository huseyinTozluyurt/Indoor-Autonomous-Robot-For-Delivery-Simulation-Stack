# ArUco markers and mast camera

## Markers (DICT_4X4_50)
| ID | Where | Size (black square) |
|----|-------|------|
| 1-4 | Left room delivery points 1-4 (west wall behind each pad, 0.6 m high) | 0.30 m |
| 5-8 | Right room delivery points 1-4 (east wall behind each pad) | 0.30 m |
| 10 | Left room, far (west) wall centre, 1.5 m high: seen when entering from the bridge | 1.00 m |
| 11 | Left room, inside the doorway wall (y=-4): seen when heading back to the bridge | 0.60 m |
| 20 | Right room, far (east) wall centre | 1.00 m |
| 21 | Right room, inside the doorway wall (y=-4) | 0.60 m |

Poses are in `config/aruco_markers.yaml`. To change or add markers, edit `MARKERS`
in `scripts/generate_aruco_models.py`, run `python3 scripts/generate_aruco_models.py`
from the package root, and paste `scripts/aruco_world_includes.sdf.snippet` over the
ARUCO MARKERS block at the end of `worlds/campus_area.sdf`.
Printable PNGs for the real robot: `models/aruco_marker_<id>/meshes/aruco_<id>.png`.

## Camera
`aruco_camera`: RGB 640x480 @ 15 Hz, HFOV 1.2 rad (69 deg), on a mast above the
cargo box (base_link + x 0.15, z 0.55). Frame `aruco_camera_optical_frame`.
- `/robot/aruco_camera/image_raw`, `/robot/aruco_camera/camera_info`
- `/aruco_detector/annotated` (image with markers drawn), `/aruco_detector/detections`
  (JSON), `/aruco_detector/poses` (PoseArray, camera frame), `/robot/current_room`

## Run
```
colcon build --symlink-install --packages-select indoor_delivery_robot_description indoor_delivery_project
source install/setup.bash
ros2 launch indoor_delivery_project sim.launch.py              # aruco:=false to skip detector
ros2 run rqt_image_view rqt_image_view /aruco_detector/annotated
ros2 launch indoor_delivery_project record.launch.py           # bag + mp4 in ~/robot_recordings
ros2 launch indoor_delivery_project sim.launch.py record:=true # record from the start
ros2 service call /video_recorder/set_recording std_srvs/srv/SetBool "{data: false}"
```
If a marker shows up mirrored in Gazebo (detector never sees it), swap the U
coordinates in the DAE template (`0 0  1 0  1 1  0 1` -> `1 0  0 0  0 1  1 1`) and regenerate.
