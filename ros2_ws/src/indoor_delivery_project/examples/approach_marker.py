#!/usr/bin/env python3
"""Find an ArUco marker, turn towards it and drive up to it.

Does its own detection on the mast camera with aruco_utils (so you see every
step), and moves with the built-in Robot commands.

    ros2 launch indoor_delivery_project sim.launch.py        # terminal 1
    python3 src/indoor_delivery_project/examples/approach_marker.py 10 --stop 1.5

Marker 10 is the big one on the far wall of the left room. Delivery points are
1-8 (see config/aruco_markers.yaml / docs/aruco_and_camera.md).
"""
import argparse
import math
import os

import yaml
from ament_index_python.packages import get_package_share_directory
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image

from indoor_delivery_project import aruco_utils
from indoor_delivery_project.image_utils import image_to_bgr
from indoor_delivery_project.robot_commands import Robot


def marker_sizes():
    path = os.path.join(get_package_share_directory('indoor_delivery_project'),
                        'config', 'aruco_markers.yaml')
    with open(path) as f:
        return {m['id']: float(m['size']) for m in yaml.safe_load(f)['markers']}


class MarkerEye:
    """Keeps the latest camera frame; measure(id) -> (distance_m, bearing_deg) or None."""

    def __init__(self, robot, sizes):
        self.robot, self.sizes = robot, sizes
        self.detector = aruco_utils.MarkerDetector('DICT_4X4_50')
        self.frame = None
        self.K = self.D = None
        # Robot.node is a normal rclpy node: add your own subscriptions to it.
        # Their callbacks run whenever a Robot command (or robot.sleep) is running.
        robot.node.create_subscription(Image, '/robot/aruco_camera/image_raw',
                                       self._image, qos_profile_sensor_data)
        robot.node.create_subscription(CameraInfo, '/robot/aruco_camera/camera_info',
                                       self._info, qos_profile_sensor_data)

    def _image(self, msg):
        self.frame = msg

    def _info(self, msg):
        self.K, self.D = aruco_utils.camera_info_to_kd(msg)

    def measure(self, marker_id):
        self.robot.sleep(0.3)            # let a fresh frame arrive
        if self.frame is None or self.K is None:
            return None
        corners, ids, _ = self.detector.detect(image_to_bgr(self.frame))
        if ids is None:
            return None
        for c, mid in zip(corners, ids.ravel()):
            if mid != marker_id:
                continue
            pose = aruco_utils.estimate_pose(c, self.sizes.get(mid, 0.3), self.K, self.D)
            if pose is None:
                return None
            x, _, z = pose[1].ravel()          # optical frame: x right, z forward
            return math.hypot(x, z), -math.degrees(math.atan2(x, z))
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('marker_id', type=int)
    ap.add_argument('--stop', type=float, default=1.0, help='stop this far away (m)')
    args = ap.parse_args()

    with Robot() as robot:
        eye = MarkerEye(robot, marker_sizes())

        # 1) Look around: turn left in 20 degree steps until the marker is seen
        seen = None
        for _ in range(18):
            seen = eye.measure(args.marker_id)
            if seen:
                break
            robot.turn_left(20)
        if not seen:
            print(f'marker {args.marker_id} not found from here')
            return

        # 2) Approach in steps: face it, drive part of the way, measure again
        for _ in range(20):
            seen = eye.measure(args.marker_id)
            if not seen:
                print('lost the marker, stopping')
                return
            distance, bearing = seen
            print(f'marker {args.marker_id}: {distance:.2f} m, bearing {bearing:+.1f} deg')
            if distance <= args.stop + 0.05:
                print('arrived')
                return
            if abs(bearing) > 3:
                robot.turn(bearing)
            robot.forward(min(2.0, 0.6 * (distance - args.stop)))


if __name__ == '__main__':
    main()
