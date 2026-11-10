#!/usr/bin/env python3
"""Robot vision: the robot's camera with detections and navigation drawn on it.

    ros2 run indoor_delivery_project robot_vision

Run it next to aruco_slam_mapper (SLAM) or delivery_navigator / delivery_gui
(delivery). The window shows

  * the camera stream (/robot/aruco_camera/image_raw) with
      - ArUco markers: outline, ID, name, distance and bearing (solvePnP);
      - obstacles from the lidar, clustered and drawn as boxes in the image
        with their distance (red when inside the robot's path);
      - optional objects from a YOLO model (detector:=yolo, needs the
        `ultralytics` Python package; distance taken from the lidar);
      - the planned path drawn on the floor, the goal as a pin, and a HUD with
        pose, speed, goal distance and the navigator status;
  * the live map (/map) with the robot, its path, the route and the markers.

The drawing code (VisionOverlay) is also used inside delivery_gui.
"""
import math
import os
import sys
import threading
import time

import cv2
import numpy as np

try:
    from indoor_delivery_project.aruco_slam_mapper import (
        ArucoObserver, default_markers_file, load_marker_config, wrap, yaw_from_quaternion)
except ImportError:                         # run as a plain script
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from aruco_slam_mapper import (  # noqa: E402
        ArucoObserver, default_markers_file, load_marker_config, wrap, yaw_from_quaternion)


def image_to_bgr(msg):
    """sensor_msgs/Image -> BGR uint8."""
    enc = msg.encoding.lower()
    ch = {'mono8': 1, '8uc1': 1, 'rgb8': 3, 'bgr8': 3, '8uc3': 3,
          'rgba8': 4, 'bgra8': 4, '8uc4': 4}.get(enc)
    if ch is None:
        raise ValueError(f'unsupported image encoding {msg.encoding!r}')
    buf = np.frombuffer(bytes(msg.data), dtype=np.uint8)
    img = buf.reshape(msg.height, msg.step)[:, :msg.width * ch]
    img = np.ascontiguousarray(img.reshape(msg.height, msg.width, ch) if ch > 1 else img)
    if ch == 1:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    code = {'rgb8': cv2.COLOR_RGB2BGR, 'rgba8': cv2.COLOR_RGBA2BGR,
            'bgra8': cv2.COLOR_BGRA2BGR, '8uc4': cv2.COLOR_BGRA2BGR}.get(enc)
    return cv2.cvtColor(img, code) if code is not None else img


# ====================================================== optional YOLO objects
class ObjectDetector:
    """Runs a YOLO model (ultralytics) in its own thread on the newest frame."""

    def __init__(self, model='yolov8n.pt', rate=3.0, min_conf=0.4, log=print):
        from ultralytics import YOLO            # optional dependency
        self.model = YOLO(model)
        self.rate = rate
        self.min_conf = min_conf
        self.frame = None
        self.result = []                        # (x1, y1, x2, y2, label, conf)
        self.lock = threading.Lock()
        threading.Thread(target=self._loop, daemon=True).start()
        log(f'YOLO object detection on ({model})')

    def push(self, bgr):
        with self.lock:
            self.frame = bgr

    def _loop(self):
        while True:
            with self.lock:
                frame, self.frame = self.frame, None
            if frame is None:
                time.sleep(0.05)
                continue
            t0 = time.time()
            res = self.model(frame, verbose=False)[0]
            out = []
            for b in res.boxes:
                conf = float(b.conf[0])
                if conf < self.min_conf:
                    continue
                x1, y1, x2, y2 = (float(v) for v in b.xyxy[0])
                out.append((x1, y1, x2, y2, res.names[int(b.cls[0])], conf))
            with self.lock:
                self.result = out
            time.sleep(max(0.0, 1.0 / self.rate - (time.time() - t0)))

    def boxes(self):
        with self.lock:
            return list(self.result)


def make_detector(kind, model, log=print):
    if kind == 'none':
        return None
    try:
        return ObjectDetector(model, log=log)
    except Exception as exc:  # noqa: BLE001
        if kind == 'yolo':
            log(f'YOLO not available ({exc}); install with: pip install ultralytics')
        return None


# ===================================================== known walls filter
class StaticMap:
    """Distance to the nearest mapped wall, so map walls are not shown as obstacles."""

    def __init__(self, occupied, origin, res):
        self.origin, self.res = origin, res
        free = (~occupied).astype(np.uint8)
        self.dist = cv2.distanceTransform(free, cv2.DIST_L2, 3) * res

    @classmethod
    def from_grid(cls, grid):                   # OccupancyGrid2D
        return cls(grid.logodds > 0.6, grid.origin, grid.res)

    @classmethod
    def from_msg(cls, m):                       # nav_msgs/OccupancyGrid
        d = np.asarray(m.data, np.int16).reshape(m.info.height, m.info.width)
        return cls(d >= 65, (m.info.origin.position.x, m.info.origin.position.y),
                   m.info.resolution)

    def is_wall(self, world_xy, tol=0.3):
        c = np.floor((world_xy[:, 0] - self.origin[0]) / self.res).astype(int)
        r = np.floor((world_xy[:, 1] - self.origin[1]) / self.res).astype(int)
        h, w = self.dist.shape
        ok = (r >= 0) & (r < h) & (c >= 0) & (c < w)
        out = np.zeros(len(world_xy), bool)
        out[ok] = self.dist[r[ok], c[ok]] < tol
        return out


# ============================================================ the overlay
class VisionOverlay:
    """Draws detections and navigation on a camera image (pure OpenCV)."""

    def __init__(self, marker_info=None, dictionary='DICT_4X4_50',
                 camera_offset=(0.15, 0.0, 0.55), robot_half_width=0.35):
        self.info = marker_info or {}
        self.observer = ArucoObserver(dictionary, self.info, camera_offset=camera_offset)
        self.cam = camera_offset
        self.half_w = robot_half_width

    # base_link (x fwd, y left, z up) -> pixel
    def project(self, pts_base, K):
        p = np.atleast_2d(np.asarray(pts_base, float))
        xo = -(p[:, 1] - self.cam[1])
        yo = -(p[:, 2] - self.cam[2])
        zo = p[:, 0] - self.cam[0]
        ok = zo > 0.2
        uv = np.full((len(p), 2), np.nan)
        uv[ok, 0] = K[0, 0] * xo[ok] / zo[ok] + K[0, 2]
        uv[ok, 1] = K[1, 1] * yo[ok] / zo[ok] + K[1, 2]
        return uv, ok

    @staticmethod
    def world_to_base(pts, pose):
        c, s = math.cos(pose[2]), math.sin(pose[2])
        d = np.asarray(pts, float) - np.array(pose[:2])
        return np.stack([c * d[:, 0] + s * d[:, 1], -s * d[:, 0] + c * d[:, 1]], 1)

    def draw(self, bgr, K, D=None, scan_base=None, pose=None, path=None, goal=None,
             status='', speed=None, objects=None, scan_ranges_fn=None, static_map=None):
        img = bgr.copy()
        h, w = img.shape[:2]
        D = np.zeros(5) if D is None else D
        hfov = 2 * math.atan2(w / 2.0, K[0, 0])
        counts = {'markers': 0, 'obstacles': 0, 'objects': 0}

        # ---- navigation: path on the floor + goal pin
        if path is not None and pose is not None and len(path) > 1:
            pb = self.world_to_base(np.asarray(path, float), pose)
            ahead = pb[(pb[:, 0] > 0.3) & (np.hypot(pb[:, 0], pb[:, 1]) < 15.0)]
            if len(ahead) > 1:
                for side, col in ((0.0, (255, 160, 0)),):
                    pts3 = np.c_[ahead[:, 0], ahead[:, 1] + side, np.zeros(len(ahead))]
                    uv, ok = self.project(pts3, K)
                    uv = uv[ok]
                    if len(uv) > 1:
                        cv2.polylines(img, [uv.astype(np.int32)], False, col, 4, cv2.LINE_AA)
                # robot-width corridor edges, faint
                for side in (-self.half_w, self.half_w):
                    pts3 = np.c_[ahead[:, 0], ahead[:, 1] + side, np.zeros(len(ahead))]
                    uv, ok = self.project(pts3, K)
                    uv = uv[ok]
                    if len(uv) > 1:
                        cv2.polylines(img, [uv.astype(np.int32)], False, (255, 220, 150), 1,
                                      cv2.LINE_AA)
        if goal is not None and pose is not None:
            gb = self.world_to_base(np.array([goal[:2]], float), pose)[0]
            dist = math.hypot(*gb)
            uv, ok = self.project([[gb[0], gb[1], 0.0], [gb[0], gb[1], 1.2]], K)
            if ok.all() and 0 <= uv[1, 0] < w:
                a, b = tuple(uv[0].astype(int)), tuple(uv[1].astype(int))
                cv2.line(img, a, b, (0, 200, 255), 3)
                cv2.circle(img, b, 8, (0, 200, 255), -1)
                cv2.putText(img, f'goal {dist:.1f} m', (b[0] + 10, b[1]),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 2)
            else:                                         # off screen: arrow at the edge
                ang = math.atan2(gb[1], gb[0])
                x = 30 if ang > 0 else w - 30
                cv2.arrowedLine(img, (w // 2, h - 40), (x, h - 40), (0, 200, 255), 3,
                                tipLength=0.08)
                cv2.putText(img, f'goal {dist:.1f} m', (w // 2 - 50, h - 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 2)

        # ---- lidar obstacles (clusters inside the camera view)
        if scan_base is not None and len(scan_base):
            sb = np.asarray(scan_base, float)
            rel = sb - np.array(self.cam[:2])
            rng = np.hypot(rel[:, 0], rel[:, 1])
            bear = np.arctan2(rel[:, 1], rel[:, 0])
            sel = (rel[:, 0] > 0.2) & (np.abs(bear) < hfov / 2 - 0.02) & (rng < 6.0)
            pts = sb[sel]
            if len(pts):
                order = np.argsort(np.arctan2(pts[:, 1], pts[:, 0]))
                pts = pts[order]
                gaps = np.hypot(*np.diff(pts, axis=0).T) > 0.3
                clusters = np.split(pts, np.nonzero(gaps)[0] + 1)
                for cl in clusters:
                    if len(cl) < 3:
                        continue
                    if static_map is not None and pose is not None:
                        c_, s_ = math.cos(pose[2]), math.sin(pose[2])
                        wx = pose[0] + c_ * cl[:, 0] - s_ * cl[:, 1]
                        wy = pose[1] + s_ * cl[:, 0] + c_ * cl[:, 1]
                        if static_map.is_wall(np.stack([wx, wy], 1)).mean() > 0.6:
                            continue                # a wall that is on the map
                    elif max(np.ptp(cl, axis=0)) > 3.0:
                        continue                    # no map: long straight = wall
                    near = cl[np.argmin(np.hypot(cl[:, 0], cl[:, 1]))]
                    dist = float(np.hypot(*near))
                    in_path = bool(((np.abs(cl[:, 1]) < self.half_w + 0.1) &
                                    (cl[:, 0] < 2.5)).any())
                    top = np.c_[cl[:, 0], cl[:, 1], np.full(len(cl), 0.9)]
                    bot = np.c_[cl[:, 0], cl[:, 1], np.zeros(len(cl))]
                    uv, ok = self.project(np.vstack([top, bot]), K)
                    uv = uv[ok]
                    if len(uv) < 2:
                        continue
                    x1, y1 = np.clip(uv.min(axis=0), 0, [w - 1, h - 1]).astype(int)
                    x2, y2 = np.clip(uv.max(axis=0), 0, [w - 1, h - 1]).astype(int)
                    col = (0, 0, 255) if in_path else (0, 165, 255)
                    cv2.rectangle(img, (x1, y1), (x2, y2), col, 2)
                    cv2.putText(img, f'obstacle {dist:.1f} m', (x1, max(y1 - 6, 12)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 2)
                    counts['obstacles'] += 1

        # ---- ArUco markers
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self.observer._detect(gray)
        if ids is not None:
            for c, mid in zip(corners, ids.ravel().tolist()):
                pts = np.asarray(c, np.float64).reshape(4, 2)
                known = mid in self.info
                col = (0, 220, 0) if known else (160, 160, 160)
                cv2.polylines(img, [pts.astype(np.int32)], True, col, 2, cv2.LINE_AA)
                cv2.circle(img, tuple(pts[0].astype(int)), 4, (0, 0, 255), -1)
                o = self.observer.from_corners(int(mid), pts, K, D)
                name = self.info.get(mid, {}).get('name', 'unknown')
                txt = f'ID {mid} {name}'
                txt2 = (f'{o.distance_3d:.2f} m  {math.degrees(o.bearing):+.0f} deg'
                        if o is not None else '')
                x, y = pts[:, 0].min(), pts[:, 1].min()
                cv2.putText(img, txt, (int(x), int(max(y - 22, 14))),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 2)
                if txt2:
                    cv2.putText(img, txt2, (int(x), int(max(y - 6, 28))),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 2)
                counts['markers'] += 1

        # ---- YOLO objects (distance from the lidar along the box centre)
        for (x1, y1, x2, y2, label, conf) in objects or []:
            cx = 0.5 * (x1 + x2)
            bearing = math.atan2(K[0, 2] - cx, K[0, 0])
            dist = scan_ranges_fn(bearing) if scan_ranges_fn else None
            cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 255), 2)
            t = f'{label} {conf:.2f}' + (f'  {dist:.1f} m' if dist else '')
            cv2.putText(img, t, (int(x1), int(max(y1 - 6, 12))), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (255, 0, 255), 2)
            counts['objects'] += 1

        # ---- HUD
        bar = np.zeros((44, w, 3), np.uint8)
        line1 = (f'pose ({pose[0]:.2f}, {pose[1]:.2f}, {math.degrees(pose[2]):.0f} deg)'
                 if pose is not None else 'pose: -')
        if speed is not None:
            line1 += f'   v {speed[0]:.2f} m/s  w {speed[1]:.2f} rad/s'
        line1 += (f'   markers {counts["markers"]}  obstacles {counts["obstacles"]}'
                  + (f'  objects {counts["objects"]}' if objects is not None else ''))
        cv2.putText(bar, line1, (8, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)
        cv2.putText(bar, (status or '')[:110], (8, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.48,
                    (120, 230, 255), 1)
        return np.vstack([bar, img]), counts


def bgr_to_qimage(bgr):
    from PyQt5.QtGui import QImage
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()


# ======================================================= standalone window
def main(args=None):
    import rclpy
    from rclpy.node import Node
    from rclpy.parameter import Parameter
    from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
    from rclpy.time import Time
    from nav_msgs.msg import OccupancyGrid, Odometry, Path
    from sensor_msgs.msg import CameraInfo, Image, LaserScan
    from std_msgs.msg import String
    from PyQt5.QtCore import QPointF, Qt, QTimer
    from PyQt5.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap, QPolygonF
    from PyQt5.QtWidgets import (QApplication, QLabel, QMainWindow, QSplitter,
                                 QVBoxLayout, QWidget)
    try:
        import tf2_ros
    except ImportError:
        tf2_ros = None

    rclpy.init(args=args if args is not None else sys.argv)

    class VisionNode(Node):
        def __init__(self):
            super().__init__('robot_vision')
            p = self.declare_parameter
            p('image_topic', '/robot/aruco_camera/image_raw')
            p('camera_info_topic', '/robot/aruco_camera/camera_info')
            p('scan_topic', '/robot/front_laser/scan')
            p('odom_topic', '/robot/diff_drive_controller/odom')
            p('markers_file', default_markers_file())
            p('camera_offset', [0.15, 0.0, 0.55])
            p('map_frame', 'map')
            p('base_frame', 'base_link')
            p('detector', 'auto')                 # auto | yolo | none
            p('yolo_model', 'yolov8n.pt')
            self.set_parameters([Parameter('use_sim_time', Parameter.Type.BOOL, True)])
            g = lambda n: self.get_parameter(n).value  # noqa: E731
            dict_name, info = load_marker_config(g('markers_file'))
            self.info = info
            self.overlay = VisionOverlay(info, dict_name, tuple(g('camera_offset')))
            self.lock = threading.Lock()
            self.img = None
            self.K = None
            self.D = None
            self.scan = None
            self.scan_base = None
            self.speed = None
            self.odom_pose = None
            self.paths = {}
            self.status = ''
            self.map_msg = None
            self.map_ver = 0
            self.static_map = None
            self.tf_buf = None
            if tf2_ros is not None:
                self.tf_buf = tf2_ros.Buffer()
                self.tf_listener = tf2_ros.TransformListener(self.tf_buf, self)
            sd = qos_profile_sensor_data
            self.create_subscription(Image, g('image_topic'), self._img, sd)
            self.create_subscription(CameraInfo, g('camera_info_topic'), self._info, sd)
            self.create_subscription(LaserScan, g('scan_topic'), self._scan, sd)
            self.create_subscription(Odometry, g('odom_topic'), self._odom, sd)
            latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
            self.create_subscription(OccupancyGrid, '/map', self._map, latched)
            for t in ('/aruco_slam_mapper/plan', '/delivery_navigator/plan',
                      '/delivery_navigator/route'):
                self.create_subscription(Path, t, lambda m, t=t: self._path(t, m), 1)
            self.create_subscription(String, '/delivery_navigator/status',
                                     lambda m: setattr(self, 'status', m.data.split('\n')[0]),
                                     10)
            self.detector = make_detector(g('detector'), g('yolo_model'),
                                          log=self.get_logger().info)

        def _img(self, m):
            try:
                bgr = image_to_bgr(m)
            except ValueError as exc:
                self.get_logger().warning(str(exc), throttle_duration_sec=5.0)
                return
            with self.lock:
                self.img = bgr
            if self.detector:
                self.detector.push(bgr)

        def _info(self, m):
            K = np.array(m.k, float).reshape(3, 3)
            if K[0, 0] > 0:
                self.K, self.D = K, (np.array(m.d, float) if len(m.d) else np.zeros(5))

        def _odom(self, m):
            self.speed = (m.twist.twist.linear.x, m.twist.twist.angular.z)
            p = m.pose.pose
            self.odom_pose = (p.position.x, p.position.y, yaw_from_quaternion(p.orientation))

        def _scan(self, m):
            T = self._laser_tf(m.header.frame_id)
            r = np.asarray(m.ranges, np.float32)
            a = m.angle_min + np.arange(len(r)) * m.angle_increment
            ok = np.isfinite(r) & (r > m.range_min) & (r < m.range_max)
            pts = np.stack([r[ok] * np.cos(a[ok]), r[ok] * np.sin(a[ok]), np.zeros(ok.sum())], 1)
            if T is not None:
                R, t = T
                pts = pts @ R.T + t
            base = pts[:, :2]
            base = base[np.hypot(base[:, 0], base[:, 1]) > 0.32]
            with self.lock:
                self.scan_base = base

        def _laser_tf(self, frame):
            if self.tf_buf is None:
                return None
            try:
                tf = self.tf_buf.lookup_transform(self.get_parameter('base_frame').value,
                                                  frame, Time())
            except Exception:  # noqa: BLE001
                return None
            q = tf.transform.rotation
            x, y, z, w = q.x, q.y, q.z, q.w
            R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                          [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                          [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
            tr = tf.transform.translation
            return R, np.array([tr.x, tr.y, tr.z])

        def _map(self, m):
            sm = StaticMap.from_msg(m)
            with self.lock:
                self.map_msg = m
                self.map_ver += 1
                self.static_map = sm

        def _path(self, topic, m):
            pts = [(ps.pose.position.x, ps.pose.position.y) for ps in m.poses]
            with self.lock:
                self.paths[topic] = pts

        def pose(self):
            if self.tf_buf is not None:
                try:
                    tf = self.tf_buf.lookup_transform(self.get_parameter('map_frame').value,
                                                      self.get_parameter('base_frame').value,
                                                      Time())
                    t = tf.transform
                    return (t.translation.x, t.translation.y, yaw_from_quaternion(t.rotation))
                except Exception:  # noqa: BLE001
                    pass
            return self.odom_pose

        def ray(self, bearing):
            with self.lock:
                sb = self.scan_base
            if sb is None or not len(sb):
                return None
            b = np.arctan2(sb[:, 1], sb[:, 0])
            k = np.abs(np.array([wrap(v - bearing) for v in b])) < 0.03
            return float(np.hypot(sb[k, 0], sb[k, 1]).min()) if k.any() else None

    node = VisionNode()
    from rclpy.executors import MultiThreadedExecutor
    ex = MultiThreadedExecutor(num_threads=3)
    ex.add_node(node)
    threading.Thread(target=ex.spin, daemon=True).start()

    app = QApplication([sys.argv[0]])

    class MiniMap(QWidget):
        def __init__(self):
            super().__init__()
            self.setMinimumSize(320, 240)
            self.pix = None
            self.ver = -1
            self.meta = None

        def paintEvent(self, _e):
            qp = QPainter(self)
            qp.fillRect(self.rect(), QColor(205, 205, 205))
            with node.lock:
                m, ver = node.map_msg, node.map_ver
                paths = dict(node.paths)
            if m is None:
                qp.drawText(self.rect(), Qt.AlignCenter, 'waiting for /map ...')
                return
            if ver != self.ver:
                h, w = m.info.height, m.info.width
                d = np.asarray(m.data, np.int16).reshape(h, w)
                img = np.full((h, w), 205, np.uint8)
                img[d == 0] = 255
                img[d >= 65] = 20
                img = np.ascontiguousarray(np.flipud(img))
                self._buf = img
                self.pix = QPixmap.fromImage(QImage(img.data, w, h, w, QImage.Format_Grayscale8))
                self.meta = (m.info.origin.position.x, m.info.origin.position.y,
                             m.info.resolution, w, h)
                self.ver = ver
            ox, oy, res, w, h = self.meta
            s = min(self.width() / w, self.height() / h)
            x0 = (self.width() - w * s) / 2
            y0 = (self.height() - h * s) / 2
            qp.drawPixmap(int(x0), int(y0), int(w * s), int(h * s), self.pix)

            def px(x, y):
                return QPointF(x0 + (x - ox) / res * s, y0 + (h - (y - oy) / res) * s)
            for t, col in (('/delivery_navigator/route', QColor(120, 120, 255)),
                           ('/aruco_slam_mapper/plan', QColor(0, 110, 255)),
                           ('/delivery_navigator/plan', QColor(0, 110, 255))):
                pts = paths.get(t)
                if pts and len(pts) > 1:
                    qp.setPen(QPen(col, 2))
                    qp.drawPolyline(QPolygonF([px(*p) for p in pts]))
            pose = node.pose()
            if pose is not None:
                c = px(pose[0], pose[1])
                r = 8
                th = pose[2]
                tri = QPolygonF([QPointF(c.x() + r * math.cos(-th), c.y() + r * math.sin(-th)),
                                 QPointF(c.x() + r * .7 * math.cos(-th + 2.4),
                                         c.y() + r * .7 * math.sin(-th + 2.4)),
                                 QPointF(c.x() + r * .7 * math.cos(-th - 2.4),
                                         c.y() + r * .7 * math.sin(-th - 2.4))])
                qp.setPen(QPen(Qt.black, 1))
                qp.setBrush(QBrush(QColor(0, 200, 0)))
                qp.drawPolygon(tri)

    win = QMainWindow()
    win.setWindowTitle('Robot vision: camera, detections and navigation')
    cam = QLabel('waiting for the camera ...')
    cam.setAlignment(Qt.AlignCenter)
    cam.setMinimumSize(640, 480)
    mini = MiniMap()
    side = QWidget()
    sl = QVBoxLayout(side)
    sl.addWidget(QLabel('Map (SLAM / delivery)'))
    sl.addWidget(mini, 1)
    legend = QLabel('<b>Camera:</b> green = ArUco marker (ID, name, distance), '
                    'orange/red box = lidar obstacle (red: in the path), '
                    'magenta = YOLO object, blue line = planned path, yellow pin = goal')
    legend.setWordWrap(True)
    sl.addWidget(legend)
    split = QSplitter()
    split.addWidget(cam)
    split.addWidget(side)
    split.setStretchFactor(0, 3)
    split.setStretchFactor(1, 2)
    win.setCentralWidget(split)
    win.resize(1300, 700)
    win.show()

    def tick():
        with node.lock:
            img = node.img
            sb = node.scan_base
            paths = dict(node.paths)
        if img is not None and node.K is not None:
            path = paths.get('/delivery_navigator/plan') or paths.get('/aruco_slam_mapper/plan')
            pose = node.pose()
            goal = path[-1] if path else None
            out, _ = node.overlay.draw(img, node.K, node.D, sb, pose, path, goal,
                                       node.status, node.speed,
                                       node.detector.boxes() if node.detector else None,
                                       node.ray, node.static_map)
            q = bgr_to_qimage(out)
            cam.setPixmap(QPixmap.fromImage(q).scaled(cam.width(), cam.height(),
                                                      Qt.KeepAspectRatio,
                                                      Qt.SmoothTransformation))
        mini.update()

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(66)
    import signal
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    try:
        app.exec_()
    finally:
        ex.shutdown(timeout_sec=1.0)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
