"""Small ArUco helpers that work with OpenCV 4.6 (Ubuntu 24.04 apt) and >= 4.7.

Pure OpenCV/numpy; ROS is only imported by grab_ros_frame(). Handy for
experiments in dev/ and for new nodes:

    import cv2
    from indoor_delivery_project.aruco_utils import MarkerDetector
    det = MarkerDetector('DICT_4X4_50')
    corners, ids, rejected = det.detect(cv2.imread('frame.png'))
"""
import cv2
import numpy as np


def has_aruco():
    return hasattr(cv2, 'aruco')


def get_dictionary(name='DICT_4X4_50'):
    dict_id = getattr(cv2.aruco, name)
    if hasattr(cv2.aruco, 'getPredefinedDictionary'):
        return cv2.aruco.getPredefinedDictionary(dict_id)
    return cv2.aruco.Dictionary_get(dict_id)


def make_parameters(**overrides):
    """DetectorParameters with optional overrides, e.g. adaptiveThreshWinSizeMax=35."""
    if hasattr(cv2.aruco, 'DetectorParameters_create'):     # OpenCV <= 4.6
        params = cv2.aruco.DetectorParameters_create()
    else:
        params = cv2.aruco.DetectorParameters()
    for key, value in overrides.items():
        if not hasattr(params, key):
            raise AttributeError(f'DetectorParameters has no field {key!r}')
        setattr(params, key, value)
    return params


class MarkerDetector:
    """detect(img) -> (corners, ids, rejected) on any OpenCV 4.x/5.x."""

    def __init__(self, dictionary='DICT_4X4_50', **param_overrides):
        self.dictionary = get_dictionary(dictionary)
        self.params = make_parameters(**param_overrides)
        if hasattr(cv2.aruco, 'ArucoDetector'):
            self._detector = cv2.aruco.ArucoDetector(self.dictionary, self.params)
        else:
            self._detector = None

    def detect(self, img):
        gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if self._detector is not None:
            return self._detector.detectMarkers(gray)
        return cv2.aruco.detectMarkers(gray, self.dictionary, parameters=self.params)


def estimate_pose(corner, marker_size, K, D):
    """rvec, tvec of one marker (corner: 1x4x2) in the camera optical frame, or None."""
    h = marker_size / 2.0
    obj = np.array([[-h, h, 0], [h, h, 0], [h, -h, 0], [-h, -h, 0]], dtype=np.float64)
    ok, rvec, tvec = cv2.solvePnP(obj, np.asarray(corner, np.float64).reshape(4, 2),
                                  K, D, flags=cv2.SOLVEPNP_IPPE_SQUARE)
    return (rvec, tvec) if ok else None


def draw(img, corners, ids, K=None, D=None, marker_size=None, rejected=None):
    """Draw markers (and axes + distance when K, D, marker_size are given). In place."""
    if rejected is not None and len(rejected):
        cv2.aruco.drawDetectedMarkers(img, rejected, borderColor=(100, 0, 255))
    if ids is None or len(ids) == 0:
        return img
    cv2.aruco.drawDetectedMarkers(img, corners, ids)
    if K is not None and marker_size:
        for c in corners:
            pose = estimate_pose(c, marker_size, K, D)
            if pose is None:
                continue
            rvec, tvec = pose
            cv2.drawFrameAxes(img, K, D, rvec, tvec, marker_size * 0.5)
            x, y = np.asarray(c).reshape(4, 2)[2].astype(int)
            cv2.putText(img, f'{np.linalg.norm(tvec):.2f} m', (int(x), int(y) + 18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
    return img


def generate_marker(marker_id, pixels=400, dictionary='DICT_4X4_50', border_bits=1):
    """Marker image (uint8) with a white quiet zone, for printing or tests."""
    d = get_dictionary(dictionary)
    if hasattr(cv2.aruco, 'generateImageMarker'):
        img = cv2.aruco.generateImageMarker(d, marker_id, pixels, borderBits=border_bits)
    else:
        img = cv2.aruco.drawMarker(d, marker_id, pixels, borderBits=border_bits)
    pad = pixels // 8
    return cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255)


def camera_info_to_kd(msg):
    """K (3x3) and D arrays from a sensor_msgs/CameraInfo."""
    K = np.array(msg.k, dtype=np.float64).reshape(3, 3)
    D = np.array(msg.d, dtype=np.float64) if len(msg.d) else np.zeros(5)
    return K, D


def grab_ros_frame(topic='/robot/aruco_camera/image_raw',
                   info_topic='/robot/aruco_camera/camera_info', timeout=5.0):
    """Grab one BGR frame (and K, D) from a ROS image topic. For notebooks/scratch.

    Returns (img, K, D); K and D are None if no camera_info arrived.
    """
    import time

    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import CameraInfo, Image

    from indoor_delivery_project.image_utils import image_to_bgr

    owns = not rclpy.ok()
    if owns:
        rclpy.init()
    node = rclpy.create_node('aruco_frame_grabber')
    got = {}
    node.create_subscription(Image, topic, lambda m: got.setdefault('img', m),
                             qos_profile_sensor_data)
    node.create_subscription(CameraInfo, info_topic, lambda m: got.setdefault('info', m),
                             qos_profile_sensor_data)
    try:
        end = time.monotonic() + timeout
        while 'img' not in got or 'info' not in got:
            if time.monotonic() > end:
                break
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        node.destroy_node()
        if owns:
            rclpy.shutdown()
    if 'img' not in got:
        raise TimeoutError(f'no image on {topic} within {timeout} s')
    K, D = camera_info_to_kd(got['info']) if 'info' in got else (None, None)
    return image_to_bgr(got['img']), K, D
