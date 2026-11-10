#!/usr/bin/env python3
"""ArUco visual SLAM mapper for the indoor delivery robot (one file).

The robot drives itself through the whole operational area, records every
ArUco detection (distance, bearing, marker orientation) together with the
odometry, and builds two maps that are saved to `output_dir`:

  * a landmark map: an EKF-SLAM estimate of every marker's position and facing
    direction, plus named delivery points in front of the delivery markers
    (aruco_landmarks.yaml);
  * an occupancy grid from the front lidar, drawn with the SLAM-corrected
    pose (map.pgm + map.yaml, the Nav2 map_server format).

How the pieces fit:
  odometry (diff drive)  -> EKF prediction (robot pose)
  ArUco (mast camera)    -> EKF update (range + bearing to each marker; the
                            marker ID makes data association trivial). Markers
                            seen for the first time are added to the state.
  lidar                  -> occupancy grid at the EKF pose; it also records
                            which wall stretches the camera has looked at from
                            close range ("visual coverage").
  explorer               -> drives to the nearest frontier (free space next to
                            unknown space) or to a viewpoint ~3 m in front of a
                            wall stretch the camera has not seen yet, until the
                            whole area and every wall has been covered. Then it
                            returns to the start and saves.

Run (simulation running: ros2 launch indoor_delivery_project sim.launch.py):

    ros2 run indoor_delivery_project aruco_slam_mapper --ros-args \
        -p initial_pose:="[-25.0, 0.0, 0.0]" \
        -p output_dir:=~/ros2_jazzy_ws/maps/campus

  initial_pose is where the robot starts in the map frame. Giving the Gazebo
  spawn pose (-25, 0, 0) makes map coordinates equal world coordinates, so the
  mapper can print the error of every marker against config/aruco_markers.yaml.
  With the default [0, 0, 0] the map frame is simply the start pose.

  -p explore:=false   map while you drive (pyqt_teleop / teleop_twist_keyboard)
  Ctrl+C              stops the robot and saves what has been mapped so far.

The file only needs rclpy, the standard ROS message packages, numpy, OpenCV
(4.6 apt or newer) and PyYAML, so it also runs as `python3 aruco_slam_mapper.py`.
delivery_navigator.py in the same package imports its building blocks.
"""
import bisect
import csv
import heapq
import math
import os
import threading
import time as _walltime
from datetime import datetime

import cv2
import numpy as np
import yaml

import rclpy
from geometry_msgs.msg import PoseStamped, TransformStamped, Twist
from nav_msgs.msg import OccupancyGrid, Odometry, Path
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from rclpy.signals import SignalHandlerOptions
from rclpy.time import Time
from sensor_msgs.msg import CameraInfo, Image, Imu, LaserScan
from visualization_msgs.msg import Marker, MarkerArray

try:
    import tf2_ros
except ImportError:          # TF is only used for RViz and the laser mount
    tf2_ros = None


class RosTime:
    """Drop-in for time.sleep / time.monotonic that follows the ROS clock.

    With use_sim_time the mission then runs in simulation seconds, so every
    wait, timeout and control period stays right when Gazebo runs faster (or
    slower) than real time. Before a node is attached, or while no /clock has
    arrived yet, it runs on the wall clock. The value never jumps backwards.
    """

    def __init__(self):
        self.node = None
        self._lock = threading.Lock()
        self._value = _walltime.monotonic()
        self._last_wall = self._value
        self._last_ros = 0.0

    def attach(self, node):
        self.node = node

    def monotonic(self):
        with self._lock:
            wall = _walltime.monotonic()
            ros = self.node.get_clock().now().nanoseconds * 1e-9 if self.node else 0.0
            if ros > 0.0 and self._last_ros > 0.0:
                self._value += max(0.0, ros - self._last_ros)      # sim / ROS seconds
            elif ros <= 0.0:
                self._value += wall - self._last_wall              # no clock yet
            self._last_ros, self._last_wall = ros, wall
            return self._value

    time = monotonic

    def sleep(self, seconds):
        end = self.monotonic() + seconds
        while True:
            left = end - self.monotonic()
            if left <= 0.0:
                return
            _walltime.sleep(min(left, 0.002))


time = RosTime()          # module-wide: all mission timing uses ROS time

MAX_LINEAR = 0.8    # m/s, config/rb1_diff_drive_controllers.yaml
MAX_ANGULAR = 1.5   # rad/s


# =============================================================== geometry
def wrap(a):
    """Wrap an angle to [-pi, pi]."""
    return math.atan2(math.sin(a), math.cos(a))


def yaw_from_quaternion(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def compose(a, b):
    """Pose a (x, y, yaw) followed by pose b expressed in a's frame."""
    c, s = math.cos(a[2]), math.sin(a[2])
    return (a[0] + c * b[0] - s * b[1], a[1] + s * b[0] + c * b[1], wrap(a[2] + b[2]))


def inverse(a):
    c, s = math.cos(a[2]), math.sin(a[2])
    return (-c * a[0] - s * a[1], s * a[0] - c * a[1], -a[2])


def default_markers_file():
    try:
        from ament_index_python.packages import get_package_share_directory
        path = os.path.join(get_package_share_directory('indoor_delivery_project'),
                            'config', 'aruco_markers.yaml')
        return path if os.path.isfile(path) else ''
    except Exception:  # noqa: BLE001 - package not installed / not sourced
        return ''


def load_marker_config(path):
    """(dictionary name, {id: info}) from config/aruco_markers.yaml, or defaults."""
    if not path or not os.path.isfile(os.path.expanduser(path)):
        return 'DICT_4X4_50', {}
    with open(os.path.expanduser(path)) as f:
        cfg = yaml.safe_load(f) or {}
    return cfg.get('dictionary', 'DICT_4X4_50'), {
        int(m['id']): m for m in cfg.get('markers', [])}


def image_to_gray(msg):
    """sensor_msgs/Image -> uint8 grayscale (rgb8, bgr8, rgba8, bgra8, mono8)."""
    enc = msg.encoding.lower()
    channels = {'mono8': 1, '8uc1': 1, 'rgb8': 3, 'bgr8': 3, '8uc3': 3,
                'rgba8': 4, 'bgra8': 4, '8uc4': 4}.get(enc)
    if channels is None:
        raise ValueError(f'unsupported image encoding {msg.encoding!r}')
    buf = np.frombuffer(bytes(msg.data), dtype=np.uint8)
    img = buf.reshape(msg.height, msg.step)[:, :msg.width * channels]
    img = img.reshape(msg.height, msg.width, channels) if channels > 1 else img
    if channels == 1:
        return np.ascontiguousarray(img)
    code = {'rgb8': cv2.COLOR_RGB2GRAY, 'rgba8': cv2.COLOR_RGBA2GRAY,
            'bgra8': cv2.COLOR_BGRA2GRAY, '8uc4': cv2.COLOR_BGRA2GRAY}.get(
                enc, cv2.COLOR_BGR2GRAY)
    return cv2.cvtColor(np.ascontiguousarray(img), code)


# ========================================================== ArUco sensor
class MarkerObservation:
    """One marker seen from the robot, in the robot base frame (2D)."""
    __slots__ = ('id', 'range', 'bearing', 'facing', 'distance_3d', 'pixels',
                 'bx', 'by', 'sigma_r', 'sigma_b')

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


class ArucoObserver:
    """Detects markers and turns solvePnP poses into range/bearing/facing.

    camera_offset: (x, y, z) of the camera in base_link (URDF: 0.15, 0, 0.55).
    The camera looks along base_link +X (the URDF mast camera has no rotation).
    """

    def __init__(self, dictionary='DICT_4X4_50', markers=None, default_size=0.30,
                 camera_offset=(0.15, 0.0, 0.55), max_range_per_size=25.0,
                 min_pixels=12.0):
        self.markers = markers or {}
        self.default_size = default_size
        self.cam = camera_offset
        self.max_range_per_size = max_range_per_size
        self.min_pixels = min_pixels
        dict_id = getattr(cv2.aruco, dictionary)
        if hasattr(cv2.aruco, 'ArucoDetector'):                      # >= 4.7
            d = cv2.aruco.getPredefinedDictionary(dict_id)
            self._det = cv2.aruco.ArucoDetector(d, cv2.aruco.DetectorParameters())
            self._detect = self._det.detectMarkers
        else:                                                         # 4.6
            d = cv2.aruco.Dictionary_get(dict_id)
            p = cv2.aruco.DetectorParameters_create()
            self._detect = lambda g: cv2.aruco.detectMarkers(g, d, parameters=p)

    def size_of(self, marker_id):
        return float(self.markers.get(marker_id, {}).get('size', self.default_size))

    def observe(self, gray, K, D):
        corners, ids, _ = self._detect(gray)
        out = []
        if ids is None:
            return out
        for c, mid in zip(corners, ids.ravel().tolist()):
            obs = self.from_corners(int(mid), np.asarray(c, np.float64).reshape(4, 2), K, D)
            if obs is not None:
                out.append(obs)
        return out

    def from_corners(self, marker_id, pts, K, D):
        size = self.size_of(marker_id)
        pixels = float(np.mean(np.linalg.norm(pts - np.roll(pts, 1, axis=0), axis=1)))
        if pixels < self.min_pixels:
            return None
        h = size / 2.0
        obj = np.array([[-h, h, 0], [h, h, 0], [h, -h, 0], [-h, -h, 0]], np.float64)
        ok, rvec, tvec = cv2.solvePnP(obj, pts, K, D, flags=cv2.SOLVEPNP_IPPE_SQUARE)
        if not ok:
            return None
        t = tvec.ravel()           # optical frame: x right, y down, z forward
        bx = self.cam[0] + t[2]
        by = self.cam[1] - t[0]
        rng = math.hypot(bx, by)
        if rng > self.max_range_per_size * size or t[2] <= 0:
            return None
        bearing = math.atan2(by, bx)
        n = cv2.Rodrigues(rvec)[0][:, 2]      # marker normal (points to camera)
        facing = math.atan2(-n[0], n[2])      # same normal in base_link
        if math.cos(facing - (bearing + math.pi)) < math.cos(math.radians(80)):
            return None                       # pose flip / implausible
        # Pixel-size based noise: range error grows with distance / marker size.
        sigma_r = max(0.03, 0.8 * rng / pixels)
        sigma_b = 0.012 + 0.5 / max(pixels, 1.0) * 0.1
        return MarkerObservation(id=marker_id, range=rng, bearing=bearing, facing=facing,
                                 distance_3d=float(np.linalg.norm(t)), pixels=pixels,
                                 bx=bx, by=by, sigma_r=sigma_r, sigma_b=sigma_b)


# ============================================================ EKF (SLAM)
class EkfSlam:
    """EKF over [x, y, yaw, l1x, l1y, l2x, l2y, ...].

    With `fixed_landmarks` ({id: (x, y)}) it is a pure localizer: those markers
    are treated as known and the state stays 3D (used by delivery_navigator).
    """

    def __init__(self, pose=(0.0, 0.0, 0.0), pose_sigma=(0.01, 0.01, 0.01),
                 fixed_landmarks=None, fixed_sigma=0.05, gate=13.8):
        self.x = np.array(pose, dtype=float)
        self.P = np.diag(np.square(pose_sigma)).astype(float)
        self.index = {}                     # marker id -> state index
        self.n_obs = {}
        self.fixed = dict(fixed_landmarks or {})
        self.fixed_var = fixed_sigma ** 2
        self.gate = gate
        self.rejected = 0

    # --------------------------------------------------------- prediction
    def predict(self, dx, dy, dth, a=(0.03, 0.03, 0.02, 0.05), extra_yaw_var=0.0):
        """Odometry increment (dx, dy in the robot frame, dth)."""
        x, y, th = self.x[:3]
        c, s = math.cos(th), math.sin(th)
        self.x[0] = x + c * dx - s * dy
        self.x[1] = y + s * dx + c * dy
        self.x[2] = wrap(th + dth)
        F = np.array([[1, 0, -s * dx - c * dy],
                      [0, 1, c * dx - s * dy],
                      [0, 0, 1]])
        trans, rot = math.hypot(dx, dy), abs(dth)
        q = np.diag([(a[0] * trans) ** 2 + 1e-8, (a[1] * trans) ** 2 + 1e-8,
                     (a[2] * rot + a[3] * trans) ** 2 + 1e-8 + extra_yaw_var])
        G = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
        P = self.P
        P[:3, :] = F @ P[:3, :]
        P[:, :3] = P[:, :3] @ F.T
        P[:3, :3] += G @ q @ G.T

    # ------------------------------------------------------------- update
    def update(self, obs):
        """Range/bearing update. Returns 'new', 'ok', 'gated' or 'fixed-unknown'."""
        if obs.id in self.fixed:
            return self._update_fixed(obs)
        if self.fixed:
            return 'fixed-unknown'
        if obs.id not in self.index:
            self._add(obs)
            return 'new'
        j = self.index[obs.id]
        lx, ly = self.x[j], self.x[j + 1]
        H, zhat = self._jacobian(lx, ly, j)
        return self._correct(obs, H, zhat, self._R(obs))

    def _update_fixed(self, obs):
        lx, ly = self.fixed[obs.id]
        H, zhat = self._jacobian(lx, ly, None)
        R = self._R(obs)
        # map uncertainty of the landmark, mapped into range/bearing
        q = max((lx - self.x[0]) ** 2 + (ly - self.x[1]) ** 2, 1e-6)
        R = R + np.diag([self.fixed_var, self.fixed_var / q])
        return self._correct(obs, H, zhat, R)

    @staticmethod
    def _R(obs):
        return np.diag([obs.sigma_r ** 2, obs.sigma_b ** 2])

    def _jacobian(self, lx, ly, j):
        x, y, th = self.x[:3]
        dx, dy = lx - x, ly - y
        q = max(dx * dx + dy * dy, 1e-9)
        r = math.sqrt(q)
        zhat = np.array([r, wrap(math.atan2(dy, dx) - th)])
        H = np.zeros((2, len(self.x)))
        H[:, :3] = [[-dx / r, -dy / r, 0.0], [dy / q, -dx / q, -1.0]]
        if j is not None:
            H[:, j:j + 2] = [[dx / r, dy / r], [-dy / q, dx / q]]
        return H, zhat

    def _correct(self, obs, H, zhat, R):
        nu = np.array([obs.range - zhat[0], wrap(obs.bearing - zhat[1])])
        S = H @ self.P @ H.T + R
        d2 = float(nu @ np.linalg.solve(S, nu))
        n = self.n_obs.get(obs.id, 0)
        if d2 > self.gate and n > 3:
            self.rejected += 1
            return 'gated'
        K = self.P @ H.T @ np.linalg.inv(S)
        self.x = self.x + K @ nu
        self.x[2] = wrap(self.x[2])
        I_KH = np.eye(len(self.x)) - K @ H
        self.P = I_KH @ self.P @ I_KH.T + K @ R @ K.T     # Joseph form
        self.n_obs[obs.id] = n + 1
        return 'ok'

    def update_pose(self, z, cov, gate=16.0, keep_heading=False):
        """Direct pose measurement (x, y, yaw) with 3x3 covariance (scan matcher)."""
        H = np.zeros((3, len(self.x)))
        H[:, :3] = np.eye(3)
        nu = np.array([z[0] - self.x[0], z[1] - self.x[1], wrap(z[2] - self.x[2])])
        S = self.P[:3, :3] + cov
        if float(nu @ np.linalg.solve(S, nu)) > gate:
            # Many rejections in a row usually mean the filter became
            # over-confident; accept a strongly down-weighted fix to re-lock.
            self.pose_rejects = getattr(self, 'pose_rejects', 0) + 1
            if self.pose_rejects < 10:
                return False
            cov = cov * 25.0
            S = self.P[:3, :3] + cov
        self.pose_rejects = 0
        K = self.P @ H.T @ np.linalg.inv(S)
        if keep_heading:
            K[2, :] = 0.0          # heading belongs to the gyro (Joseph form keeps P valid)
        self.x = self.x + K @ nu
        self.x[2] = wrap(self.x[2])
        I_KH = np.eye(len(self.x)) - K @ H
        self.P = I_KH @ self.P @ I_KH.T + K @ cov @ K.T
        return True

    def _add(self, obs):
        x, y, th = self.x[:3]
        a = th + obs.bearing
        c, s = math.cos(a), math.sin(a)
        lx, ly = x + obs.range * c, y + obs.range * s
        Gx = np.array([[1, 0, -obs.range * s], [0, 1, obs.range * c]])
        Gz = np.array([[c, -obs.range * s], [s, obs.range * c]])
        n = len(self.x)
        self.x = np.append(self.x, [lx, ly])
        P = np.zeros((n + 2, n + 2))
        P[:n, :n] = self.P
        P[n:, :n] = Gx @ self.P[:3, :n]
        P[:n, n:] = P[n:, :n].T
        P[n:, n:] = Gx @ self.P[:3, :3] @ Gx.T + Gz @ self._R(obs) @ Gz.T
        self.P = P
        self.index[obs.id] = n
        self.n_obs[obs.id] = 1

    # ------------------------------------------------------------ queries
    def pose(self):
        return float(self.x[0]), float(self.x[1]), float(self.x[2])

    def set_pose(self, pose, sigma=(0.3, 0.3, 0.2)):
        self.x[:3] = pose
        self.P[:3, :] = 0.0
        self.P[:, :3] = 0.0
        self.P[:3, :3] = np.diag(np.square(sigma))

    def landmarks(self):
        """{id: (x, y, sigma_xy)}"""
        out = {}
        for mid, j in self.index.items():
            sig = math.sqrt(max(self.P[j, j] + self.P[j + 1, j + 1], 0.0) / 2.0)
            out[mid] = (float(self.x[j]), float(self.x[j + 1]), sig)
        return out


class FacingAccumulator:
    """Weighted circular mean of each marker's facing direction (map frame)."""

    def __init__(self):
        self.sums = {}

    def add(self, marker_id, yaw, weight):
        s = self.sums.setdefault(marker_id, [0.0, 0.0, 0.0])
        s[0] += weight * math.cos(yaw)
        s[1] += weight * math.sin(yaw)
        s[2] += weight

    def yaw(self, marker_id):
        s = self.sums.get(marker_id)
        return None if not s or s[2] == 0 else math.atan2(s[1], s[0])


# ======================================================= occupancy grid
class OccupancyGrid2D:
    """Log-odds grid + a 'seen by the camera' layer. Cell (row, col) = (y, x)."""

    L_OCC, L_FREE, L_MIN, L_MAX = 0.85, -0.4, -4.0, 4.0

    def __init__(self, resolution=0.1, size=160.0, center=(0.0, 0.0)):
        self.res = resolution
        n = int(round(size / resolution))
        self.origin = (center[0] - size / 2.0, center[1] - size / 2.0)
        self.logodds = np.zeros((n, n), np.float32)
        self.seen = np.zeros((n, n), bool)

    @property
    def shape(self):
        return self.logodds.shape

    def to_cell(self, xy):
        xy = np.asarray(xy, float)
        c = np.floor((xy[..., 0] - self.origin[0]) / self.res).astype(np.int64)
        r = np.floor((xy[..., 1] - self.origin[1]) / self.res).astype(np.int64)
        return r, c

    def to_world(self, r, c):
        return (self.origin[0] + (np.asarray(c) + 0.5) * self.res,
                self.origin[1] + (np.asarray(r) + 0.5) * self.res)

    def _inside(self, r, c):
        h, w = self.shape
        return (r >= 0) & (r < h) & (c >= 0) & (c < w)

    def update_scan(self, origin_xy, hits_xy, hit_valid, free_step=None):
        """Ray-trace from origin to each end point. hit_valid: True if the beam hit
        something (end point is occupied), False for max-range beams."""
        hits_xy = np.asarray(hits_xy, float)
        if len(hits_xy) == 0:
            return
        o = np.asarray(origin_xy, float)
        d = hits_xy - o
        length = np.hypot(d[:, 0], d[:, 1])
        step = free_step or self.res * 0.9
        n = int(np.ceil(length.max() / step)) + 1
        t = np.arange(n) * step                              # (n,)
        u = d / np.maximum(length, 1e-9)[:, None]            # (B, 2)
        mask = t[None, :] < (length[:, None] - self.res)     # (B, n)
        pts = o[None, None, :] + u[:, None, :] * t[None, :, None]
        r, c = self.to_cell(pts[mask])
        ok = self._inside(r, c)
        h, w = self.shape
        free_idx = np.unique(r[ok] * w + c[ok])
        hr, hc = self.to_cell(hits_xy[hit_valid])
        ok = self._inside(hr, hc)
        hit_idx = np.unique(hr[ok] * w + hc[ok])
        free_idx = np.setdiff1d(free_idx, hit_idx, assume_unique=True)
        flat = self.logodds.reshape(-1)
        flat[free_idx] += self.L_FREE
        flat[hit_idx] += self.L_OCC
        flat[free_idx] = np.clip(flat[free_idx], self.L_MIN, self.L_MAX)
        flat[hit_idx] = np.clip(flat[hit_idx], self.L_MIN, self.L_MAX)

    def clear_disk(self, xy, radius):
        r, c = self.to_cell(xy)
        n = int(math.ceil(radius / self.res))
        r0, c0 = max(int(r) - n, 0), max(int(c) - n, 0)
        sub = self.logodds[r0:int(r) + n + 1, c0:int(c) + n + 1]
        yy, xx = np.mgrid[r0:r0 + sub.shape[0], c0:c0 + sub.shape[1]]
        disk = (yy - r) ** 2 + (xx - c) ** 2 <= n * n
        sub[disk] = np.minimum(sub[disk], 3 * self.L_FREE)

    def mark_seen(self, pts_xy, radius_cells=1):
        r, c = self.to_cell(np.asarray(pts_xy, float))
        h, w = self.shape
        for dr in range(-radius_cells, radius_cells + 1):
            for dc in range(-radius_cells, radius_cells + 1):
                rr, cc = r + dr, c + dc
                ok = self._inside(rr, cc)
                self.seen[rr[ok], cc[ok]] = True

    def ternary(self):
        """int8: -1 unknown, 0 free, 100 occupied."""
        t = np.full(self.shape, -1, np.int8)
        t[self.logodds < -0.4] = 0
        t[self.logodds > 0.6] = 100
        return t

    def ensure_contains(self, xy_min, xy_max, margin=5.0, step=20.0):
        """Grow the grid (in steps of `step` metres) so that the box
        xy_min..xy_max plus `margin` fits. Returns True if it grew."""
        h, w = self.shape
        x0, y0 = self.origin
        x1, y1 = x0 + w * self.res, y0 + h * self.res
        need = [x0 - (xy_min[0] - margin), (xy_max[0] + margin) - x1,
                y0 - (xy_min[1] - margin), (xy_max[1] + margin) - y1]
        if max(need) <= 0.0:
            return False
        cells = [int(math.ceil(max(v, 0.0) / step)) * int(round(step / self.res)) for v in need]
        left, right, bottom, top = cells
        pad = ((bottom, top), (left, right))
        self.logodds = np.pad(self.logodds, pad)
        self.seen = np.pad(self.seen, pad)
        self.origin = (x0 - left * self.res, y0 - bottom * self.res)
        return True

    def known_bbox(self, margin_cells=10):
        known = np.abs(self.logodds) > 0.3
        rows, cols = np.nonzero(known.any(axis=1))[0], np.nonzero(known.any(axis=0))[0]
        if len(rows) == 0:
            return 0, self.shape[0], 0, self.shape[1]
        h, w = self.shape
        return (max(rows[0] - margin_cells, 0), min(rows[-1] + margin_cells + 1, h),
                max(cols[0] - margin_cells, 0), min(cols[-1] + margin_cells + 1, w))

    # ------------------------------------------------------- file / ROS I/O
    def save(self, directory, name='map'):
        r0, r1, c0, c1 = self.known_bbox()
        t = self.ternary()[r0:r1, c0:c1]
        img = np.full(t.shape, 205, np.uint8)       # map_server trinary values
        img[t == 0] = 254
        img[t == 100] = 0
        cv2.imwrite(os.path.join(directory, name + '.pgm'), np.flipud(img))
        ox, oy = self.origin[0] + c0 * self.res, self.origin[1] + r0 * self.res
        meta = {'image': name + '.pgm', 'mode': 'trinary', 'resolution': self.res,
                'origin': [float(round(ox, 4)), float(round(oy, 4)), 0.0],
                'negate': 0, 'occupied_thresh': 0.65, 'free_thresh': 0.25}
        with open(os.path.join(directory, name + '.yaml'), 'w') as f:
            yaml.safe_dump(meta, f, sort_keys=False)
        return os.path.join(directory, name + '.yaml')

    @classmethod
    def load(cls, yaml_path):
        """Load a map_server map (map.yaml + image) as a static grid."""
        yaml_path = os.path.expanduser(yaml_path)
        with open(yaml_path) as f:
            meta = yaml.safe_load(f)
        img_path = meta['image']
        if not os.path.isabs(img_path):
            img_path = os.path.join(os.path.dirname(yaml_path), img_path)
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise FileNotFoundError(img_path)
        img = np.flipud(img).astype(np.float32)
        p = img / 255.0 if meta.get('negate', 0) else (255.0 - img) / 255.0
        g = cls.__new__(cls)
        g.res = float(meta['resolution'])
        g.origin = (float(meta['origin'][0]), float(meta['origin'][1]))
        g.logodds = np.zeros(img.shape, np.float32)
        g.logodds[p > float(meta.get('occupied_thresh', 0.65))] = cls.L_MAX
        g.logodds[p < float(meta.get('free_thresh', 0.25))] = cls.L_MIN
        if meta.get('mode', 'trinary') == 'trinary':
            g.logodds[img == 205] = 0.0            # map_server 'unknown'
        g.seen = np.zeros(img.shape, bool)
        return g

    def to_msg(self, stamp, frame_id='map', crop=True):
        r0, r1, c0, c1 = self.known_bbox() if crop else (0, self.shape[0], 0, self.shape[1])
        t = self.ternary()[r0:r1, c0:c1]
        msg = OccupancyGrid()
        msg.header.stamp = stamp
        msg.header.frame_id = frame_id
        msg.info.resolution = float(self.res)
        msg.info.width, msg.info.height = int(t.shape[1]), int(t.shape[0])
        msg.info.origin.position.x = float(self.origin[0] + c0 * self.res)
        msg.info.origin.position.y = float(self.origin[1] + r0 * self.res)
        msg.info.origin.orientation.w = 1.0
        msg.data = t.reshape(-1).tolist()
        return msg


# ========================================================= scan matcher
class ScanMatcher:
    """Correlative lidar scan-to-map matching (corrects odometry drift between
    marker sightings). Scores candidate poses around the prediction with a
    likelihood field of the occupancy grid; returns the score-weighted mean
    pose and its covariance, so long featureless corridors give a large
    covariance along the corridor instead of a wrong fix."""

    def __init__(self, sigma=0.12, search_xy=0.15, step_xy=0.03, search_th=0.06,
                 step_th=0.01, max_points=180, min_quality=0.35):
        self.sigma = sigma
        d = np.arange(-search_xy, search_xy + 1e-9, step_xy)
        self.dxy = np.array([(x, y) for x in d for y in d])
        self.dth = np.arange(-search_th, search_th + 1e-9, step_th)
        self.max_points = max_points
        self.min_quality = min_quality
        self.step_xy, self.step_th = step_xy, step_th

    def field(self, grid, center=None, half=20.0):
        """(likelihood array, row0, col0, res, origin) for the grid or a window."""
        if center is None:
            r0, r1, c0, c1 = 0, grid.shape[0], 0, grid.shape[1]
        else:
            r, c = grid.to_cell(center[:2])
            n = int(half / grid.res)
            r0, r1 = max(int(r) - n, 0), min(int(r) + n, grid.shape[0])
            c0, c1 = max(int(c) - n, 0), min(int(c) + n, grid.shape[1])
        occ = grid.logodds[r0:r1, c0:c1] > 0.6
        if occ.sum() < 50:
            return None
        dist = cv2.distanceTransform((~occ).astype(np.uint8), cv2.DIST_L2, 5) * grid.res
        lik = np.exp(-0.5 * (dist / self.sigma) ** 2).astype(np.float32)
        return lik, r0, c0, grid.res, grid.origin

    def match(self, field, pose, pts_base, fix_heading=False):
        """pts_base: (N, 2) lidar hits in base_link. Returns (pose, cov) or None.
        fix_heading: search x, y only (heading comes from the gyro)."""
        dths = np.zeros(1) if fix_heading else self.dth
        if field is None or len(pts_base) < 30:
            return None
        lik, r0, c0, res, origin = field
        if len(pts_base) > self.max_points:
            pts_base = pts_base[np.linspace(0, len(pts_base) - 1, self.max_points).astype(int)]
        n = len(pts_base)
        h, w = lik.shape
        best = []
        for dth in dths:
            th = pose[2] + dth
            c, s = math.cos(th), math.sin(th)
            off = np.stack([c * pts_base[:, 0] - s * pts_base[:, 1],
                            s * pts_base[:, 0] + c * pts_base[:, 1]], 1)
            xy = pose[:2] + self.dxy                                  # (M, 2)
            wx = xy[:, None, 0] + off[None, :, 0]
            wy = xy[:, None, 1] + off[None, :, 1]
            cc = np.floor((wx - origin[0]) / res).astype(np.int64) - c0
            rr = np.floor((wy - origin[1]) / res).astype(np.int64) - r0
            ok = (rr >= 0) & (rr < h) & (cc >= 0) & (cc < w)
            vals = np.where(ok, lik[np.clip(rr, 0, h - 1), np.clip(cc, 0, w - 1)], 0.0)
            best.append(vals.sum(axis=1))
        scores = np.stack(best)                                       # (T, M)
        smax = float(scores.max())
        if smax / n < self.min_quality:
            return None
        wts = np.exp((scores - smax) / max(1.0, 0.03 * n))
        wts /= wts.sum()
        cand = np.zeros(scores.shape + (3,))
        cand[..., 0] = pose[0] + self.dxy[None, :, 0]
        cand[..., 1] = pose[1] + self.dxy[None, :, 1]
        cand[..., 2] = pose[2] + dths[:, None]
        cand = cand.reshape(-1, 3)
        wts = wts.reshape(-1)
        mean = (wts[:, None] * cand).sum(axis=0)
        d = cand - mean
        cov = (wts[:, None, None] * d[:, :, None] * d[:, None, :]).sum(axis=0)
        cov = 1.5 * cov + np.diag([0.015 ** 2, 0.015 ** 2, 0.004 ** 2])
        if fix_heading:
            cov[2, :] = cov[:, 2] = 0.0
            cov[2, 2] = 1e4                       # no heading information
        return (float(mean[0]), float(mean[1]), wrap(float(mean[2]))), cov


# ============================================================== planning
def dilate(mask, radius):
    """Binary dilation by a disk of `radius` cells (numpy only)."""
    if radius <= 0:
        return mask.copy()
    out = mask.copy()
    h, w = mask.shape
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            if dr * dr + dc * dc > radius * radius or (dr == 0 and dc == 0):
                continue
            src = mask[max(-dr, 0):h - max(dr, 0), max(-dc, 0):w - max(dc, 0)]
            out[max(dr, 0):h - max(-dr, 0), max(dc, 0):w - max(-dc, 0)] |= src
    return out


_NEIGHBORS = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
              (-1, -1, math.sqrt(2)), (-1, 1, math.sqrt(2)),
              (1, -1, math.sqrt(2)), (1, 1, math.sqrt(2))]


class PlanningGrid:
    """Coarse, inflated grid built from an OccupancyGrid2D, with A*/Dijkstra.

    Cells closer than robot_radius to an obstacle are blocked; cells within
    soft_radius cost more, so paths keep to the middle of corridors and doors.
    """

    def __init__(self, grid, resolution=0.2, robot_radius=0.45, soft_radius=1.0,
                 soft_weight=4.0, unknown_blocked=True, extra_obstacles=None,
                 bbox=None):
        k = max(1, int(round(resolution / grid.res)))
        r0, r1, c0, c1 = bbox or grid.known_bbox(margin_cells=2 * k)
        r1 = r0 + ((r1 - r0) // k) * k
        c1 = c0 + ((c1 - c0) // k) * k
        tern = grid.ternary()[r0:r1, c0:c1]
        h, w = tern.shape[0] // k, tern.shape[1] // k
        blk = tern.reshape(h, k, w, k)
        occ = (blk == 100).any(axis=(1, 3))
        nfree = (blk == 0).sum(axis=(1, 3))
        unknown = ~occ & (nfree * 2 < k * k)
        self.res = grid.res * k
        self.origin = (grid.origin[0] + c0 * grid.res, grid.origin[1] + r0 * grid.res)
        self.shape = (h, w)
        if extra_obstacles is not None and len(extra_obstacles):
            rr, cc = self.to_cell(extra_obstacles)
            ok = (rr >= 0) & (rr < h) & (cc >= 0) & (cc < w)
            occ[rr[ok], cc[ok]] = True
        self.occ = occ
        self.unknown = unknown
        self.free = ~occ & ~unknown
        self.blocked = dilate(occ, int(math.ceil(robot_radius / self.res)))
        if unknown_blocked:
            self.blocked |= unknown
        # soft cost from distance-to-obstacle rings
        soft = max(1, int(round(soft_radius / self.res)))
        ring = np.full((h, w), soft, np.int32)
        cur = self.blocked.copy()
        for i in range(soft):
            ring[cur & (ring == soft)] = i
            cur = dilate(cur, 1)
        self.cost = 1.0 + soft_weight * ((soft - ring) / soft) ** 2
        self.cost[self.blocked] = np.inf

    def to_cell(self, xy):
        xy = np.asarray(xy, float)
        c = np.floor((xy[..., 0] - self.origin[0]) / self.res).astype(np.int64)
        r = np.floor((xy[..., 1] - self.origin[1]) / self.res).astype(np.int64)
        return r, c

    def to_world(self, r, c):
        return (self.origin[0] + (np.asarray(c) + 0.5) * self.res,
                self.origin[1] + (np.asarray(r) + 0.5) * self.res)

    def inside(self, r, c):
        return 0 <= r < self.shape[0] and 0 <= c < self.shape[1]

    def nearest_open(self, xy, max_dist=1.5):
        """Closest unblocked cell to xy (within max_dist m), or None."""
        r, c = self.to_cell(xy)
        r, c = int(r), int(c)
        if self.inside(r, c) and not self.blocked[r, c]:
            return r, c
        rad = int(math.ceil(max_dist / self.res))
        r0, r1 = max(r - rad, 0), min(r + rad + 1, self.shape[0])
        c0, c1 = max(c - rad, 0), min(c + rad + 1, self.shape[1])
        if r0 >= r1 or c0 >= c1:
            return None
        sub = ~self.blocked[r0:r1, c0:c1]
        rr, cc = np.nonzero(sub)
        if len(rr) == 0:
            return None
        d = (rr + r0 - r) ** 2 + (cc + c0 - c) ** 2
        i = int(np.argmin(d))
        if d[i] > rad * rad:
            return None
        return int(rr[i] + r0), int(cc[i] + c0)

    def _search(self, start, goal=None, heuristic=True):
        """Dijkstra (heuristic=False or no goal) or A* over the 8-connected grid.
        Edge cost = step length x mean cell cost (cells near walls cost more)."""
        h, w = self.shape
        cost = self.cost.reshape(-1).tolist()
        n = h * w
        g = [math.inf] * n
        parent = [-1] * n
        s = start[0] * w + start[1]
        g[s] = 0.0
        if goal is not None and heuristic:
            gr, gc = goal
            gi = gr * w + gc

            def heur(i):
                dr, dc = abs(i // w - gr), abs(i % w - gc)
                return (dr + dc) + (math.sqrt(2) - 2) * min(dr, dc)
        else:
            gi = -1 if goal is None else goal[0] * w + goal[1]

            def heur(_i):
                return 0.0
        openq = [(heur(s), s)]
        closed = bytearray(n)
        while openq:
            _, i = heapq.heappop(openq)
            if closed[i]:
                continue
            closed[i] = 1
            if i == gi:
                break
            r, c = divmod(i, w)
            gi_cost = g[i]
            ci = cost[i]
            for dr, dc, step in _NEIGHBORS:
                rr, cc = r + dr, c + dc
                if rr < 0 or rr >= h or cc < 0 or cc >= w:
                    continue
                j = rr * w + cc
                cj = cost[j]
                if cj == math.inf or closed[j]:
                    continue
                ng = gi_cost + step * 0.5 * (ci + cj)
                if ng < g[j]:
                    g[j] = ng
                    parent[j] = i
                    heapq.heappush(openq, (ng + heur(j), j))
        return g, parent, gi

    def astar(self, start_xy, goal_xy, snap=1.5):
        """List of (x, y) waypoints from start to goal (A*), or None."""
        return self.shortest_path(start_xy, goal_xy, snap, method='astar')

    def dijkstra(self, start_xy, goal_xy, snap=1.5):
        """List of (x, y) waypoints from start to goal (Dijkstra), or None."""
        return self.shortest_path(start_xy, goal_xy, snap, method='dijkstra')

    def shortest_path(self, start_xy, goal_xy, snap=1.5, method='dijkstra'):
        s = self.nearest_open(start_xy, snap)
        t = self.nearest_open(goal_xy, snap)
        if s is None or t is None:
            return None
        g, parent, gi = self._search(s, t, heuristic=(method == 'astar'))
        if g[gi] == math.inf:
            return None
        return self._trace(parent, gi, goal_xy, snap)

    def _trace(self, parent, gi, goal_xy, snap):
        w = self.shape[1]
        cells = []
        i = gi
        while i != -1:
            cells.append(divmod(i, w))
            i = parent[i]
        cells.reverse()
        rr = np.array([c[0] for c in cells])
        cc = np.array([c[1] for c in cells])
        xs, ys = self.to_world(rr, cc)
        path = list(zip(xs.tolist(), ys.tolist()))
        path[-1] = (float(goal_xy[0]), float(goal_xy[1])) if \
            math.hypot(path[-1][0] - goal_xy[0], path[-1][1] - goal_xy[1]) < 0.5 * snap \
            else path[-1]
        return path

    def distances(self, start_xy, snap=1.5):
        """Path-cost (metres-ish) from start to every cell; inf = unreachable."""
        s = self.nearest_open(start_xy, snap)
        if s is None:
            return None
        g, _, _ = self._search(s)
        return np.array(g).reshape(self.shape) * self.res

    def dijkstra_tree(self, start_xy, snap=1.5):
        """One full Dijkstra from start: (cost list, parent list) over all cells,
        so the shortest path to ANY cell can be read out afterwards."""
        s = self.nearest_open(start_xy, snap)
        if s is None:
            return None
        g, parent, _ = self._search(s)
        return g, parent

    def tree_cost(self, tree, xy, snap=1.5):
        cell = self.nearest_open(xy, snap)
        if tree is None or cell is None:
            return math.inf
        return tree[0][cell[0] * self.shape[1] + cell[1]] * self.res

    def tree_path(self, tree, xy, snap=1.5):
        cell = self.nearest_open(xy, snap)
        if tree is None or cell is None:
            return None
        gi = cell[0] * self.shape[1] + cell[1]
        if tree[0][gi] == math.inf:
            return None
        return self._trace(tree[1], gi, xy, snap)

    def line_of_sight(self, a, b, stop_short=0.3):
        """True if the straight segment a->b crosses no occupied cell."""
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(2, int(d / (self.res * 0.5)))
        for t in np.linspace(0.0, max(0.0, 1.0 - stop_short / max(d, 1e-6)), n):
            r, c = self.to_cell((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
            if not self.inside(int(r), int(c)) or self.occ[int(r), int(c)]:
                return False
        return True


# ========================================================= exploration
def choose_exploration_target(grid, plan, pose, blacklist, view_range=(2.0, 3.5),
                              block_size=2.5, min_block_cells=6, blacklist_radius=1.0):
    """Next goal for full coverage, or None when everything has been covered.

    Returns dict(kind='frontier'|'view', goal=(x, y), look_at=(x, y) or None,
    key=..., cost=...). 'view' goals stand in front of wall stretches that the
    camera has not looked at from close range, so every marker gets detected.
    """
    dist = plan.distances(pose[:2])
    if dist is None:
        return None
    reach = np.isfinite(dist) & ~plan.blocked
    candidates = []

    points, keys = blacklist['points'], blacklist['keys']

    def blacklisted(xy):
        return any(math.hypot(xy[0] - b[0], xy[1] - b[1]) < blacklist_radius
                   for b in points)

    # --- frontiers: reachable free cells next to unknown space
    unk = plan.unknown
    nb_unknown = np.zeros_like(unk)
    nb_unknown[1:, :] |= unk[:-1, :]
    nb_unknown[:-1, :] |= unk[1:, :]
    nb_unknown[:, 1:] |= unk[:, :-1]
    nb_unknown[:, :-1] |= unk[:, 1:]
    front = reach & plan.free & nb_unknown
    if front.any():
        rr, cc = np.nonzero(front)
        order = np.argsort(dist[rr, cc])
        for i in order[:400]:
            xy = tuple(float(v) for v in plan.to_world(rr[i], cc[i]))
            if math.hypot(xy[0] - pose[0], xy[1] - pose[1]) < 1.0 or blacklisted(xy):
                continue
            # require a few frontier cells around it (ignore single-cell noise)
            r0, c0 = rr[i], cc[i]
            if front[max(r0 - 2, 0):r0 + 3, max(c0 - 2, 0):c0 + 3].sum() < 3:
                continue
            candidates.append(dict(kind='frontier', goal=xy, look_at=None, key=xy,
                                   cost=float(dist[r0, c0])))
            break

    # --- wall stretches not yet seen by the camera
    occ = grid.logodds > 0.6
    todo = occ & ~grid.seen
    if todo.any():
        r, c = np.nonzero(todo)
        wx, wy = grid.to_world(r, c)
        bx = np.floor(wx / block_size).astype(np.int64)
        by = np.floor(wy / block_size).astype(np.int64)
        bkeys, inv, counts = np.unique(np.stack([bx, by], 1), axis=0,
                                      return_inverse=True, return_counts=True)
        inv = inv.ravel()
        rr, cc = np.nonzero(reach)
        if len(rr):
            px, py = plan.to_world(rr, cc)
            pd = dist[rr, cc]
            best = None
            for k in np.nonzero(counts >= min_block_cells)[0]:
                sel = inv == k
                centre = (float(wx[sel].mean()), float(wy[sel].mean()))
                key = ('view', int(bkeys[k][0]), int(bkeys[k][1]))
                if key in keys or blacklisted(centre):
                    continue
                e = np.hypot(px - centre[0], py - centre[1])
                band = np.nonzero((e > view_range[0]) & (e < view_range[1]))[0]
                if len(band) == 0:
                    continue
                for j in band[np.argsort(pd[band])][:15]:
                    vp = (float(px[j]), float(py[j]))
                    if plan.line_of_sight(vp, centre):
                        if best is None or pd[j] < best['cost']:
                            best = dict(kind='view', goal=vp, look_at=centre, key=key,
                                        cost=float(pd[j]))
                        break
            if best is not None:
                candidates.append(best)
    if not candidates:
        return None
    return min(candidates, key=lambda t: t['cost'])


def coverage_stats(grid):
    occ = grid.logodds > 0.6
    n = int(occ.sum())
    seen = int((occ & grid.seen).sum())
    free = int((grid.logodds < -0.4).sum())
    return dict(wall_cells=n, wall_seen=seen,
                wall_seen_pct=100.0 * seen / n if n else 0.0,
                free_area_m2=free * grid.res ** 2)


# ===================================================== ROS robot base
class MissionAborted(Exception):
    """Raised from the drive helpers when abort_event is set (e.g. a Stop button)."""


class ArucoRobotBase(Node):
    """Shared ROS plumbing for the mapper and the navigator.

    Subclasses provide `self.ekf` (EkfSlam) and override `nav_grid()`.
    Callbacks run in a background MultiThreadedExecutor, the mission runs in
    the main thread and talks to the robot through drive helpers below.
    """
    LIVE_SCAN_MATCHING = True   # navigator: lidar localization on the saved map
    ANGULAR_SPEED = 0.8         # rad/s
    GYRO_NOISE = 0.0015         # navigator: the lidar match on the saved map corrects heading
    GYRO_ALPHA = (0.005, 0.001)


    def __init__(self, name):
        super().__init__(name)
        p = self.declare_parameter
        p('sim', True)
        p('odom_topic', '/robot/diff_drive_controller/odom')
        p('scan_topic', '/robot/front_laser/scan')
        p('image_topic', '/robot/aruco_camera/image_raw')
        p('camera_info_topic', '/robot/aruco_camera/camera_info')
        p('cmd_vel_topic', '/cmd_vel')
        p('imu_topic', '/robot/imu/data')
        p('use_imu', True)                       # gyro yaw rate instead of wheel yaw (wheels slip in turns)
        p('gyro_noise', self.GYRO_NOISE)         # rad/sqrt(s), heading random walk
        # heading noise with the gyro: per rad turned (scale error), per m driven.
        # Small: the gyro does not slip, so a marker sighting must not be able
        # to swing the heading by many degrees (that bends the map).
        p('gyro_alpha', list(self.GYRO_ALPHA))
        # Use each sensor's time stamp: a camera image or a scan that is older or
        # newer than the latest odometry is moved by the motion in between
        # (gyro + wheels) before it is used. Matters in fast simulation, where
        # the sensors arrive with different delays while the robot turns.
        p('sync_sensors', True)
        p('camera_time_error', 0.1)              # s, image timing uncertainty (bearing noise x turn rate)
        p('max_turn_rate_for_markers', 0.5)      # rad/s; faster spins: markers not used for the pose
        p('odom_alpha', [0.05, 0.05, 0.06, 0.1])  # odometry noise: x/m, y/m, yaw/rad, yaw/m
        p('markers_file', default_markers_file())
        p('map_frame', 'map')
        p('odom_frame', 'odom')
        p('base_frame', 'base_link')
        p('camera_offset', [0.15, 0.0, 0.55])
        p('laser_offset', [0.21, 0.0, 0.0])     # used only if TF is unavailable
        p('laser_upside_down', True)             # URDF mounts it rpy="0 pi pi"
        p('camera_rate', 6.0)
        p('linear_speed', 0.45)
        p('angular_speed', self.ANGULAR_SPEED)
        p('robot_radius', 0.45)                  # RB1 ~0.28 m + safety margin
        p('stop_distance', 0.35)                 # lidar emergency stop, from bumper
        p('lookahead', 0.8)
        p('goal_tolerance', 0.15)
        p('planner', 'dijkstra')                 # 'dijkstra' or 'astar' (same paths, A* faster)
        p('self_filter_radius', 0.32)            # ignore lidar hits on the robot body
        p('known_markers_only', True)            # ignore IDs not in markers_file
        p('scan_matching', self.LIVE_SCAN_MATCHING)   # live lidar correction
        p('max_scan_rate', 40.0)                 # scans per WALL second (CPU guard), 0 = all
        if self.get_parameter('sim').value:
            self.set_parameters([Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        if isinstance(time, RosTime):
            time.attach(self)                    # waits and timeouts in sim seconds
        g = lambda n: self.get_parameter(n).value  # noqa: E731
        self.gp = g

        dict_name, self.marker_info = load_marker_config(g('markers_file'))
        self.observer = ArucoObserver(dict_name, self.marker_info,
                                      camera_offset=tuple(g('camera_offset')))
        self.lock = threading.RLock()
        self.abort_event = threading.Event()     # set it to stop any running drive
        self.current_path = []                   # last planned path (for displays)
        self.last_cmd = (0.0, 0.0)
        self.matcher = ScanMatcher() if g('scan_matching') else None
        self.match_count = 0
        self.ekf = None
        self.facing = FacingAccumulator()
        self.K = self.D = None
        self.cam_hfov = 1.2
        self._last_odom = None
        self.dr_pose = (0.0, 0.0, 0.0)    # wheels for distance + gyro for heading
        self.imu_yaw = None              # integrated gyro yaw
        self._imu_stamp = None
        self._imu_rate = None
        self._imu_wall = -1.0
        self._imu_at_odom = None
        self._odom_t = None
        self._imu_t, self._imu_y = [], []          # gyro yaw history (stamp, yaw)
        self._odom_h = []                         # (stamp, odom pose, dead-reckoning pose)
        self.odom_pose = None
        self._last_image_t = 0.0
        self._last_scan_wall = 0.0
        self.last_obs = []
        self.last_obs_wall = 0.0
        self.scan_base = None          # (N, 2) lidar points in base_link
        self.scan_valid = None
        self.scan_angles_base = None
        self.scan_wall = 0.0
        self._laser_T = None           # (R 3x3, t 3) laser -> base
        self.tf_buffer = None
        if tf2_ros is not None:
            self.tf_buffer = tf2_ros.Buffer()
            self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
            self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)
        self.cmd_pub = self.create_publisher(Twist, g('cmd_vel_topic'), 10)
        self.path_pub = self.create_publisher(Path, '~/plan', 1)
        self.lm_pub = self.create_publisher(MarkerArray, '~/landmarks', 1)
        latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.map_pub = self.create_publisher(OccupancyGrid, '/map', latched)
        self.create_subscription(Odometry, g('odom_topic'), self._odom_cb,
                                 qos_profile_sensor_data)
        if g('use_imu'):
            self.create_subscription(Imu, g('imu_topic'), self._imu_cb, qos_profile_sensor_data)
        self.create_subscription(LaserScan, g('scan_topic'), self._scan_cb,
                                 qos_profile_sensor_data)
        self.create_subscription(CameraInfo, g('camera_info_topic'), self._info_cb,
                                 qos_profile_sensor_data)
        self.create_subscription(Image, g('image_topic'), self._image_cb,
                                 qos_profile_sensor_data)
        self.create_timer(0.05, self._tf_timer)
        self.create_timer(1.0, self._landmark_timer)

    # ------------------------------------------------------------- hooks
    def on_observations(self, stamp, obs, pose, odom):
        """Called (under lock) after the EKF processed a camera frame."""

    def on_scan(self, stamp, pose):
        """Called (under lock) after a scan was converted to base_link."""

    def nav_grid(self):
        raise NotImplementedError

    def apply_scan_match(self, field):
        """Match the latest scan against `field`, fuse into the EKF (under lock)."""
        if self.matcher is None or field is None:
            return False
        pts = self.scan_base[self.scan_valid]
        gyro = time.monotonic() - self._imu_wall < 0.5
        stamp = getattr(self, 'scan_stamp', None)
        pose_s, M = self.pose_at(stamp) if stamp is not None else (self.ekf.pose(), (0.0, 0.0, 0.0))
        res = self.matcher.match(field, pose_s, pts, fix_heading=gyro)
        if res is None:
            return False
        ok = self.ekf.update_pose(compose(res[0], M), res[1], keep_heading=gyro)
        self.match_count += int(ok)
        return ok

    def landmark_positions(self):
        """{id: (x, y)} for RViz."""
        with self.lock:
            return {k: v[:2] for k, v in self.ekf.landmarks().items()} if self.ekf else {}

    # --------------------------------------------------------- callbacks
    def _odom_cb(self, msg):
        p = msg.pose.pose
        cur = (p.position.x, p.position.y, yaw_from_quaternion(p.orientation))
        with self.lock:
            last = self._last_odom
            self._last_odom = cur
            self.odom_pose = cur
            self.odom_stamp = msg.header.stamp
            t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            imu = None
            if time.monotonic() - self._imu_wall < 0.5:
                imu = self.gyro_yaw_at(t) if self.gp('sync_sensors') else self.imu_yaw
            imu_last, self._imu_at_odom = self._imu_at_odom, imu
            dt = 0.0 if self._odom_t is None else clamp(t - self._odom_t, 0.0, 0.5)
            self._odom_t = t
            if last is None:
                return
            d = compose(inverse(last), cur)
            gyro_ok = imu is not None and imu_last is not None
            self.dr_pose = compose(self.dr_pose, (d[0], d[1], imu - imu_last if gyro_ok else d[2]))
            if not self._odom_h or t > self._odom_h[-1][0]:
                self._odom_h.append((t, cur, self.dr_pose))
                if len(self._odom_h) > 600:
                    del self._odom_h[:100]
            if self.ekf is None:
                return
            alpha = self.gp('odom_alpha')
            if imu is None or imu_last is None:
                self.ekf.predict(d[0], d[1], d[2], a=alpha)
            else:
                # the gyro is far better than wheels in turns: yaw noise from it only
                ga = self.gp('gyro_alpha')
                self.ekf.predict(d[0], d[1], imu - imu_last,
                                 a=(alpha[0], alpha[1], ga[0], ga[1]),
                                 extra_yaw_var=self.gp('gyro_noise') ** 2 * dt)

    # ------------------------------------------------- time alignment
    def gyro_yaw_at(self, t):
        """Integrated gyro yaw at stamp t (interpolated; clamped to the history)."""
        ts = self._imu_t
        if not ts:
            return self.imu_yaw
        i = bisect.bisect_left(ts, t)
        if i <= 0:
            return self._imu_y[0]
        if i >= len(ts):
            return self._imu_y[-1]
        a = (t - ts[i - 1]) / max(ts[i] - ts[i - 1], 1e-9)
        return self._imu_y[i - 1] + a * (self._imu_y[i] - self._imu_y[i - 1])

    def odom_at(self, t):
        """(odom pose, dead-reckoning pose) at stamp t, interpolated."""
        h = self._odom_h
        if not h:
            return self.odom_pose, self.dr_pose
        i = bisect.bisect_left(h, t, key=lambda e: e[0])
        if i <= 0:
            return h[0][1], h[0][2]
        if i >= len(h):
            return h[-1][1], h[-1][2]
        (t0, o0, d0), (t1, o1, d1) = h[i - 1], h[i]
        a = (t - t0) / max(t1 - t0, 1e-9)

        def lerp(p, q):
            return (p[0] + a * (q[0] - p[0]), p[1] + a * (q[1] - p[1]),
                    wrap(p[2] + a * wrap(q[2] - p[2])))
        return lerp(o0, o1), lerp(d0, d1)

    def motion_between(self, t1, t2):
        """Robot pose at stamp t2 in the robot frame at stamp t1 (wheels for the
        distance, gyro for the turn). (0, 0, 0) if it is not known."""
        if not self.gp('sync_sensors') or self._odom_t is None or abs(t2 - t1) < 1e-4 \
                or abs(t2 - t1) > 2.0:
            return (0.0, 0.0, 0.0)
        o1, _ = self.odom_at(t1)
        o2, _ = self.odom_at(t2)
        if o1 is None or o2 is None:
            return (0.0, 0.0, 0.0)
        d = compose(inverse(o1), o2)
        if self._imu_t and time.monotonic() - self._imu_wall < 0.5:
            d = (d[0], d[1], self.gyro_yaw_at(t2) - self.gyro_yaw_at(t1))
        return d

    def pose_at(self, stamp):
        """EKF pose moved back/forward to a sensor stamp, and the motion M from
        that stamp to the EKF time (pose_ekf = pose_at o M)."""
        pose = self.ekf.pose()
        if self._odom_t is None:
            return pose, (0.0, 0.0, 0.0)
        t = stamp.sec + stamp.nanosec * 1e-9
        M = self.motion_between(t, self._odom_t)
        return compose(pose, inverse(M)), M

    @staticmethod
    def shift_observation(o, M):
        """Marker seen at the image time, expressed at the EKF time (robot moved by M)."""
        if M == (0.0, 0.0, 0.0):
            return o
        c, s = math.cos(M[2]), math.sin(M[2])
        px, py = o.bx - M[0], o.by - M[1]
        bx, by = c * px + s * py, -s * px + c * py
        return MarkerObservation(id=o.id, range=math.hypot(bx, by), bearing=math.atan2(by, bx),
                                 facing=wrap(o.facing - M[2]), distance_3d=o.distance_3d,
                                 pixels=o.pixels, bx=bx, by=by, sigma_r=o.sigma_r,
                                 sigma_b=o.sigma_b)

    def weight_by_turn_rate(self, obs, t_img):
        """While the robot spins, a few tens of ms of camera timing error turn into
        degrees of bearing error (at 50 deg/s, 0.1 s = 5 deg), and the EKF would
        pass that straight into the heading. So the bearing noise grows with the
        turn rate, and above max_turn_rate_for_markers the sighting is not used."""
        if not self._imu_t or time.monotonic() - self._imu_wall > 0.5:
            return obs
        rate = abs(self.gyro_yaw_at(t_img + 0.1) - self.gyro_yaw_at(t_img - 0.1)) / 0.2
        if rate > self.gp('max_turn_rate_for_markers'):
            return []
        extra = (rate * self.gp('camera_time_error')) ** 2
        if extra < 1e-8:
            return obs
        out = []
        for o in obs:
            o2 = MarkerObservation(**{k: getattr(o, k) for k in MarkerObservation.__slots__})
            o2.sigma_b = math.sqrt(o.sigma_b ** 2 + extra)
            out.append(o2)
        return out

    def _imu_cb(self, msg):
        """Integrate the gyro z rate (smooth, no magnetometer needed)."""
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        with self.lock:
            if self._imu_stamp is None:
                self.imu_yaw = 0.0
                self.get_logger().info('Gyro yaw rate in use for heading prediction')
            else:
                dt = t - self._imu_stamp
                wz = msg.angular_velocity.z
                # trapezoid; gaps (messages dropped in fast simulation) up to 1 s are
                # bridged instead of losing that part of the turn
                if 0.0 < dt < 1.0:
                    w0 = self._imu_rate if self._imu_rate is not None else wz
                    self.imu_yaw += 0.5 * (w0 + wz) * dt
            self._imu_rate = msg.angular_velocity.z
            self._imu_stamp = t
            self._imu_wall = time.monotonic()
            if not self._imu_t or t > self._imu_t[-1]:
                self._imu_t.append(t)
                self._imu_y.append(self.imu_yaw)
                if len(self._imu_t) > 1200:
                    del self._imu_t[:200], self._imu_y[:200]

    def _info_cb(self, msg):
        K = np.array(msg.k, dtype=np.float64).reshape(3, 3)
        if K[0, 0] <= 0:
            return
        self.K = K
        self.D = np.array(msg.d, dtype=np.float64) if len(msg.d) else np.zeros(5)
        self.cam_hfov = 2.0 * math.atan2(msg.width / 2.0, K[0, 0])

    def _image_cb(self, msg):
        now = time.monotonic()
        if self.K is None or self.ekf is None or \
                now - self._last_image_t < 1.0 / self.gp('camera_rate'):
            return
        self._last_image_t = now
        try:
            gray = image_to_gray(msg)
        except ValueError as exc:
            self.get_logger().warning(str(exc), throttle_duration_sec=5.0)
            return
        obs = self.observer.observe(gray, self.K, self.D)
        if self.marker_info and self.gp('known_markers_only'):
            obs = [o for o in obs if o.id in self.marker_info]   # drop misreads
        with self.lock:
            if obs and self._odom_t is not None:
                t_img = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
                M = self.motion_between(t_img, self._odom_t)
                obs = [self.shift_observation(o, M) for o in obs]
                obs = self.weight_by_turn_rate(obs, t_img)
            pose_before = self.ekf.pose()
            for o in obs:
                self.ekf.update(o)
            pose = self.ekf.pose()
            for o in obs:
                w = 1.0 / max(o.range, 1.0) ** 2
                self.facing.add(o.id, pose[2] + o.facing, w)
            self.last_obs = obs
            self.last_obs_wall = now
            self.on_observations(msg.header.stamp, obs, pose_before, self.odom_pose)

    def _laser_transform(self, frame_id):
        if self._laser_T is not None:
            return self._laser_T
        if self.tf_buffer is not None:
            try:
                tf = self.tf_buffer.lookup_transform(
                    self.gp('base_frame'), frame_id, Time())
                q = tf.transform.rotation
                x, y, z, w = q.x, q.y, q.z, q.w
                R = np.array([
                    [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                    [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                    [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
                t = tf.transform.translation
                self._laser_T = (R, np.array([t.x, t.y, t.z]))
                self.get_logger().info(
                    f'Laser mount from TF ({frame_id}): x={t.x:.3f} y={t.y:.3f} '
                    f'{"upside down" if R[2, 2] < 0 else "upright"}')
                return self._laser_T
            except Exception:  # noqa: BLE001 - not yet available
                if not hasattr(self, '_tf_wait_start'):
                    self._tf_wait_start = time.monotonic()
                if time.monotonic() - self._tf_wait_start < 3.0:
                    return None
        off = self.gp('laser_offset')
        R = np.diag([1.0, -1.0, -1.0]) if self.gp('laser_upside_down') else np.eye(3)
        self._laser_T = (R, np.array(off, float))
        self.get_logger().warning('No TF for the laser: using laser_offset / '
                               'laser_upside_down parameters.')
        return self._laser_T

    def _scan_cb(self, msg):
        # CPU guard for fast simulation (real_time_factor > 1): at most
        # max_scan_rate scans per wall second are processed, the rest skipped
        rate = self.gp('max_scan_rate')
        wall = _walltime.monotonic()
        if rate > 0 and wall - self._last_scan_wall < 1.0 / rate:
            return
        self._last_scan_wall = wall
        T = self._laser_transform(msg.header.frame_id)
        if T is None:
            return
        R, t = T
        ranges = np.asarray(msg.ranges, np.float32)
        ang = msg.angle_min + np.arange(len(ranges)) * msg.angle_increment
        rmax = min(msg.range_max, 20.0)
        valid = np.isfinite(ranges) & (ranges > max(msg.range_min, 0.15)) & (ranges < rmax - 0.05)
        r = np.where(valid, ranges, rmax)
        pts = np.stack([r * np.cos(ang), r * np.sin(ang), np.zeros_like(r)], 1)
        base = pts @ R.T + t
        body = np.hypot(base[:, 0], base[:, 1]) < self.gp('self_filter_radius')
        valid &= ~body
        with self.lock:
            self.scan_base = base[:, :2]
            self.scan_valid = valid
            self.scan_use = ~body
            self.scan_origin_base = t[:2]
            self.scan_wall = time.monotonic()
            self.scan_stamp = msg.header.stamp
            if self.ekf is not None:
                self.on_scan(msg.header.stamp, self.ekf.pose())

    def _tf_timer(self):
        if tf2_ros is None or self.ekf is None:
            return
        with self.lock:
            if self.odom_pose is None:
                return
            m_o = compose(self.ekf.pose(), inverse(self.odom_pose))
            stamp = self.odom_stamp
        tf = TransformStamped()
        tf.header.stamp = stamp
        tf.header.frame_id = self.gp('map_frame')
        tf.child_frame_id = self.gp('odom_frame')
        tf.transform.translation.x, tf.transform.translation.y = m_o[0], m_o[1]
        tf.transform.rotation.z = math.sin(m_o[2] / 2.0)
        tf.transform.rotation.w = math.cos(m_o[2] / 2.0)
        self.tf_broadcaster.sendTransform(tf)

    def _landmark_timer(self):
        arr = MarkerArray()
        stamp = self.get_clock().now().to_msg()
        for mid, (x, y) in self.landmark_positions().items():
            info = self.marker_info.get(mid, {})
            for k, (typ, scale, z) in enumerate([(Marker.CYLINDER, 0.3, 0.6),
                                                 (Marker.TEXT_VIEW_FACING, 0.5, 1.6)]):
                m = Marker()
                m.header.frame_id = self.gp('map_frame')
                m.header.stamp = stamp
                m.ns = 'aruco' if k == 0 else 'aruco_text'
                m.id = int(mid)
                m.type = typ
                m.pose.position.x, m.pose.position.y, m.pose.position.z = x, y, z
                m.pose.orientation.w = 1.0
                m.scale.x = m.scale.y = 0.3
                m.scale.z = scale if k else 1.2
                m.color.a = 1.0
                m.color.r, m.color.g, m.color.b = ((0.1, 0.8, 0.2) if info.get('kind') == 'delivery'
                                                   else (0.2, 0.4, 1.0))
                m.text = f"{mid} {info.get('name', '')}"
                arr.markers.append(m)
        self.lm_pub.publish(arr)

    # ------------------------------------------------------ drive helpers
    def pose(self):
        with self.lock:
            return self.ekf.pose()

    def _publish_cmd(self, v, w):
        self.last_cmd = (float(v), float(w))
        msg = Twist()
        msg.linear.x = float(clamp(v, -MAX_LINEAR, MAX_LINEAR))
        msg.angular.z = float(clamp(w, -MAX_ANGULAR, MAX_ANGULAR))
        self.cmd_pub.publish(msg)

    def send(self, v, w):
        if self.abort_event.is_set():
            self._publish_cmd(0.0, 0.0)
            raise MissionAborted()
        self._publish_cmd(v, w)

    def stop(self):
        for _ in range(3):
            self._publish_cmd(0.0, 0.0)
            time.sleep(0.03)

    def sim_now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def wait_for_sensors(self, timeout=60.0, need_camera=True):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            ok = self.odom_pose is not None and self.scan_base is not None
            if need_camera:
                ok = ok and self.K is not None
            if ok:
                if self.gp('use_imu'):
                    t_imu = time.monotonic() + 2.0
                    while self._imu_stamp is None and time.monotonic() < t_imu:
                        time.sleep(0.1)
                    if self._imu_stamp is None:
                        self.get_logger().warning(
                            f'No gyro data on {self.gp("imu_topic")}: heading comes from the '
                            'wheels, which slip in turns. In Gazebo the world needs '
                            '<plugin filename="gz-sim-imu-system" name="gz::sim::systems::Imu"/>.')
                return True
            time.sleep(0.2)
        missing = [n for n, v in [('odometry', self.odom_pose), ('lidar', self.scan_base),
                                  ('camera_info', self.K)] if v is None]
        self.get_logger().error(f'No data from: {", ".join(missing)}. Is the sim running?')
        return False

    def front_blocked(self, v_sign=1.0):
        """True if the lidar sees something right in front of the robot."""
        with self.lock:
            pts, ok = self.scan_base, self.scan_valid
        if pts is None:
            return False
        front = self.gp('robot_radius') - 0.1 + self.gp('stop_distance')
        half = self.gp('robot_radius') - 0.1
        p = pts[ok]
        if v_sign < 0:
            return False                          # lidar only looks forward
        sel = (p[:, 0] > 0.0) & (p[:, 0] < front) & (np.abs(p[:, 1]) < half)
        return bool(sel.sum() >= 3)

    def new_obstacles(self, pts_world):
        """Scan points that are real obstacles (subclasses drop mapped walls)."""
        return pts_world

    def recover_pose(self):
        """Try to fix a wrong pose estimate; True if it was corrected."""
        return False

    def scan_points_world(self, max_range=3.0):
        with self.lock:
            pts, ok = self.scan_base, self.scan_valid
            pose = self.ekf.pose()
        if pts is None:
            return np.zeros((0, 2))
        p = pts[ok]
        p = p[np.hypot(p[:, 0], p[:, 1]) < max_range]
        c, s = math.cos(pose[2]), math.sin(pose[2])
        return np.stack([pose[0] + c * p[:, 0] - s * p[:, 1],
                         pose[1] + s * p[:, 0] + c * p[:, 1]], 1)

    def turn_to(self, yaw, tol=0.04, timeout=30.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            err = wrap(yaw - self.pose()[2])
            if abs(err) < tol:
                break
            w = math.copysign(clamp(1.8 * abs(err), 0.15, self.gp('angular_speed')), err)
            self.send(0.0, w)
            time.sleep(0.05)
        self.stop()

    def rotate(self, angle, speed=None, timeout=60.0):
        """Rotate in place by a signed angle (can exceed 2*pi), on odometry."""
        speed = speed or self.gp('angular_speed') * 0.6
        turned = 0.0
        last = self.odom_pose[2]
        end = time.monotonic() + timeout
        while abs(turned) < abs(angle) and time.monotonic() < end:
            self.send(0.0, math.copysign(speed, angle))
            time.sleep(0.05)
            cur = self.odom_pose[2]
            turned += wrap(cur - last)
            last = cur
        self.stop()

    def publish_path(self, path):
        self.current_path = [tuple(p) for p in path]
        msg = Path()
        msg.header.frame_id = self.gp('map_frame')
        msg.header.stamp = self.get_clock().now().to_msg()
        for x, y in path:
            ps = PoseStamped()
            ps.header = msg.header
            ps.pose.position.x, ps.pose.position.y = float(x), float(y)
            ps.pose.orientation.w = 1.0
            msg.poses.append(ps)
        self.path_pub.publish(msg)

    def follow(self, path, timeout=None, replan_period=None):
        """Pure pursuit along path. Returns 'reached', 'blocked', 'timeout', 'replan'."""
        if not path:
            return 'reached'
        L = self.gp('lookahead')
        vmax = self.gp('linear_speed')
        wmax = self.gp('angular_speed')
        tol = self.gp('goal_tolerance')
        pts = np.asarray(path, float)
        seg = np.hypot(*np.diff(pts, axis=0).T) if len(pts) > 1 else np.zeros(0)
        length = float(seg.sum())
        timeout = timeout or 30.0 + 4.0 * length / max(vmax, 0.05)
        start = time.monotonic()
        idx = 0
        blocked_since = None
        while True:
            now = time.monotonic()
            if now - start > timeout:
                self.stop()
                return 'timeout'
            if replan_period and now - start > replan_period:
                return 'replan'
            x, y, th = self.pose()
            gx, gy = pts[-1]
            dgoal = math.hypot(gx - x, gy - y)
            if dgoal < tol:
                self.stop()
                return 'reached'
            # progress along the path (only forward, within a window)
            win = pts[idx:idx + 40]
            idx += int(np.argmin(np.hypot(win[:, 0] - x, win[:, 1] - y)))
            j = idx
            while j < len(pts) - 1 and math.hypot(pts[j, 0] - x, pts[j, 1] - y) < L:
                j += 1
            tx, ty = pts[j]
            alpha = wrap(math.atan2(ty - y, tx - x) - th)
            if abs(alpha) > 0.9:
                v, w = 0.0, math.copysign(clamp(1.5 * abs(alpha), 0.3, wmax), alpha)
            else:
                ld = max(math.hypot(tx - x, ty - y), 0.2)
                v = vmax * (1.0 - 0.6 * min(abs(alpha) / 0.9, 1.0))
                v = min(v, max(0.12, 0.8 * dgoal))
                w = clamp(2.0 * v * math.sin(alpha) / ld, -wmax, wmax)
            if v > 0 and self.front_blocked():
                self.send(0.0, 0.0)
                blocked_since = blocked_since or now
                if now - blocked_since > 2.0:
                    self.stop()
                    return 'blocked'
                time.sleep(0.1)
                continue
            blocked_since = None
            self.send(v, w)
            time.sleep(0.1)

    def navigate_to(self, goal, final_yaw=None, unknown_blocked=True, max_attempts=6,
                    replan_period=None, timeout=None):
        """Plan on nav_grid() (Dijkstra or A*, param planner) and drive there, replanning around obstacles.

        Returns True when the goal was reached.
        """
        extra = np.zeros((0, 2))
        deadline = time.monotonic() + (timeout or 1e9)
        attempts = 0
        recoveries = 0
        while attempts < max_attempts and time.monotonic() < deadline:
            plan = self.nav_grid(extra_obstacles=extra, unknown_blocked=unknown_blocked)
            pose = self.pose()
            path = plan.shortest_path(pose[:2], goal, method=self.gp('planner'))
            if path is None:
                attempts += 1
                self.get_logger().warning(f'No path to ({goal[0]:.1f}, {goal[1]:.1f}) '
                                       f'(attempt {attempts}/{max_attempts})')
                if len(extra):
                    # obstacles seen earlier on this leg close the way: they may have
                    # been seen from a wrong pose or moved away, so forget them
                    extra = np.zeros((0, 2))
                    self.recover_pose()
                    continue
                if attempts >= 3:
                    return False
                if self.recover_pose():
                    continue
                # back off a little (maybe the robot is inside the inflation)
                self.send(-0.15, 0.0)
                time.sleep(1.0)
                self.stop()
                continue
            self.publish_path(path)
            res = self.follow(path, replan_period=replan_period,
                              timeout=max(5.0, deadline - time.monotonic()))
            if res == 'reached':
                if final_yaw is not None:
                    self.turn_to(final_yaw)
                return True
            if res == 'replan':
                continue
            attempts += 1
            if res == 'blocked':
                # First check the pose: with a pose that is off sideways the real
                # walls land on free floor of the map and look like obstacles.
                if recoveries < 4 and self.recover_pose():
                    recoveries += 1
                    attempts -= 1               # a fixed pose is a fresh try
                    extra = np.zeros((0, 2))    # seen from the wrong pose
                    self.get_logger().info('Path blocked: the pose was off and is '
                                           'corrected from the lidar, replanning')
                else:
                    pts = self.new_obstacles(self.scan_points_world(2.5))
                    if len(pts):
                        extra = np.vstack([extra, pts]) if len(extra) else pts
                        self.get_logger().info('Path blocked: replanning around the '
                                               'obstacle')
                    else:
                        self.get_logger().info('Too close to a mapped wall: replanning')
                self.send(-0.15, 0.0)
                time.sleep(0.8)
                self.stop()
        self.stop()
        return False


def spin_in_background(node, threads=4):
    ex = MultiThreadedExecutor(num_threads=threads)
    ex.add_node(node)
    th = threading.Thread(target=ex.spin, daemon=True)
    th.start()
    return ex, th


# ========================================================== the mapper
class ArucoSlamMapper(ArucoRobotBase):
    LIVE_SCAN_MATCHING = False  # the mapper draws with gyro + wheels + markers only
    ANGULAR_SPEED = 0.45        # slower turns while mapping: sharper scans and marker views
    # While mapping the heading comes from the gyro and is trusted strongly: the
    # Gazebo gyro drifts well under 1 deg over a whole run, while a marker
    # sighting (estimated marker position, camera delay) can be off by degrees.
    # Markers then mostly correct position; they can no longer turn the map.
    GYRO_NOISE = 0.0003
    GYRO_ALPHA = (0.005, 0.0002)

    def __init__(self):
        super().__init__('aruco_slam_mapper')
        p = self.declare_parameter
        p('initial_pose', [0.0, 0.0, 0.0], ParameterDescriptor(dynamic_typing=True))
        p('output_dir', '~/ros2_jazzy_ws/maps/aruco_slam_map')
        p('explore', True)
        p('max_duration', 3600.0)          # sim seconds
        p('map_resolution', 0.1)
        p('map_size', 160.0)
        p('laser_max_range', 15.0)
        p('visual_range', 6.0)             # wall counts as seen within this range
        p('view_distance', [2.5, 4.0])
        p('delivery_standoff', 2.3)        # delivery point distance in front of marker
        p('return_home', True)
        p('autosave_period', 60.0)
        # optional: optimize the whole trajectory at the end and write
        # map_corrected.* next to the live map (the live map is never overwritten)
        p('post_correction', False)
        p('save_scans', True)              # scans.npz for re-processing (correct_map.py)
        g = self.gp
        x0 = tuple(float(v) for v in g('initial_pose'))
        self.start_pose = x0
        self.ekf = EkfSlam(pose=x0)
        self.grid = OccupancyGrid2D(g('map_resolution'), g('map_size'), center=x0[:2])
        self.out_dir = os.path.expanduser(g('output_dir'))
        os.makedirs(self.out_dir, exist_ok=True)
        self.obs_log = []          # rows for observations.csv
        self.traj = []             # (t, x, y, yaw, odom x y yaw, dead-reckoning x y yaw)
        self.scan_log = []         # (lidar end points in base_link, hit mask) per traj row
        self._last_map_pose = None
        self._t0 = None
        self.create_timer(2.0, self._map_timer)
        self.get_logger().info(
            f'ArUco SLAM mapper: start pose {x0}, {len(self.marker_info)} markers '
            f'in config, output -> {self.out_dir}')

    # ---------------------------------------------------- sensor hooks
    def on_observations(self, stamp, obs, pose, odom):
        t = stamp.sec + stamp.nanosec * 1e-9
        for o in obs:
            self.obs_log.append([f'{t:.3f}', o.id, self.marker_info.get(o.id, {}).get('name', ''),
                                 f'{o.distance_3d:.3f}', f'{o.range:.3f}',
                                 f'{math.degrees(o.bearing):.2f}',
                                 f'{math.degrees(o.facing):.2f}', f'{o.pixels:.1f}',
                                 f'{pose[0]:.3f}', f'{pose[1]:.3f}',
                                 f'{math.degrees(pose[2]):.2f}',
                                 f'{odom[0]:.3f}', f'{odom[1]:.3f}',
                                 f'{math.degrees(odom[2]):.2f}',
                                 f'{self.dr_pose[0]:.4f}', f'{self.dr_pose[1]:.4f}',
                                 f'{math.degrees(self.dr_pose[2]):.3f}'])
            if o.id not in self.ekf.n_obs or self.ekf.n_obs[o.id] == 1:
                info = self.marker_info.get(o.id, {})
                self.get_logger().info(
                    f'New marker {o.id} {info.get("name", "")} at {o.range:.2f} m '
                    f'(bearing {math.degrees(o.bearing):.0f} deg)')

    def on_scan(self, stamp, pose):
        pose, M = self.pose_at(stamp)            # the pose when the scan was taken
        last = self._last_map_pose
        if last is not None and math.hypot(pose[0] - last[0], pose[1] - last[1]) < 0.08 \
                and abs(wrap(pose[2] - last[2])) < 0.05:
            return
        if self.matcher is not None and (self.grid.logodds > 0.6).sum() > 300:
            self.apply_scan_match(self.matcher.field(self.grid, pose, half=20.0))
            pose, M = self.pose_at(stamp)
        self._last_map_pose = pose
        c, s = math.cos(pose[2]), math.sin(pose[2])
        use = self.scan_use
        pts = self.scan_base[use]
        valid = self.scan_valid[use]
        rng = np.hypot(pts[:, 0] - self.scan_origin_base[0], pts[:, 1] - self.scan_origin_base[1])
        rmax = self.gp('laser_max_range')
        # shorten no-return and far beams to rmax (free space only)
        scale = np.where(rng > rmax, rmax / np.maximum(rng, 1e-6), 1.0)
        valid &= rng <= rmax
        ob = self.scan_origin_base
        pb = ob + (pts - ob) * scale[:, None]
        world = np.stack([pose[0] + c * pb[:, 0] - s * pb[:, 1],
                          pose[1] + s * pb[:, 0] + c * pb[:, 1]], 1)
        origin = (pose[0] + c * ob[0] - s * ob[1], pose[1] + s * ob[0] + c * ob[1])
        if self.grid.ensure_contains(world.min(axis=0), world.max(axis=0)):
            h, w = self.grid.shape
            self.get_logger().info(f'Map grown to {w * self.grid.res:.0f} x '
                                   f'{h * self.grid.res:.0f} m')
        self.grid.update_scan(origin, world, valid)
        self.grid.clear_disk(pose[:2], 0.3)              # the robot stands here: free
        # visual coverage: wall points inside the camera FOV and close enough
        cam = self.gp('camera_offset')
        bear = np.arctan2(pts[:, 1] - cam[1], pts[:, 0] - cam[0])
        dist = np.hypot(pts[:, 0] - cam[0], pts[:, 1] - cam[1])
        fresh = time.monotonic() - self.last_obs_wall < 1.0
        sel = valid & (np.abs(bear) < self.cam_hfov / 2.0 - 0.05) & \
            (dist < self.gp('visual_range'))
        if fresh and sel.any():
            self.grid.mark_seen(world[sel], radius_cells=1)
        t = stamp.sec + stamp.nanosec * 1e-9
        o, dr = self.odom_at(t) if self.gp('sync_sensors') else (self.odom_pose, self.dr_pose)
        self.traj.append((t, pose[0], pose[1], pose[2], o[0], o[1], o[2]) + tuple(dr))
        if self.gp('save_scans'):          # raw data for correct_map.py
            self.scan_log.append((pb[::2].astype(np.float16), valid[::2].copy()))

    def landmark_positions(self):
        with self.lock:
            return {k: v[:2] for k, v in self.ekf.landmarks().items()}

    def nav_grid(self, extra_obstacles=None, unknown_blocked=True):
        with self.lock:
            grid_copy = self._grid_snapshot()
        return PlanningGrid(grid_copy, robot_radius=self.gp('robot_radius'),
                            unknown_blocked=unknown_blocked,
                            extra_obstacles=extra_obstacles)

    def _grid_snapshot(self):
        g = OccupancyGrid2D.__new__(OccupancyGrid2D)
        g.res, g.origin = self.grid.res, self.grid.origin
        g.logodds = self.grid.logodds.copy()
        g.seen = self.grid.seen.copy()
        return g

    def _map_timer(self):
        with self.lock:
            msg = self.grid.to_msg(self.get_clock().now().to_msg(), self.gp('map_frame'))
        self.map_pub.publish(msg)

    # ----------------------------------------------------------- saving
    def save(self, final=False):
        with self.lock:
            grid = self._grid_snapshot()
            lms = self.ekf.landmarks()
            n_obs = dict(self.ekf.n_obs)
            facing = {mid: self.facing.yaw(mid) for mid in lms}
            obs_rows = list(self.obs_log)
            traj = list(self.traj)
            scans = list(self.scan_log)
            pose = self.ekf.pose()
        d = self.out_dir
        if scans:
            lens = np.array([len(sc[0]) for sc in scans])
            np.savez_compressed(
                os.path.join(d, 'scans.npz'),
                traj=np.array(traj[:len(scans)], np.float64),   # t, slam xyyaw, odom xyyaw, dr xyyaw
                points=np.concatenate([sc[0] for sc in scans]),
                hit=np.concatenate([sc[1] for sc in scans]),
                offsets=np.concatenate([[0], np.cumsum(lens)]),
                laser_origin=np.asarray(self.scan_origin_base, np.float64),
                start_pose=np.asarray(self.start_pose, np.float64))
        map_yaml = grid.save(d, 'map')
        standoff = self.gp('delivery_standoff')
        markers, delivery = [], {}
        for mid in sorted(lms):
            x, y, sig = lms[mid]
            info = self.marker_info.get(mid, {})
            yaw = facing.get(mid)
            entry = {'id': int(mid), 'name': info.get('name', f'marker_{mid}'),
                     'kind': info.get('kind', 'unknown'), 'room': info.get('room'),
                     'size': self.observer.size_of(mid),
                     'x': round(x, 3), 'y': round(y, 3),
                     'yaw': round(yaw, 4) if yaw is not None else None,
                     'sigma_xy': round(sig, 3), 'observations': int(n_obs.get(mid, 0))}
            if 'standoff' in info:               # per-marker standoff (e.g. tables)
                entry['standoff'] = float(info['standoff'])
            markers.append(entry)
            if info.get('kind') == 'delivery' and yaw is not None:
                so = entry.get('standoff', standoff)
                delivery[entry['name']] = {
                    'x': round(x + so * math.cos(yaw), 3),
                    'y': round(y + so * math.sin(yaw), 3),
                    'yaw': round(wrap(yaw + math.pi), 4),      # face the marker
                    'marker_id': int(mid)}
        delivery['home'] = {'x': round(self.start_pose[0], 3), 'y': round(self.start_pose[1], 3),
                            'yaw': round(self.start_pose[2], 4), 'marker_id': None}
        doc = {'frame': 'map', 'created': datetime.now().isoformat(timespec='seconds'),
               'dictionary': 'DICT_4X4_50', 'occupancy_map': os.path.basename(map_yaml),
               'start_pose': {'x': self.start_pose[0], 'y': self.start_pose[1],
                              'yaw': self.start_pose[2]},
               'delivery_standoff': standoff,
               'markers': markers, 'delivery_points': delivery}
        with open(os.path.join(d, 'aruco_landmarks.yaml'), 'w') as f:
            f.write('# ArUco landmark map written by aruco_slam_mapper.py\n'
                    '# x, y in metres (map frame); yaw = direction the marker faces.\n'
                    '# delivery_points: where the robot stops to deliver (edit freely).\n')
            yaml.safe_dump(doc, f, sort_keys=False)
        with open(os.path.join(d, 'observations.csv'), 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['t', 'marker_id', 'name', 'distance_3d_m', 'range_2d_m',
                        'bearing_deg', 'marker_facing_deg', 'pixels',
                        'slam_x', 'slam_y', 'slam_yaw_deg', 'odom_x', 'odom_y', 'odom_yaw_deg',
                        'dr_x', 'dr_y', 'dr_yaw_deg'])
            w.writerows(obs_rows)
        with open(os.path.join(d, 'trajectory.csv'), 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['t', 'slam_x', 'slam_y', 'slam_yaw', 'odom_x', 'odom_y', 'odom_yaw',
                        'dr_x', 'dr_y', 'dr_yaw'])
            w.writerows([[f'{v:.4f}' for v in row] for row in traj])
        self._save_preview(grid, markers, delivery, traj, pose)
        if final:
            self._report(markers, grid)
            if self.gp('post_correction') and scans:
                self.get_logger().info('Correcting the whole trajectory (pose graph with markers '
                                       'and lidar loop matches)... this takes a minute.')
                try:
                    try:
                        from indoor_delivery_project.map_optimizer import optimize_map_dir
                    except ImportError:
                        from map_optimizer import optimize_map_dir
                    optimize_map_dir(d, log=self.get_logger().info)
                except Exception as exc:  # noqa: BLE001 - the online map is already saved
                    self.get_logger().error(f'Trajectory correction failed ({exc}); the online '
                                            f'map in {d} is kept. Retry: ros2 run '
                                            f'indoor_delivery_project optimize_map {d}')
        return d

    def _save_preview(self, grid, markers, delivery, traj, pose):
        r0, r1, c0, c1 = grid.known_bbox()
        t = grid.ternary()[r0:r1, c0:c1]
        img = np.full(t.shape + (3,), 160, np.uint8)
        img[t == 0] = (255, 255, 255)
        img[t == 100] = (0, 0, 0)
        seen = grid.seen[r0:r1, c0:c1] & (t == 100)
        img[seen] = (0, 140, 0)
        scale = max(1, int(round(1200 / max(t.shape))))
        img = cv2.resize(img, (t.shape[1] * scale, t.shape[0] * scale),
                         interpolation=cv2.INTER_NEAREST)

        def px(x, y):
            c = (x - grid.origin[0]) / grid.res - c0
            r = (y - grid.origin[1]) / grid.res - r0
            return int(c * scale), int(r * scale)

        for i in range(1, len(traj)):
            cv2.line(img, px(*traj[i - 1][1:3]), px(*traj[i][1:3]), (255, 120, 0), 1)
        for m in markers:
            cv2.circle(img, px(m['x'], m['y']), 5, (0, 0, 255), -1)
        for name, dp in delivery.items():
            cv2.drawMarker(img, px(dp['x'], dp['y']), (0, 160, 255), cv2.MARKER_STAR, 14, 2)
        img = np.ascontiguousarray(np.flipud(img))
        H = img.shape[0]
        for m in markers:
            x, y = px(m['x'], m['y'])
            cv2.putText(img, str(m['id']), (x + 6, H - y - 6), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (0, 0, 200), 1)
        cv2.imwrite(os.path.join(self.out_dir, 'map_preview.png'), img)

    def _report(self, markers, grid):
        cov = coverage_stats(grid)
        lines = [f'Map saved to {self.out_dir}',
                 f'  free area {cov["free_area_m2"]:.0f} m2, walls seen by camera '
                 f'{cov["wall_seen_pct"]:.0f}%, {len(markers)} markers, '
                 f'{len(self.obs_log)} marker observations']
        truth = {mid: i['pose'] for mid, i in self.marker_info.items() if 'pose' in i}
        aligned = self.start_pose != (0.0, 0.0, 0.0)
        for m in markers:
            line = (f'  id {m["id"]:>3} {m["name"]:<24} x={m["x"]:8.2f} y={m["y"]:8.2f} '
                    f'sigma={m["sigma_xy"]:.2f} m  n={m["observations"]}')
            if aligned and m['id'] in truth:
                tp = truth[m['id']]
                line += f'  error vs world {math.hypot(m["x"] - tp["x"], m["y"] - tp["y"]):.2f} m'
            lines.append(line)
        missing = sorted(set(self.marker_info) - {m['id'] for m in markers})
        if missing:
            lines.append(f'  not detected: {missing}')
        self.get_logger().info('\n'.join(lines))

    # ---------------------------------------------------------- mission
    def run(self):
        g = self.gp
        if not self.wait_for_sensors():
            return
        self._t0 = self.sim_now()
        last_save = time.monotonic()
        self.get_logger().info('Sensors ready. Initial 360 deg scan...')
        self.rotate(2 * math.pi + 0.3)
        if not g('explore'):
            self.get_logger().info('explore:=false - drive the robot yourself; '
                                   'Ctrl+C saves the map.')
            while self.sim_now() - self._t0 < g('max_duration'):
                time.sleep(1.0)
                if time.monotonic() - last_save > g('autosave_period'):
                    self.save()
                    last_save = time.monotonic()
            return
        blacklist = {'points': [], 'keys': set()}
        failures = {}
        n_goals = 0
        while self.sim_now() - self._t0 < g('max_duration'):
            if time.monotonic() - last_save > g('autosave_period'):
                self.save()
                last_save = time.monotonic()
            pose = self.pose()
            with self.lock:
                grid = self._grid_snapshot()
            plan = PlanningGrid(grid, robot_radius=g('robot_radius'))
            target = choose_exploration_target(grid, plan, pose, blacklist,
                                               view_range=tuple(g('view_distance')))
            if target is None:
                self.get_logger().info('Exploration complete: no frontiers and no '
                                       'unseen walls left.')
                break
            n_goals += 1
            cov = coverage_stats(grid)
            self.get_logger().info(
                f'Goal {n_goals}: {target["kind"]} at ({target["goal"][0]:.1f}, '
                f'{target["goal"][1]:.1f}), {target["cost"]:.1f} m away | walls seen '
                f'{cov["wall_seen_pct"]:.0f}%, markers {len(self.ekf.index)}')
            ok = self.navigate_to(target['goal'], replan_period=8.0, max_attempts=4,
                                  timeout=240.0)
            if ok and target['look_at'] is not None:
                lx, ly = target['look_at']
                p = self.pose()
                self.turn_to(math.atan2(ly - p[1], lx - p[0]))
                time.sleep(0.8)                      # let the camera look
            if target['kind'] == 'view':
                blacklist['keys'].add(target['key'])  # visited once is enough
            else:
                blacklist['points'].append(target['goal'])
            if not ok:
                k = (round(target['goal'][0]), round(target['goal'][1]))
                failures[k] = failures.get(k, 0) + 1
                if failures[k] >= 2 or target['kind'] == 'frontier':
                    blacklist['points'].append(target['goal'])
        if g('return_home'):
            self.get_logger().info('Returning to the start pose...')
            self.navigate_to(self.start_pose[:2], final_yaw=self.start_pose[2],
                             max_attempts=4, timeout=600.0)


def main(args=None):
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = ArucoSlamMapper()
    executor, _ = spin_in_background(node)
    try:
        node.run()
    except KeyboardInterrupt:
        node.get_logger().info('Interrupted: stopping and saving the map...')
    finally:
        try:
            node.stop()
        except Exception:  # noqa: BLE001
            pass
        node.save(final=True)
        executor.shutdown(timeout_sec=1.0)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
