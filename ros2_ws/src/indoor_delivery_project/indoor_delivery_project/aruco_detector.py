"""ArUco marker detector for the indoor delivery robot camera.

Subscribes to the mast camera, detects markers from config/aruco_markers.yaml
and publishes:
  ~/annotated      sensor_msgs/Image   camera image with markers, ids, distance
  ~/poses          geometry_msgs/PoseArray  marker poses in the camera optical frame
  ~/detections     std_msgs/String     JSON list: id, name, kind, room, distance_m
  /robot/current_room  std_msgs/String  last room identified by a room marker

Works with OpenCV 4.6 (Ubuntu 24.04 python3-opencv) and the >= 4.7 API.
"""
import json
import math
import os

import cv2
import numpy as np
import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import Pose, PoseArray
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String

from indoor_delivery_project.image_utils import bgr_to_image, image_to_bgr


def rvec_to_quaternion(rvec):
    rot, _ = cv2.Rodrigues(rvec)
    tr = rot[0, 0] + rot[1, 1] + rot[2, 2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        return ((rot[2, 1] - rot[1, 2]) / s, (rot[0, 2] - rot[2, 0]) / s,
                (rot[1, 0] - rot[0, 1]) / s, 0.25 * s)
    i = int(np.argmax([rot[0, 0], rot[1, 1], rot[2, 2]]))
    j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1.0 + rot[i, i] - rot[j, j] - rot[k, k]) * 2
    q = [0.0, 0.0, 0.0]
    q[i] = 0.25 * s
    q[j] = (rot[j, i] + rot[i, j]) / s
    q[k] = (rot[k, i] + rot[i, k]) / s
    w = (rot[k, j] - rot[j, k]) / s
    return q[0], q[1], q[2], w


class ArucoDetector(Node):
    def __init__(self):
        super().__init__('aruco_detector')
        default_markers = os.path.join(
            get_package_share_directory('indoor_delivery_project'),
            'config', 'aruco_markers.yaml')
        self.declare_parameter('image_topic', '/robot/aruco_camera/image_raw')
        self.declare_parameter('camera_info_topic', '/robot/aruco_camera/camera_info')
        self.declare_parameter('markers_file', default_markers)
        self.declare_parameter('default_marker_size', 0.30)
        self.declare_parameter('publish_annotated', True)

        with open(self.get_parameter('markers_file').value) as f:
            cfg = yaml.safe_load(f)
        self.markers = {m['id']: m for m in cfg.get('markers', [])}
        dict_name = cfg.get('dictionary', 'DICT_4X4_50')
        dict_id = getattr(cv2.aruco, dict_name)
        if hasattr(cv2.aruco, 'ArucoDetector'):            # OpenCV >= 4.7
            dictionary = cv2.aruco.getPredefinedDictionary(dict_id)
            self._detector = cv2.aruco.ArucoDetector(
                dictionary, cv2.aruco.DetectorParameters())
            self._detect = self._detector.detectMarkers
        else:                                               # OpenCV 4.6
            dictionary = cv2.aruco.Dictionary_get(dict_id)
            params = cv2.aruco.DetectorParameters_create()
            self._detect = lambda img: cv2.aruco.detectMarkers(
                img, dictionary, parameters=params)

        self.K = None
        self.D = None
        self.current_room = None
        self.default_size = float(self.get_parameter('default_marker_size').value)
        self.publish_annotated = bool(self.get_parameter('publish_annotated').value)

        self.create_subscription(
            CameraInfo, self.get_parameter('camera_info_topic').value,
            self._info_cb, qos_profile_sensor_data)
        self.create_subscription(
            Image, self.get_parameter('image_topic').value,
            self._image_cb, qos_profile_sensor_data)
        self.annotated_pub = self.create_publisher(Image, '~/annotated', 5)
        self.poses_pub = self.create_publisher(PoseArray, '~/poses', 10)
        self.det_pub = self.create_publisher(String, '~/detections', 10)
        self.room_pub = self.create_publisher(String, '/robot/current_room', 10)
        self.get_logger().info(
            f'ArUco {dict_name}: {len(self.markers)} known markers, image '
            f'{self.get_parameter("image_topic").value}')

    def _info_cb(self, msg: CameraInfo):
        self.K = np.array(msg.k, dtype=np.float64).reshape(3, 3)
        self.D = np.array(msg.d, dtype=np.float64) if len(msg.d) else np.zeros(5)

    def _image_cb(self, msg: Image):
        try:
            img = image_to_bgr(msg)
        except ValueError as exc:
            self.get_logger().warn(str(exc), throttle_duration_sec=5.0)
            return
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self._detect(gray)

        poses = PoseArray()
        poses.header = msg.header
        detections = []
        if ids is not None:
            cv2.aruco.drawDetectedMarkers(img, corners, ids)
            for c, mid in zip(corners, ids.ravel().tolist()):
                info = self.markers.get(mid, {})
                det = {'id': mid, 'name': info.get('name', 'unknown'),
                       'kind': info.get('kind', 'unknown'),
                       'room': info.get('room')}
                if self.K is not None:
                    size = float(info.get('size', self.default_size))
                    h = size / 2.0
                    obj = np.array([[-h, h, 0], [h, h, 0], [h, -h, 0], [-h, -h, 0]],
                                   dtype=np.float64)
                    ok, rvec, tvec = cv2.solvePnP(
                        obj, c.reshape(4, 2).astype(np.float64), self.K, self.D,
                        flags=cv2.SOLVEPNP_IPPE_SQUARE)
                    if ok:
                        t = tvec.ravel()
                        det['distance_m'] = round(float(np.linalg.norm(t)), 3)
                        p = Pose()
                        p.position.x, p.position.y, p.position.z = map(float, t)
                        (p.orientation.x, p.orientation.y,
                         p.orientation.z, p.orientation.w) = rvec_to_quaternion(rvec)
                        poses.poses.append(p)
                        cv2.drawFrameAxes(img, self.K, self.D, rvec, tvec, size * 0.5)
                label = f"{mid} {det['name']}"
                if 'distance_m' in det:
                    label += f" {det['distance_m']:.1f}m"
                x, y = c.reshape(4, 2)[0].astype(int)
                cv2.putText(img, label, (int(x), max(15, int(y) - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                detections.append(det)
                if det['kind'] == 'room' and det['room'] != self.current_room:
                    self.current_room = det['room']
                    self.get_logger().info(f'Entered/identified room: {self.current_room}')
                    self.room_pub.publish(String(data=self.current_room))

        self.poses_pub.publish(poses)
        self.det_pub.publish(String(data=json.dumps(detections)))
        if self.publish_annotated:
            self.annotated_pub.publish(bgr_to_image(img, msg.header))


def main(args=None):
    rclpy.init(args=args)
    node = ArucoDetector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
