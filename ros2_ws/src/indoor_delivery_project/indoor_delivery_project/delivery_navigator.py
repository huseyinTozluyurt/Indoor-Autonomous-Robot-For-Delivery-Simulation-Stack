#!/usr/bin/env python3
"""Point-to-point delivery navigation on the map made by aruco_slam_mapper.py.

Loads the saved map directory (map.yaml/pgm + aruco_landmarks.yaml) and then:
  * localizes with an EKF: wheel odometry for prediction, every ArUco marker
    in the landmark map as a known beacon for correction;
  * plans with Dijkstra on a clearance map of the saved grid (distance to
    the nearest wall per cell): the shortest path that keeps to the middle of
    corridors and doors. It plans again from the current pose every
    replan_period seconds, moves a goal that is too close to a wall or table
    to the nearest free spot, forgets lidar obstacles after obstacle_memory
    seconds or when the pose is corrected, and relaxes the safety margin
    step by step instead of giving up when no path is found;
  * multipoint delivery: start at A, visit stops x, y, z in the order with the
    shortest total driving distance (all-pairs Dijkstra + exact Held-Karp),
    finish at B;
  * drives the path with pure pursuit, stops for obstacles the lidar sees and
    replans around them;
  * at each delivery point turns to face the delivery marker and checks that
    it sees the right marker ID before reporting "delivered".

Run (simulation running, robot at the same start pose as during mapping):

    # deliver a fixed route and come back home
    ros2 run indoor_delivery_project delivery_navigator --ros-args \
        -p map_dir:=~/ros2_jazzy_ws/maps/campus \
        -p deliveries:="['left_delivery_point_1', 'right_delivery_point_3', 'home']"

    # multipoint: start at home, deliver to 3 points in the shortest order,
    # finish at right_delivery_point_4
    ros2 run indoor_delivery_project delivery_navigator --ros-args \
        -p map_dir:=~/ros2_jazzy_ws/maps/campus -p route_start:=home \
        -p stops:="['right_delivery_point_1', 'left_delivery_point_4', 'right_delivery_point_3']" \
        -p route_end:=right_delivery_point_4

    # interactive: type a delivery point name or number at the prompt, or
    #   route home left_delivery_point_2 right_delivery_point_1 3 home
    ros2 run indoor_delivery_project delivery_navigator --ros-args \
        -p map_dir:=~/ros2_jazzy_ws/maps/campus

    # from another terminal / program while it runs
    ros2 topic pub --once /delivery_navigator/goal std_msgs/msg/String \
        "{data: right_delivery_point_2}"

  initial_pose:=home (default) starts at the mapping start pose; 'auto' finds
  the pose from the closest marker (turns in place until it sees one); or give
  "[x, y, yaw]".
"""
import math
import os
import queue
import sys
import threading

import cv2
import numpy as np
import rclpy
import yaml
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.signals import SignalHandlerOptions
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
from std_msgs.msg import String

try:
    from indoor_delivery_project.aruco_slam_mapper import (
        ArucoRobotBase, EkfSlam, OccupancyGrid2D, PlanningGrid,
        MissionAborted, spin_in_background, time, wrap)
except ImportError:                         # run as a plain script
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from aruco_slam_mapper import (  # noqa: E402
        ArucoRobotBase, EkfSlam, OccupancyGrid2D, PlanningGrid,
        MissionAborted, spin_in_background, time, wrap)


# ================================================== robust Dijkstra planner
class ClearancePlanner(PlanningGrid):
    """Dijkstra on a clearance map of the saved occupancy grid.

    Every 0.2 m cell knows its distance to the nearest wall (measured on the
    full 0.1 m map, so thin or slightly doubled walls do not eat whole
    corridor cells). A cell is drivable when that clearance is at least the
    robot radius; the step cost grows as the clearance gets smaller, so the
    shortest path keeps to the middle of corridors and doors. The search
    itself (Dijkstra over the 8-connected grid, parents for path extraction)
    is PlanningGrid._search.
    """

    def __init__(self, grid, resolution=0.2, robot_radius=0.45, comfort=1.0,
                 weight=4.0, unknown_blocked=True, extra_obstacles=None, base=None):
        if base is None:
            base = self.base_layers(grid, resolution)
        self.res, self.origin, self.shape = base['res'], base['origin'], base['shape']
        clear = base['clear']
        if extra_obstacles is not None and len(extra_obstacles):
            h, w = self.shape
            rr, cc = self.to_cell(extra_obstacles)
            ok = (rr >= 0) & (rr < h) & (cc >= 0) & (cc < w)
            mask = np.zeros((h, w), np.uint8)
            mask[rr[ok], cc[ok]] = 1
            d = cv2.distanceTransform(1 - mask, cv2.DIST_L2, 5) * self.res
            clear = np.minimum(clear, np.maximum(d - 0.5 * self.res, 0.0))
        self.clear = clear
        self.occ = base['occ']
        self.unknown = base['unknown']
        self.free = ~self.occ & ~self.unknown
        self.robot_radius = robot_radius
        self.blocked = clear < robot_radius
        if unknown_blocked:
            self.blocked |= self.unknown
        span = max(comfort - robot_radius, 0.1)
        t = (comfort - np.clip(clear, robot_radius, comfort)) / span
        self.cost = 1.0 + weight * t ** 2
        self.cost[self.blocked] = np.inf

    @staticmethod
    def base_layers(grid, resolution=0.2):
        """Clearance (m), occupied and unknown masks on the coarse grid.
        Computed once per map; everything else is cheap."""
        k = max(1, int(round(resolution / grid.res)))
        tern = grid.ternary()
        H, W = tern.shape
        H2, W2 = (H // k) * k, (W // k) * k
        tern = tern[:H2, :W2]
        occ_f = tern == 100
        dist = cv2.distanceTransform((~occ_f).astype(np.uint8), cv2.DIST_L2, 5) * grid.res
        h, w = H2 // k, W2 // k
        clear = dist.reshape(h, k, w, k).min(axis=(1, 3))     # worst point of the cell
        blk = tern.reshape(h, k, w, k)
        occ = (blk == 100).any(axis=(1, 3))
        unknown = ~occ & ((blk == 0).sum(axis=(1, 3)) * 2 < k * k)
        return dict(res=grid.res * k, origin=tuple(grid.origin), shape=(h, w),
                    clear=clear.astype(np.float64), occ=occ, unknown=unknown)

    def reachable_near(self, start_cell, goal_xy, max_dist=1.5, min_clear=None):
        """Dijkstra from start_cell; then the reachable cell closest to goal_xy
        (within max_dist), preferring cells with at least min_clear clearance.
        Returns (cell, g, parent) or (None, g, parent)."""
        g, parent, _ = self._search(start_cell)
        G = np.array(g).reshape(self.shape)
        r, c = self.to_cell(goal_xy)
        rad = int(math.ceil(max_dist / self.res))
        h, w = self.shape
        r0, r1 = max(int(r) - rad, 0), min(int(r) + rad + 1, h)
        c0, c1 = max(int(c) - rad, 0), min(int(c) + rad + 1, w)
        if r0 >= r1 or c0 >= c1:
            return None, g, parent
        sub = np.isfinite(G[r0:r1, c0:c1])
        rr, cc = np.nonzero(sub)
        if len(rr) == 0:
            return None, g, parent
        rr, cc = rr + r0, cc + c0
        xs, ys = self.to_world(rr, cc)
        d = np.hypot(xs - goal_xy[0], ys - goal_xy[1])
        ok = d <= max_dist
        if min_clear is not None and (ok & (self.clear[rr, cc] >= min_clear)).any():
            ok &= self.clear[rr, cc] >= min_clear
        if not ok.any():
            return None, g, parent
        i = int(np.argmin(np.where(ok, d, np.inf)))
        return (int(rr[i]), int(cc[i])), g, parent

    def plan(self, start_xy, goal_xy, goal_clear=None, snap=1.5):
        """Shortest path start -> (goal, or the closest reachable point to it).
        Returns (path, goal_used) or (None, None)."""
        s = self.nearest_open(start_xy, snap)
        if s is None:
            return None, None
        cell, g, parent = self.reachable_near(s, goal_xy, snap, goal_clear)
        if cell is None:
            return None, None
        gi = cell[0] * self.shape[1] + cell[1]
        path = self._trace(parent, gi, goal_xy, 0.0)   # ends on the cell centre
        gx, gy = self.to_world(cell[0], cell[1])
        exact = math.hypot(gx - goal_xy[0], gy - goal_xy[1]) <= self.res and \
            not self.blocked[cell]
        goal_used = (float(goal_xy[0]), float(goal_xy[1])) if exact else (float(gx), float(gy))
        path[-1] = goal_used
        if math.hypot(path[0][0] - start_xy[0], path[0][1] - start_xy[1]) > 0.05:
            path.insert(0, (float(start_xy[0]), float(start_xy[1])))
        return path, goal_used


def load_landmark_map(map_dir):
    map_dir = os.path.expanduser(map_dir)
    with open(os.path.join(map_dir, 'aruco_landmarks.yaml')) as f:
        doc = yaml.safe_load(f)
    grid_yaml = os.path.join(map_dir, doc.get('occupancy_map', 'map.yaml'))
    return doc, OccupancyGrid2D.load(grid_yaml)


class DeliveryNavigator(ArucoRobotBase):

    def __init__(self):
        super().__init__('delivery_navigator')
        p = self.declare_parameter
        p('map_dir', '~/ros2_jazzy_ws/maps/aruco_slam_map')
        p('initial_pose', 'home', ParameterDescriptor(dynamic_typing=True))
        p('deliveries', [''], ParameterDescriptor(dynamic_typing=True))
        p('dwell_time', 3.0)               # seconds "unloading" at each point
        p('return_home', True)             # after the deliveries list
        p('interactive', True)             # read goals from the terminal
        # multipoint delivery: start A -> stops (best order) -> end B
        p('route_start', '')               # '' = where the robot is now
        p('stops', [''], ParameterDescriptor(dynamic_typing=True))
        p('route_end', '')                 # '' = back to route_start
        p('optimize_order', True)          # False = visit stops in the given order
        p('replan_period', 15.0)           # s: plan again from the current pose
        p('obstacle_memory', 30.0)         # s: how long a seen obstacle stays in the plan
        g = self.gp
        self.doc, self.static_grid = load_landmark_map(g('map_dir'))
        self.points = dict(self.doc.get('delivery_points') or {})
        self.lm = {int(m['id']): m for m in self.doc.get('markers', [])}
        # marker names and sizes come from the map itself, so no markers_file
        # is needed (a wrong size would give wrong ranges and a wrong pose)
        for mid, m in self.lm.items():
            info = dict(self.marker_info.get(mid, {}))
            info.update({k: m[k] for k in ('name', 'kind', 'room', 'size') if m.get(k) is not None})
            self.marker_info[mid] = info
        self.observer.markers = self.marker_info
        # markers added by hand with localize: false only confirm a delivery;
        # they are not used as beacons (their position is not measured)
        fixed = {mid: (m['x'], m['y']) for mid, m in self.lm.items()
                 if m.get('localize', True)}
        sp = self.doc.get('start_pose', {'x': 0.0, 'y': 0.0, 'yaw': 0.0})
        self.home = (float(sp['x']), float(sp['y']), float(sp['yaw']))
        self.ekf = EkfSlam(pose=self.home, pose_sigma=(0.05, 0.05, 0.03),
                           fixed_landmarks=fixed, fixed_sigma=0.08)
        self._plan_base = None             # clearance map, built on first use
        self._plan_cache = {}
        self.match_field = self.matcher.field(self.static_grid) if self.matcher else None
        # distance to the nearest mapped wall (to tell new obstacles from walls)
        occ = self.static_grid.logodds > 0.6
        self.wall_dist = cv2.distanceTransform((~occ).astype(np.uint8), cv2.DIST_L2, 3) * \
            self.static_grid.res
        # soft "on a wall" score per map cell for the pose checks (sigma 0.15 m)
        self.wall_lik = np.exp(-0.5 * (self.wall_dist / 0.15) ** 2).astype(np.float32)
        self.known = self.static_grid.ternary() >= 0
        self._recover_lock = threading.Lock()
        self._bad_fit_since = None
        self._last_fit_check = 0.0
        self._last_auto_recover = 0.0
        self.last_fit = 1.0
        self._last_match = 0.0
        self.goals = queue.Queue()
        self.status_pub = self.create_publisher(String, '~/status', 10)
        self.route_pub = self.create_publisher(Path, '~/route', 1)
        self.create_subscription(String, '~/goal', lambda m: self.goals.put(m.data.strip()), 10)
        self.create_timer(5.0, self._publish_map)
        self.get_logger().info(
            f'Loaded {len(self.lm)} landmarks and {len(self.points)} delivery points '
            f'from {os.path.expanduser(g("map_dir"))}')

    # ------------------------------------------------------------ maps
    def landmark_positions(self):
        return {mid: (m['x'], m['y']) for mid, m in self.lm.items()}

    def planner(self, level=0, extra_obstacles=None):
        """Dijkstra planner on the saved map. level 0: full robot radius;
        1: 0.1 m less (tight doors, slightly thick walls on the map);
        2: smallest safe radius and unknown cells allowed (last resort)."""
        if self._plan_base is None:
            self._plan_base = ClearancePlanner.base_layers(self.static_grid)
        r = self.gp('robot_radius')
        radius = [r, max(r - 0.1, 0.33), max(r - 0.15, 0.3)][level]
        unknown_blocked = level < 2
        if extra_obstacles is None or len(extra_obstacles) == 0:
            if level not in self._plan_cache:
                self._plan_cache[level] = ClearancePlanner(
                    self.static_grid, robot_radius=radius, unknown_blocked=unknown_blocked,
                    base=self._plan_base)
            return self._plan_cache[level]
        return ClearancePlanner(self.static_grid, robot_radius=radius,
                                unknown_blocked=unknown_blocked,
                                extra_obstacles=extra_obstacles, base=self._plan_base)

    def nav_grid(self, extra_obstacles=None, unknown_blocked=True):
        return self.planner(0 if unknown_blocked else 2, extra_obstacles)

    def plan_path(self, goal, obstacles=None):
        """Shortest path from the robot to goal, relaxing step by step when the
        normal plan finds nothing. Returns (path, goal_used, level)."""
        pose = self.pose()
        goal_clear = self.gp('robot_radius') + self.gp('stop_distance') * 0.5
        tries = []
        if obstacles is not None and len(obstacles):
            tries += [(0, obstacles), (1, obstacles)]
        tries += [(0, None), (1, None), (2, None)]
        for level, obst in tries:
            path, goal_used = self.planner(level, obst).plan(pose[:2], goal, goal_clear)
            if path is not None:
                return path, goal_used, level, obst is not None
        return None, None, None, False

    def navigate_to(self, goal, final_yaw=None, unknown_blocked=True, max_attempts=8,
                    replan_period=None, timeout=None):
        """Robust go-to on the saved map (Dijkstra on the clearance map).

        * plans from where the robot is now, every replan_period seconds too,
          so a pose correction or a detour never leaves it on a stale path;
        * a goal that lies too close to a wall or table is replaced by the
          closest reachable spot with room around it;
        * obstacles seen by the lidar are remembered for obstacle_memory
          seconds only and dropped when the pose is corrected (they were then
          walls seen from a wrong pose), so an old detour can never block a
          corridor the robot drove before;
        * when nothing is found it relaxes: forget obstacles, smaller safety
          radius, then unknown cells allowed;
        * 'blocked' close to the goal counts as arrived.
        Returns True when the goal was reached."""
        replan_period = replan_period or self.gp('replan_period')
        memory = self.gp('obstacle_memory')
        obstacles = []                       # (time, points)
        deadline = time.monotonic() + (timeout or 1e9)
        attempts = recoveries = 0
        last_level = 0
        while attempts < max_attempts and time.monotonic() < deadline:
            if self.abort_event.is_set():
                raise MissionAborted()
            now = time.monotonic()
            obstacles = [(t, p) for t, p in obstacles if now - t < memory]
            obst = np.vstack([p for _, p in obstacles]) if obstacles else None
            path, goal_used, level, used_obst = self.plan_path(goal, obst)
            if path is None:
                attempts += 1
                self.say(f'No path to ({goal[0]:.1f}, {goal[1]:.1f}) from '
                         f'({self.pose()[0]:.1f}, {self.pose()[1]:.1f}); checking the pose '
                         f'(attempt {attempts}/{max_attempts})')
                obstacles = []
                if not self.recover_pose():
                    self._back_off()
                continue
            if obst is not None and not used_obst:
                obstacles = []                 # they closed the way: forget them
            if level != last_level:
                self.say(['Planning with the normal safety margin again',
                          'Tight passage: planning with a smaller safety margin',
                          'Planning through unmapped cells (last resort)'][level])
                last_level = level
            if goal_used != (float(goal[0]), float(goal[1])):
                self.get_logger().info(
                    f'Goal ({goal[0]:.2f}, {goal[1]:.2f}) is too close to an obstacle: '
                    f'stopping at ({goal_used[0]:.2f}, {goal_used[1]:.2f}) instead',
                    throttle_duration_sec=30.0)
            self.publish_path(path)
            res = self.follow(path, replan_period=replan_period,
                              timeout=max(5.0, deadline - time.monotonic()))
            pose = self.pose()
            near = math.hypot(goal_used[0] - pose[0], goal_used[1] - pose[1])
            if res == 'reached' or (res == 'blocked' and near < 0.7):
                self.stop()
                self.last_goal_used = goal_used
                if final_yaw is not None:
                    self.turn_to(final_yaw)
                return True
            if res == 'replan':
                continue
            attempts += 1
            if res == 'blocked':
                pts = self.new_obstacles(self.scan_points_world(2.5))
                if recoveries < 4 and self.recover_pose(quiet=True):
                    recoveries += 1
                    attempts -= 1               # a fixed pose is a fresh try
                    obstacles = []              # seen from the wrong pose
                    self.say('Path blocked: the pose was off and is corrected from the '
                             'lidar, replanning')
                elif len(pts):
                    obstacles.append((time.monotonic(), pts))
                    self.say('Path blocked by an obstacle: replanning around it')
                else:
                    self.say('Too close to a mapped wall: backing off and replanning')
                self._back_off()
        self.stop()
        return False

    def _back_off(self, seconds=1.2):
        """Reverse a little (the lidar only looks forward, so slowly)."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.send(-0.12, 0.0)
            time.sleep(0.1)
        self.stop()

    def new_obstacles(self, pts_world):
        """Keep only scan points more than 0.35 m away from walls on the map."""
        if len(pts_world) == 0:
            return pts_world
        g = self.static_grid
        r, c = g.to_cell(pts_world)
        h, w = self.wall_dist.shape
        ok = (r >= 0) & (r < h) & (c >= 0) & (c < w)
        far = np.ones(len(pts_world), bool)
        far[ok] = self.wall_dist[r[ok], c[ok]] > 0.35
        return pts_world[far]

    def _local_points(self, pts_base, max_range=5.0, n=150):
        """Nearby lidar hits only: far walls of a slightly bent map would make a
        right pose look wrong."""
        if pts_base is None or len(pts_base) == 0:
            return np.zeros((0, 2))
        p = pts_base[np.hypot(pts_base[:, 0], pts_base[:, 1]) < max_range]
        if len(p) > n:
            p = p[np.linspace(0, len(p) - 1, n).astype(int)]
        return p

    def _fit_many(self, pts, xs, ys, th):
        """Mean wall score of pts for every (x, y) offset at heading th."""
        c, s = math.cos(th), math.sin(th)
        ox = c * pts[:, 0] - s * pts[:, 1]
        oy = s * pts[:, 0] + c * pts[:, 1]
        g = self.static_grid
        cc = np.floor((xs[:, None] + ox[None] - g.origin[0]) / g.res).astype(np.int64)
        rr = np.floor((ys[:, None] + oy[None] - g.origin[1]) / g.res).astype(np.int64)
        h, w = self.wall_lik.shape
        ok = (rr >= 0) & (rr < h) & (cc >= 0) & (cc < w)
        v = np.where(ok, self.wall_lik[np.clip(rr, 0, h - 1), np.clip(cc, 0, w - 1)], 0.0)
        return v.mean(axis=1)

    def scan_fit_pts(self, pose, p):
        return float(self._fit_many(p, np.array([pose[0]]), np.array([pose[1]]), pose[2])[0])

    def scan_fit(self, pose, pts_base):
        """How well the nearby lidar hits lie on mapped walls from `pose`
        (0..1; about 0.7-0.95 when the pose is right). It drops fast when the
        pose is off sideways, because the walls then land on free floor."""
        p = self._local_points(pts_base)
        if len(p) < 20:
            return 1.0
        return float(self._fit_many(p, np.array([pose[0]]), np.array([pose[1]]), pose[2])[0])

    def _search_pose(self, pose, p, rad_xy, step_xy, rad_th, step_th, tol=0.1):
        """Grid search around pose for where the nearby lidar hits fit the map.

        Returns (pose, fit). Only the directions the scan pins down are changed:
        in a corridor every shift along it fits about equally well, so the
        position along the corridor is kept and only the sideways offset (and
        heading) is corrected. If several separate places fit, nothing moves."""
        d = np.arange(-rad_xy, rad_xy + 1e-9, step_xy)
        dx, dy = [a.ravel() for a in np.meshgrid(d, d)]
        dths = np.arange(-rad_th, rad_th + 1e-9, step_th)
        fits = np.stack([self._fit_many(p, pose[0] + dx, pose[1] + dy, pose[2] + t)
                         for t in dths])                       # (T, M)
        top = float(fits.max())
        ti, mi = np.nonzero(fits >= top - tol)                 # near-best poses
        gx, gy, gt = dx[mi], dy[mi], dths[ti]
        mean = np.array([gx.mean(), gy.mean()])
        cov = np.cov(np.stack([gx, gy])) if len(gx) > 2 else np.eye(2) * step_xy ** 2
        vals, vecs = np.linalg.eigh(np.atleast_2d(cov))
        shift = np.zeros(2)
        for k in range(2):
            if math.sqrt(max(vals[k], 0.0)) < max(0.3, 2 * step_xy):   # well pinned
                shift += vecs[:, k] * float(vecs[:, k] @ mean)
        dth = float(gt.mean()) if gt.std() < 2.5 * step_th else 0.0
        q = (pose[0] + shift[0], pose[1] + shift[1], wrap(pose[2] + dth))
        return q, self.scan_fit_pts(q, p)

    def recover_pose(self, quiet=False):
        """Lidar search on the saved map around the estimate: +-1 m / +-17 deg,
        then +-2.5 m if that is not enough. True if the pose was corrected."""
        if not self._recover_lock.acquire(blocking=False):
            return False
        try:
            return self._recover_pose(quiet)
        finally:
            self._recover_lock.release()

    def _recover_pose(self, quiet):
        with self.lock:
            pts, ok = self.scan_base, self.scan_valid
            pose = self.ekf.pose()
        if pts is None:
            return False
        allp = pts[ok]
        p = self._local_points(allp)
        if len(p) < 30:
            return False
        before = self.scan_fit_pts(pose, p)
        gyro = time.monotonic() - self._imu_wall < 0.5
        th = 0.1 if gyro else 0.3                  # the gyro keeps the heading good
        new, fit = self._search_pose(pose, p, 1.0, 0.1, th, 0.02)
        if fit < 0.6:
            new2, fit2 = self._search_pose(pose, p, 2.5, 0.15, th, 0.04)
            if fit2 > fit + 0.05:
                new, fit = new2, fit2
                new3, fit3 = self._search_pose(new2, p, 0.3, 0.05, 0.04, 0.02)
                if fit3 >= fit:
                    new, fit = new3, fit3
        if fit < max(0.55, before + 0.2):
            if not quiet:
                self.say(f'Pose check: no better lidar match (fit {before:.0%})')
            return False
        moved = math.hypot(new[0] - pose[0], new[1] - pose[1])
        if moved < 0.1 and abs(wrap(new[2] - pose[2])) < 0.03:
            return False
        with self.lock:
            # the robot moved during the search: carry that motion over
            cur = self.ekf.pose()
            new = (new[0] + cur[0] - pose[0], new[1] + cur[1] - pose[1],
                   wrap(new[2] + cur[2] - pose[2]))
            self.ekf.set_pose(new, sigma=(0.1, 0.1, 0.03))
        self.say(f'Pose corrected by {moved:.2f} m / '
                 f'{math.degrees(wrap(new[2] - pose[2])):.1f} deg from the lidar '
                 f'(map fit {before:.0%} -> {fit:.0%})')
        return True

    def check_localization(self, now):
        """Called on every scan: if the scan stops fitting the map for 1 s
        (pose drifted or jumped sideways), search for the right pose."""
        if now - self._last_fit_check < 0.5:
            return
        self._last_fit_check = now
        with self.lock:
            pts, ok = self.scan_base, self.scan_valid
            pose = self.ekf.pose()
        if pts is None:
            return
        self.last_fit = fit = self.scan_fit(pose, pts[ok])
        if fit >= 0.3:
            self._bad_fit_since = None
            return
        self._bad_fit_since = self._bad_fit_since or now
        if now - self._bad_fit_since > 1.0 and now - self._last_auto_recover > 3.0:
            self._last_auto_recover = now
            if self.recover_pose(quiet=True):
                self._bad_fit_since = None

    def on_scan(self, stamp, pose):
        now = time.monotonic()
        if now - self._last_match >= 0.2:          # 5 Hz lidar localization
            self._last_match = now
            self.apply_scan_match(self.match_field)
        self.check_localization(now)

    def _publish_map(self):
        self.map_pub.publish(self.static_grid.to_msg(self.get_clock().now().to_msg(),
                                                     self.gp('map_frame'), crop=False))

    def say(self, text):
        self.get_logger().info(text)
        self.status_pub.publish(String(data=text))

    # ---------------------------------------------------- localization
    def set_initial_pose(self):
        ip = self.gp('initial_pose')
        if isinstance(ip, str) and ip.strip().lower() == 'auto':
            return self.relocalize()
        if isinstance(ip, str) and ip.strip().lower() not in ('', 'home'):
            name = ip.strip()
            if name in self.points:
                dp = self.points[name]
                pose = (float(dp['x']), float(dp['y']), float(dp['yaw']))
            else:
                pose = tuple(float(v) for v in yaml.safe_load(ip))
        elif not isinstance(ip, str) and len(ip) == 3:      # list / array.array
            pose = tuple(float(v) for v in ip)
        else:
            pose = self.home
        with self.lock:
            self.ekf.set_pose(pose, sigma=(0.1, 0.1, 0.05))
        self.say(f'Initial pose ({pose[0]:.2f}, {pose[1]:.2f}, {math.degrees(pose[2]):.0f} deg)')
        return True

    def relocalize(self, good_range=5.0):
        """Pose from one marker: its map position + facing and the observed
        range, bearing and facing give x, y and yaw of the robot. Turns in
        30 deg steps (a full circle at most) and uses the closest marker."""
        self.say('Relocalizing: turning until a known marker is in view...')
        samples = []                      # (observation, map marker, odom yaw)
        turned = 0.0
        while turned < 2 * math.pi:
            t_end = time.monotonic() + 1.0
            while time.monotonic() < t_end:
                with self.lock:
                    fresh = time.monotonic() - self.last_obs_wall < 0.3
                    obs = list(self.last_obs) if fresh else []
                    oyaw = self.odom_pose[2]
                for o in obs:
                    m = self.lm.get(o.id)
                    if m and m.get('yaw') is not None:
                        samples.append((o, m, oyaw))
                time.sleep(0.15)
            if samples and min(sm[0].range for sm in samples) < good_range:
                break
            self.rotate(math.radians(30))
            turned += math.radians(30)
        if not samples:
            self.get_logger().error('No known marker found; falling back to the home pose.')
            with self.lock:
                self.ekf.set_pose(self.home, sigma=(0.5, 0.5, 0.2))
            return False
        best_id = min(samples, key=lambda sm: sm[0].range)[0].id
        sel = [sm for sm in samples if sm[0].id == best_id]
        m = sel[0][1]
        with self.lock:
            oyaw_now = self.odom_pose[2]
        xs, ys, cs, ss = [], [], [], []
        for o, _, oyaw in sel:
            th = wrap(m['yaw'] - o.facing)
            c, s_ = math.cos(th), math.sin(th)
            xs.append(m['x'] - (c * o.bx - s_ * o.by))
            ys.append(m['y'] - (s_ * o.bx + c * o.by))
            th_now = th + wrap(oyaw_now - oyaw)        # turned since the sample
            cs.append(math.cos(th_now))
            ss.append(math.sin(th_now))
        rng = float(np.mean([o.range for o, _, _ in sel]))
        pose = (float(np.mean(xs)), float(np.mean(ys)), math.atan2(np.mean(ss), np.mean(cs)))
        sig = 0.1 + 0.05 * rng
        with self.lock:
            self.ekf.set_pose(pose, sigma=(sig, sig, 0.05 + 0.02 * rng))
        self.say(f'Relocalized from marker {best_id} at {rng:.1f} m: ({pose[0]:.2f}, '
                 f'{pose[1]:.2f}, {math.degrees(pose[2]):.0f} deg)')
        time.sleep(1.0)                    # let a few EKF updates refine it
        return True

    # -------------------------------------------------------- delivery
    def resolve(self, text):
        names = list(self.points)
        if text.isdigit() and 1 <= int(text) <= len(names):
            return names[int(text) - 1]
        if text in self.points:
            return text
        matches = [n for n in names if text.lower() in n.lower()]
        return matches[0] if len(matches) == 1 else None

    def deliver(self, name):
        dp = self.points[name]
        goal = (float(dp['x']), float(dp['y']))
        yaw = dp.get('yaw')
        pose = self.pose()
        self.say(f'Going to {name} ({goal[0]:.1f}, {goal[1]:.1f}), '
                 f'{math.hypot(goal[0] - pose[0], goal[1] - pose[1]):.1f} m away')
        t0 = self.sim_now()
        ok = self.navigate_to(goal, final_yaw=None if yaw is None else float(yaw))
        if not ok:
            self.say(f'Could not reach {name} yet: checking the pose and trying again')
            self.recover_pose()
            ok = self.navigate_to(goal, final_yaw=None if yaw is None else float(yaw))
        if not ok:
            self.say(f'FAILED to reach {name}')
            return False
        pose = self.pose()
        used = getattr(self, 'last_goal_used', goal)
        msg = (f'Arrived at {name} in {self.sim_now() - t0:.0f} s; pose error '
               f'{math.hypot(used[0] - pose[0], used[1] - pose[1]):.2f} m')
        if math.hypot(used[0] - goal[0], used[1] - goal[1]) > 0.2:
            msg += (f' (stopped {math.hypot(used[0] - goal[0], used[1] - goal[1]):.1f} m '
                    f'before the point: too close to a wall or table)')
        mid = dp.get('marker_id')
        if mid is not None:
            ids = set(dp.get('marker_ids') or []) | {mid}   # any marker of that table
            seen = None
            end = time.monotonic() + 2.0
            while time.monotonic() < end and seen is None:
                with self.lock:
                    seen = next((o for o in self.last_obs if o.id in ids), None)
                time.sleep(0.1)
            msg += (f'; marker {seen.id} confirmed at {seen.distance_3d:.2f} m' if seen
                    else f'; WARNING marker {mid} not in view')
        self.say(msg)
        if name != 'home':
            end = time.monotonic() + self.gp('dwell_time')
            while time.monotonic() < end:
                if self.abort_event.is_set():
                    raise MissionAborted()
                time.sleep(0.1)
            self.say(f'Delivered at {name}')
        return True

    # --------------------------------------------- multipoint delivery
    def plan_tour(self, start, stops, end, optimize=True):
        """Shortest multipoint route on the SLAM map.

        start, end: (label, (x, y)); stops: list of delivery point names.
        1. One full Dijkstra run from the start and from every stop gives the
           shortest path length between every pair of points (on the inflated
           occupancy grid, so the lengths are real driving distances).
        2. The visiting order with the smallest total length is found exactly
           (Held-Karp dynamic programming, up to 12 stops; above that nearest
           neighbour + 2-opt).
        Returns dict(order, legs, total, given_total) or raises ValueError.
        """
        plan = self.nav_grid()
        nodes = [start] + [(n, (float(self.points[n]['x']), float(self.points[n]['y'])))
                           for n in stops] + [end]
        t0 = time.monotonic()
        trees = [plan.dijkstra_tree(xy) for _, xy in nodes[:-1]]
        n = len(nodes)
        D = np.full((n, n), math.inf)
        for i, tree in enumerate(trees):
            for j, (_, xy) in enumerate(nodes):
                D[i, j] = 0.0 if i == j else plan.tree_cost(tree, xy)
        bad = [nodes[j][0] for j in range(1, n) if not math.isfinite(D[0, j])]
        if trees[0] is None or bad:
            raise ValueError(f'unreachable on the map: {bad or [start[0]]}')
        k = len(stops)
        idx = list(range(1, k + 1))
        if not optimize or k <= 1:
            order = idx
        elif k <= 12:
            order = self._held_karp(D, k)
        else:
            order = self._two_opt(D, self._nearest_neighbour(D, k))

        def length(o):
            seq = [0] + o + [n - 1]
            return float(sum(D[a, b] for a, b in zip(seq, seq[1:])))
        seq = [0] + order + [n - 1]
        legs = [(nodes[a][0], nodes[b][0], float(D[a, b])) for a, b in zip(seq, seq[1:])]
        # full route for RViz from the Dijkstra trees
        full = []
        for a, b in zip(seq, seq[1:]):
            full += plan.tree_path(trees[a], nodes[b][1]) or []
        self._publish_route(full)
        return dict(order=[nodes[i][0] for i in order], legs=legs, total=length(order),
                    given_total=length(idx), seconds=time.monotonic() - t0, path=full)

    def preview_tour(self, start_name, stops, end_name, optimize=True):
        """Plan without driving: the way to the start point (if any) plus the
        shortest tour. Returns the plan_tour dict with 'approach' (path from the
        robot to the start) and 'approach_length' added. Raises ValueError."""
        for nm in [start_name, end_name] + list(stops):
            if nm and nm not in self.points:
                raise ValueError(f'unknown point {nm!r}')
        plan = self.nav_grid()
        here = tuple(self.pose()[:2])
        approach, approach_len = [], 0.0
        if start_name:
            sxy = self._point(start_name)
            if math.hypot(here[0] - sxy[0], here[1] - sxy[1]) > 0.5:
                tree = plan.dijkstra_tree(here)
                approach = (plan.tree_path(tree, sxy) or []) if tree is not None else []
                approach_len = plan.tree_cost(tree, sxy) if tree is not None else math.inf
                if not approach or not math.isfinite(approach_len):
                    raise ValueError(f'no path from the robot to {start_name}')
            start = (start_name, sxy)
        else:
            start = ('current position', here)
        end_name = end_name or start_name
        end = (end_name, self._point(end_name)) if end_name else start
        tour = self.plan_tour(start, stops, end, optimize)
        tour.update(approach=approach, approach_length=float(approach_len), start=start[0],
                    end=end[0])
        self._publish_route(approach + tour['path'])
        return tour

    @staticmethod
    def _held_karp(D, k):
        """Exact shortest open path 0 -> all of 1..k -> k+1."""
        full = (1 << k) - 1
        best = {(1 << i, i): (D[0, i + 1], -1) for i in range(k)}
        for mask in range(1, full + 1):
            for last in range(k):
                if (mask, last) not in best:
                    continue
                cost, _ = best[(mask, last)]
                for nxt in range(k):
                    if mask & (1 << nxt):
                        continue
                    key = (mask | (1 << nxt), nxt)
                    c = cost + D[last + 1, nxt + 1]
                    if key not in best or c < best[key][0]:
                        best[key] = (c, last)
        last = min(range(k), key=lambda i: best[(full, i)][0] + D[i + 1, k + 1])
        order, mask = [], full
        while last != -1:
            order.append(last + 1)
            prev = best[(mask, last)][1]
            mask &= ~(1 << last)
            last = prev
        return order[::-1]

    @staticmethod
    def _nearest_neighbour(D, k):
        order, cur, left = [], 0, set(range(1, k + 1))
        while left:
            cur = min(left, key=lambda j: D[cur, j])
            order.append(cur)
            left.remove(cur)
        return order

    @staticmethod
    def _two_opt(D, order):
        n_end = len(order) + 1
        seq = [0] + order + [n_end]
        improved = True
        while improved:
            improved = False
            for i in range(1, len(seq) - 2):
                for j in range(i + 1, len(seq) - 1):
                    a, b, c, d = seq[i - 1], seq[i], seq[j], seq[j + 1]
                    if D[a, c] + D[b, d] < D[a, b] + D[c, d] - 1e-9:
                        seq[i:j + 1] = seq[i:j + 1][::-1]
                        improved = True
        return seq[1:-1]

    def _publish_route(self, pts):
        msg = Path()
        msg.header.frame_id = self.gp('map_frame')
        msg.header.stamp = self.get_clock().now().to_msg()
        for x, y in pts:
            ps = PoseStamped()
            ps.header = msg.header
            ps.pose.position.x, ps.pose.position.y = float(x), float(y)
            ps.pose.orientation.w = 1.0
            msg.poses.append(ps)
        self.route_pub.publish(msg)

    def _point(self, name):
        dp = self.points[name]
        return (float(dp['x']), float(dp['y']))

    def run_tour(self, start_name, stops, end_name, optimize=True, deliver_start=False):
        """Drive start -> stops in the shortest order -> end, delivering at each.
        deliver_start: also deliver at the start point ("go to 3, then ...")."""
        for nm in [start_name, end_name] + list(stops):
            if nm and nm not in self.points:
                self.say(f'Unknown point {nm!r}')
                return False
        if start_name:
            if math.hypot(*np.subtract(self.pose()[:2], self._point(start_name))) > 0.5:
                self.say(f'Driving to the route start {start_name}')
                if not self.navigate_to(self._point(start_name),
                                        final_yaw=self.points[start_name].get('yaw')):
                    self.say(f'FAILED to reach the route start {start_name}')
                    return False
            if deliver_start and start_name != 'home':
                self.deliver(start_name)
            start = (start_name, self._point(start_name))
        else:
            start = ('current position', tuple(self.pose()[:2]))
        end_name = end_name or start_name
        end = (end_name, self._point(end_name)) if end_name else start
        try:
            tour = self.plan_tour(start, stops, end, optimize)
        except ValueError as exc:
            self.say(f'Cannot plan the route: {exc}')
            return False
        lines = [f'Shortest route ({tour["total"]:.1f} m, given order would be '
                 f'{tour["given_total"]:.1f} m; planned in {tour["seconds"]:.1f} s):']
        for i, (a, b, d) in enumerate(tour['legs'], 1):
            lines.append(f'  leg {i}: {a} -> {b}  {d:.1f} m')
        self.say('\n'.join(lines))
        t0 = self.sim_now()
        done = []
        for name in tour['order']:
            if self.deliver(name):
                done.append(name)
        if end_name and end_name not in tour['order']:
            self.deliver(end_name)
        elif not end_name:
            self.navigate_to(start[1])
        self.say(f'Route finished in {self.sim_now() - t0:.0f} s: delivered at '
                 f'{len(done)}/{len(stops)} stops ({", ".join(done)})')
        return len(done) == len(stops)

    def print_points(self):
        lines = ['Delivery points:']
        for i, (n, dp) in enumerate(self.points.items(), 1):
            lines.append(f'  {i:>2}. {n:<26} ({dp["x"]:7.2f}, {dp["y"]:7.2f})')
        print('\n'.join(lines), flush=True)

    def _stdin_reader(self):
        while rclpy.ok():
            try:
                line = input('delivery point, or "route <start> <stop> ... <end>", '
                             '"list", "q"> ')
            except EOFError:
                return
            self.goals.put(line.strip())

    def run(self):
        if not self.wait_for_sensors():
            return
        self.set_initial_pose()
        stops = [str(d).strip() for d in (self.gp('stops') or []) if str(d).strip()]
        if stops:
            self.print_points()
            self.run_tour(self.gp('route_start').strip(),
                          [self.resolve(s) or s for s in stops],
                          self.gp('route_end').strip(), self.gp('optimize_order'))
            return
        route = [d for d in (self.gp('deliveries') or []) if str(d).strip()]
        for d in route:
            self.goals.put(str(d))
        interactive = self.gp('interactive') and not route and sys.stdin.isatty()
        self.print_points()
        if interactive:
            threading.Thread(target=self._stdin_reader, daemon=True).start()
        elif not route:
            self.say('Waiting for goals on /delivery_navigator/goal ...')
        done_route = False
        while rclpy.ok():
            try:
                text = self.goals.get(timeout=0.5)
            except queue.Empty:
                if route and not done_route and self.goals.empty():
                    done_route = True
                    if self.gp('return_home') and route[-1] != 'home':
                        self.deliver('home')
                    self.say('Route finished.')
                    if not interactive:
                        return
                continue
            if not text:
                continue
            if text.lower() in ('q', 'quit', 'exit'):
                return
            if text.lower() in ('l', 'list'):
                self.print_points()
                continue
            if text.lower().startswith('route '):
                names = [self.resolve(t) or t for t in text.split()[1:]]
                if len(names) < 3:
                    print('usage: route <start> <stop> [<stop> ...] <end>', flush=True)
                    continue
                self.run_tour(names[0], names[1:-1], names[-1], self.gp('optimize_order'))
                continue
            name = self.resolve(text)
            if name is None:
                print(f'Unknown delivery point {text!r}', flush=True)
                self.print_points()
                continue
            self.deliver(name)


def main(args=None):
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = DeliveryNavigator()
    executor, _ = spin_in_background(node)
    try:
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.stop()
        except Exception:  # noqa: BLE001
            pass
        executor.shutdown(timeout_sec=1.0)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
