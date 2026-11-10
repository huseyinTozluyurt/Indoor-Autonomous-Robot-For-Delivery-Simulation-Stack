#!/usr/bin/env python3
"""Web bridge: connects the DeliveryBot web application (React + Spring Boot +
MySQL) to the Gazebo delivery simulation.

The Spring Boot backend already talks to the real robot (Raspberry Pi) over a
small REST API on port 5000. This node serves the SAME API, so the web app
drives the simulated robot when Robot Settings points at this PC
(IP 127.0.0.1, port 5000), and the real robot when it points at the Pi.

Robot side it is delivery_navigator.DeliveryNavigator (the same map, EKF
localization on the ArUco markers, Dijkstra planning and delivery check as
delivery_navigator / delivery_gui).

REST API (JSON):

  POST /robot/delivery   {"orderID": "1001", "orderDbId": 7, "tableNumber": 3,
                          "targetArucoId": 12, "route": ""}
        Queues a delivery. The delivery point is found from
          1. route, if it is a delivery point name or number of the map, else
          2. targetArucoId: the delivery point whose marker_id (or marker_ids)
             is that ArUco ID.
        Orders that wait together are driven as one shortest-order tour
        (Dijkstra + exact order), then the robot returns home.
  POST /robot/command    {"command": "FORWARD" | "BACKWARD" | "LEFT" | "RIGHT" |
                          "STOP" | "EMERGENCY_STOP" | "RETURN_BASE" | "SET_HOME_POSE" |
                          "RELOCALIZE"}
  GET  /robot/status          state, pose, current and queued orders, log
  GET  /robot/points          delivery points of the map (name, marker id, x, y)
  GET  /robot/jobs            recent deliveries and their status
  GET  /robot/sensors/latest  front/left/right/back distance in cm from the lidar
  GET  /robot/camera-stream   MJPEG stream of the robot camera
  GET  /robot/camera-snapshot one JPEG

Every change of an order (Delivering, Delivered, Failed, Cancelled) is sent to
the backend: POST {backend_url}/orders/robot-status
{"id": <orderDbId>, "orderID": ..., "status": ..., "message": ..., "deliveryPoint": ...}

Run (simulation running, robot at home):

    ros2 run indoor_delivery_project web_bridge --ros-args \\
        -p map_dir:=~/ros2_jazzy_ws/maps/campus_full_map7 \\
        -p backend_url:=http://localhost:8080/api
"""
import itertools
import json
import math
import os
import queue
import sys
import threading
import time as wall
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import cv2
import numpy as np
import rclpy
from rclpy.qos import qos_profile_sensor_data
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import Image

try:
    from indoor_delivery_project.delivery_navigator import DeliveryNavigator
    from indoor_delivery_project.aruco_slam_mapper import MissionAborted, spin_in_background
    from indoor_delivery_project.image_utils import image_to_bgr
except ImportError:                         # run as a plain script
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from delivery_navigator import DeliveryNavigator  # noqa: E402
    from aruco_slam_mapper import MissionAborted, spin_in_background  # noqa: E402
    from image_utils import image_to_bgr  # noqa: E402

FINAL = ('Delivered', 'Failed', 'Cancelled')
MANUAL = {                      # command -> (linear factor, angular factor)
    'FORWARD': (1.0, 0.0),
    'BACKWARD': (-1.0, 0.0),
    'LEFT': (0.0, 1.0),
    'RIGHT': (0.0, -1.0),
}


class WebBridge(DeliveryNavigator):
    """DeliveryNavigator driven by HTTP requests from the web backend."""

    def __init__(self):
        super().__init__()
        p = self.declare_parameter
        p('http_host', '0.0.0.0')
        p('http_port', 5000)
        p('backend_url', 'http://localhost:8080/api')   # '' = do not report back
        p('stream_topic', '/robot/aruco_camera/image_raw')
        p('stream_fps', 5.0)
        p('jpeg_quality', 70)
        p('manual_speed', 0.3)          # m/s for FORWARD / BACKWARD
        p('manual_turn', 0.6)           # rad/s for LEFT / RIGHT
        p('manual_duration', 0.6)       # s each manual command drives
        p('body_radius', 0.3)           # m, subtracted from the lidar distances
        p('world', 'two_buildings')     # Gazebo world: drawn as the campus map of the web app
        p('world_file', '')             # or the .sdf path itself
        if 'home' not in self.points:   # deliver('home') needs it
            self.points['home'] = {'x': self.home[0], 'y': self.home[1], 'yaw': self.home[2]}

        self.state = 'starting'
        self.job_lock = threading.Lock()
        self.job_event = threading.Event()
        self.queue = deque()            # jobs waiting
        self.current = []               # jobs of the running batch
        self.history = deque(maxlen=100)
        self._ids = itertools.count(1)
        self.log = deque(maxlen=40)
        self.last_message = ''
        self._manual_token = 0
        self._shutdown = threading.Event()
        self.manual = False             # admin has taken control: no autonomous driving
        self.route_pts = []             # route being driven, for the web map
        self._map_cache = None          # (png bytes, info dict)

        self._report_q = queue.Queue()
        threading.Thread(target=self._reporter, daemon=True).start()

        self._jpeg = None
        self._jpeg_seq = 0
        self._jpeg_cond = threading.Condition()
        self._last_frame = 0.0
        self.create_subscription(Image, self.gp('stream_topic'), self._stream_cb,
                                 qos_profile_sensor_data)

    # ------------------------------------------------------------ messages
    def say(self, text):
        super().say(text)
        self.last_message = text
        if hasattr(self, 'log'):          # say() may run inside the base __init__
            self.log.append({'time': wall.strftime('%H:%M:%S'), 'text': text})

    def _job_public(self, j):
        return {k: j.get(k) for k in ('jobId', 'orderID', 'orderDbId', 'tableNumber',
                                      'targetArucoId', 'deliveryPoint', 'status', 'message',
                                      'created', 'updated')}

    def _set_job(self, job, status, message=None):
        job['status'] = status
        if message is not None:
            job['message'] = message
        job['updated'] = wall.strftime('%H:%M:%S')
        if job.get('orderID') is not None or job.get('orderDbId') is not None:
            self._report_q.put({'id': job.get('orderDbId'), 'orderID': job.get('orderID'),
                                'status': status, 'message': job.get('message'),
                                'deliveryPoint': job.get('deliveryPoint')})

    def _reporter(self):
        """Sends order status changes to the Spring Boot backend (own thread,
        so a stopped backend never blocks the robot)."""
        warned = 0.0
        while True:
            body = self._report_q.get()
            url = self.gp('backend_url').rstrip('/')
            if not url:
                continue
            req = urllib.request.Request(url + '/orders/robot-status',
                                         data=json.dumps(body).encode(),
                                         headers={'Content-Type': 'application/json'},
                                         method='POST')
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    r.read()
            except (urllib.error.URLError, OSError, ValueError) as exc:
                if wall.monotonic() - warned > 10.0:
                    warned = wall.monotonic()
                    self.get_logger().warning(f'Could not report order status to {url}: {exc}')

    def _publish_route(self, pts):
        super()._publish_route(pts)
        pts = [(float(x), float(y)) for x, y in pts]
        step = max(1, len(pts) // 400)            # at most ~400 points to the browser
        self.route_pts = [[round(x, 2), round(y, 2)] for x, y in pts[::step]]
        if pts:
            self.route_pts.append([round(pts[-1][0], 2), round(pts[-1][1], 2)])

    # ------------------------------------------------------------ campus map
    def map_data(self):
        """The saved SLAM map as a PNG (walls dark, floor light, unknown grey)
        plus what the web page needs to place things on it:
        pixel (px, py) of a world point (x, y) = ((x - x0) / res, height - (y - y0) / res)."""
        if self._map_cache is None:
            g = self.static_grid
            r0, r1, c0, c1 = g.known_bbox(margin_cells=15)
            t = g.ternary()[r0:r1, c0:c1]
            img = np.empty(t.shape + (3,), np.uint8)
            img[:] = (205, 211, 207)                  # unknown (BGR)
            img[t == 0] = (232, 241, 244)             # floor
            img[t == 100] = (63, 79, 47)              # walls
            img = np.ascontiguousarray(np.flipud(img))
            ok, png = cv2.imencode('.png', img)
            if not ok:
                raise RuntimeError('could not encode the map')
            h, w = img.shape[:2]
            info = {'width': int(w), 'height': int(h), 'resolution': float(g.res),
                    'x0': float(g.origin[0] + c0 * g.res), 'y0': float(g.origin[1] + r0 * g.res),
                    'mapDir': os.path.expanduser(self.gp('map_dir')),
                    'home': {'x': self.home[0], 'y': self.home[1]}}
            info['layout'] = self.world_layout()
            self._map_cache = (png.tobytes(), info)
        png, info = self._map_cache
        return png, dict(info, points=self.points_list())

    def _world_path(self):
        path = os.path.expanduser(str(self.gp('world_file') or ''))
        if path:
            return path
        name = str(self.gp('world') or '')
        if not name:
            return ''
        if not name.endswith('.sdf'):
            name += '.sdf'
        try:
            from ament_index_python.packages import get_package_share_directory
            return os.path.join(get_package_share_directory('indoor_delivery_project'),
                                'worlds', name)
        except Exception:  # noqa: BLE001
            return ''

    def world_layout(self):
        """Floors, walls, tables and pads of the Gazebo world (top view, metres),
        so the web app can draw the campus as it looks in the simulation.
        Returns None if the world file is not found."""
        path = self._world_path()
        if not path or not os.path.isfile(path):
            self.get_logger().warning(f'World file not found ({path!r}): web map uses the SLAM image')
            return None
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError) as exc:
            self.get_logger().warning(f'Could not read the world {path}: {exc}')
            return None

        def pose6(text):
            v = [float(t) for t in (text or '').split()] + [0.0] * 6
            return v[0], v[1], v[5]

        def colour(vis):
            for tag in ('material/diffuse', 'material/ambient'):
                t = vis.findtext(tag)
                if t:
                    c = [float(x) for x in t.split()[:3]]
                    return '#%02x%02x%02x' % tuple(int(max(0, min(1, x)) * 255) for x in c)
            return None

        shapes = []
        for model in root.iter('model'):
            name = model.get('name') or ''
            if name == 'ground_plane':
                continue
            mx, my, myaw = pose6(model.findtext('pose'))
            if name.endswith('_floor'):
                kind = 'floor'
            elif 'wall' in name:
                kind = 'wall'
            elif 'table' in name:
                kind = 'table'
            elif 'delivery_point' in name:
                kind = 'pad'
            else:
                kind = 'object'
            for link in model.findall('link'):
                lx, ly, lyaw = pose6(link.findtext('pose'))
                for vis in link.findall('visual'):
                    vx, vy, vyaw = pose6(vis.findtext('pose'))
                    # visual -> link -> model -> world (2-D)
                    x1 = lx + vx * math.cos(lyaw) - vy * math.sin(lyaw)
                    y1 = ly + vx * math.sin(lyaw) + vy * math.cos(lyaw)
                    x = mx + x1 * math.cos(myaw) - y1 * math.sin(myaw)
                    y = my + x1 * math.sin(myaw) + y1 * math.cos(myaw)
                    yaw = math.degrees(myaw + lyaw + vyaw)
                    box = vis.findtext('geometry/box/size')
                    cyl = vis.find('geometry/cylinder')
                    part = kind
                    if kind == 'table':
                        vname = vis.get('name') or ''
                        if vname.startswith('body'):
                            continue               # same outline as the table top
                        part = 'table' if vname.startswith('top') else 'chair'
                    item = {'kind': part, 'name': name, 'x': round(x, 3), 'y': round(y, 3),
                            'yaw': round(yaw, 1), 'color': colour(vis)}
                    if box:
                        sx, sy = [float(t) for t in box.split()[:2]]
                        item.update(shape='box', w=round(sx, 3), h=round(sy, 3))
                    elif cyl is not None:
                        item.update(shape='circle', r=round(float(cyl.findtext('radius') or 0.5), 3))
                    else:
                        continue
                    shapes.append(item)
        if not shapes:
            return None
        xs, ys = [], []
        for it in shapes:
            if it['shape'] == 'circle':
                ex = ey = it['r']
            else:
                c, s_ = abs(math.cos(math.radians(it['yaw']))), abs(math.sin(math.radians(it['yaw'])))
                ex = it['w'] / 2 * c + it['h'] / 2 * s_
                ey = it['w'] / 2 * s_ + it['h'] / 2 * c
            xs += [it['x'] - ex, it['x'] + ex]
            ys += [it['y'] - ey, it['y'] + ey]
        return {'world': os.path.basename(path), 'shapes': shapes,
                'bounds': {'xmin': min(xs), 'xmax': max(xs), 'ymin': min(ys), 'ymax': max(ys)}}

    def plan(self, stops, end='home'):
        """Dijkstra shortest tour from the robot through the stops (best order),
        without driving. Returns a dict for the web page."""
        names = []
        for s_ in stops:
            n = s_ if s_ in self.points else self.resolve(str(s_))
            if n is None:
                raise ValueError(f'unknown delivery point {s_!r}')
            if n != 'home' and n not in names:
                names.append(n)
        if not names:
            raise ValueError('no delivery points given')
        keep = self.route_pts
        try:
            tour = self.preview_tour('', names, end if end in self.points else 'home',
                                     self.gp('optimize_order'))
        finally:
            self.route_pts = keep                 # a preview is not the driven route
        path = tour['approach'] + tour['path']
        step = max(1, len(path) // 400)
        return {'order': tour['order'], 'start': tour['start'], 'end': tour['end'],
                'legs': [{'from': a, 'to': b, 'length': round(d, 1)} for a, b, d in tour['legs']],
                'total': round(tour['total'] + tour['approach_length'], 1),
                'givenOrderTotal': round(tour['given_total'], 1),
                'seconds': round(tour['seconds'], 2),
                'path': [[round(float(x), 2), round(float(y), 2)] for x, y in path[::step]]}

    # ------------------------------------------------------------ jobs
    def resolve_target(self, body):
        """Delivery point for a request: route (point name / number), else the
        point whose marker is targetArucoId. Returns (name, None) or (None, error)."""
        names = list(self.points)
        route = str(body.get('route') or '').strip()
        if route:
            if route in self.points:
                return route, None
            low = {n.lower(): n for n in names}
            if route.lower() in low:
                return low[route.lower()], None
            if route.isdigit() and 1 <= int(route) <= len(names):
                return names[int(route) - 1], None
        aid = body.get('targetArucoId', body.get('arucoId'))
        if aid is not None and str(aid).strip() != '':
            try:
                aid = int(aid)
            except (TypeError, ValueError):
                return None, f'targetArucoId {aid!r} is not a number'
            for n, dp in self.points.items():
                ids = set(dp.get('marker_ids') or [])
                if dp.get('marker_id') is not None:
                    ids.add(int(dp['marker_id']))
                if aid in {int(i) for i in ids}:
                    return n, None
            valid = sorted(int(dp['marker_id']) for dp in self.points.values()
                           if dp.get('marker_id') is not None)
            return None, f'no delivery point has ArUco marker {aid} (valid IDs: {valid})'
        return None, ('the order has no ArUco ID and its route is not a delivery point; '
                      'set the table ArUco ID to one of the map markers')

    def add_job(self, point, body=None):
        body = body or {}
        job = {'jobId': next(self._ids), 'orderID': body.get('orderID'),
               'orderDbId': body.get('orderDbId'), 'tableNumber': body.get('tableNumber'),
               'targetArucoId': body.get('targetArucoId'), 'deliveryPoint': point,
               'status': 'Queued', 'message': f'Queued for {point}',
               'created': wall.strftime('%H:%M:%S'), 'updated': wall.strftime('%H:%M:%S')}
        with self.job_lock:
            self.queue.append(job)
            self.history.append(job)
            position = len(self.queue) + (1 if self.current else 0)
        self.job_event.set()
        return job, position

    def add_jobs(self, items):
        """Queue several deliveries at once, so they are driven as ONE tour.
        items: list of (point, body)."""
        jobs = []
        with self.job_lock:
            for point, body in items:
                job = {'jobId': next(self._ids), 'orderID': body.get('orderID'),
                       'orderDbId': body.get('orderDbId'), 'tableNumber': body.get('tableNumber'),
                       'targetArucoId': body.get('targetArucoId'), 'deliveryPoint': point,
                       'status': 'Queued', 'message': f'Queued for {point}',
                       'created': wall.strftime('%H:%M:%S'), 'updated': wall.strftime('%H:%M:%S')}
                self.queue.append(job)
                self.history.append(job)
                jobs.append(job)
        self.job_event.set()
        return jobs

    def cancel_queue(self, reason):
        with self.job_lock:
            jobs = list(self.queue)
            self.queue.clear()
        for j in jobs:
            self._set_job(j, 'Cancelled', reason)
        return len(jobs)

    def deliver(self, name):
        if name == 'home':
            with self.job_lock:
                waiting = bool(self.queue)
            if waiting:
                self.say('New orders are waiting: not driving home first')
                return True
            self.state = 'returning home'
            return super().deliver(name)
        jobs = [j for j in self.current if j['deliveryPoint'] == name and j['status'] not in FINAL]
        for j in jobs:
            self._set_job(j, 'Delivering', f'Robot on the way to {name}')
        self.state = f'delivering to {name}'
        try:
            ok = super().deliver(name)
        except MissionAborted:
            if not self.manual:               # a takeover only pauses the delivery
                for j in jobs:
                    self._set_job(j, 'Cancelled', 'Stopped by the user')
            raise
        for j in jobs:
            self._set_job(j, 'Delivered' if ok else 'Failed', self.last_message)
        return ok

    def _run_batch(self, batch):
        for j in batch:
            if j['deliveryPoint'] != 'home' and j['status'] not in ('Delivering',):
                self._set_job(j, 'Delivering', 'Loaded on the robot; route planned')
        stops = []
        for j in batch:
            if j['deliveryPoint'] != 'home' and j['deliveryPoint'] not in stops:
                stops.append(j['deliveryPoint'])
        if not stops:
            self.deliver('home')
        elif self.gp('return_home'):
            self.run_tour('', stops, 'home', self.gp('optimize_order'))
        else:
            for s in stops:
                self.deliver(s)

    def worker(self):
        self.state = 'waiting for sensors'
        while not self._shutdown.is_set():
            if self.wait_for_sensors():
                break
            self.state = 'no sensor data (is the simulation running?)'
            self.say('No sensor data yet: is the simulation running? Retrying...')
        if self._shutdown.is_set():
            return
        self.set_initial_pose()
        self.state = 'idle'
        self.say('Web bridge ready: waiting for deliveries from the web app')
        while not self._shutdown.is_set() and rclpy.ok():
            # goals typed with: ros2 topic pub /delivery_navigator/goal ... also work
            while not self.goals.empty():
                name = self.resolve(self.goals.get().strip())
                if name:
                    self.add_job(name)
            self.job_event.wait(0.5)
            if self.manual:
                self.state = 'manual control (admin)'
                continue
            with self.job_lock:
                batch = list(self.queue)
                self.queue.clear()
                self.job_event.clear()
                self.current = batch
            if not batch:
                continue
            self.abort_event.clear()
            self.state = 'busy'
            paused = []
            try:
                self._run_batch(batch)
            except MissionAborted:
                if self.manual:
                    # admin took control: keep the orders, resume them on release
                    paused = [j for j in batch if j['status'] not in FINAL]
                    for j in paused:
                        self._set_job(j, j['status'] if j['deliveryPoint'] != 'home' else 'Queued',
                                      'Paused: the admin has taken manual control')
                    with self.job_lock:
                        self.queue.extendleft(reversed(paused))
                    self.say(f'Admin took control: {len(paused)} deliveries paused')
                else:
                    self.say('Mission STOPPED')
                    for j in batch:
                        if j['status'] not in FINAL:
                            self._set_job(j, 'Cancelled', 'Stopped by the user')
            except Exception as exc:  # noqa: BLE001
                self.get_logger().error(f'Mission failed: {exc}')
                for j in batch:
                    if j['status'] not in FINAL:
                        self._set_job(j, 'Failed', f'Mission failed: {exc}')
            finally:
                try:
                    self.stop()
                except Exception:  # noqa: BLE001
                    pass
                for j in batch:          # e.g. unreachable point: never started
                    if j['status'] not in FINAL and j not in paused:
                        self._set_job(j, 'Failed', self.last_message)
                with self.job_lock:
                    self.current = []
                self.route_pts = []
                self.state = 'manual control (admin)' if self.manual else 'idle'

    # ------------------------------------------------------------ commands
    def busy(self):
        with self.job_lock:
            return bool(self.current) or bool(self.queue)

    def command(self, cmd):
        """Returns (http status, response dict)."""
        cmd = (cmd or '').strip().upper()
        if cmd in ('STOP', 'EMERGENCY_STOP'):
            self._manual_token += 1
            self.abort_event.set()
            n = self.cancel_queue('Emergency stop') if cmd == 'EMERGENCY_STOP' else 0
            threading.Thread(target=self.stop, daemon=True).start()
            self.say(f'{cmd} from the web app' + (f'; {n} queued orders cancelled' if n else ''))
            return 200, {'ok': True, 'command': cmd, 'cancelledQueued': n}
        if cmd in ('TAKEOVER', 'TAKE_CONTROL'):
            if self.manual:
                return 200, {'ok': True, 'command': cmd, 'manual': True}
            self.manual = True
            self._manual_token += 1
            self.abort_event.set()                    # stops the running leg
            threading.Thread(target=self.stop, daemon=True).start()
            self.state = 'manual control (admin)'
            self.say('Admin has taken manual control of the robot')
            return 200, {'ok': True, 'command': cmd, 'manual': True}
        if cmd in ('RELEASE', 'RELEASE_CONTROL', 'RESUME'):
            if not self.manual:
                return 200, {'ok': True, 'command': cmd, 'manual': False}
            self._manual_token += 1
            self._publish_cmd(0.0, 0.0)
            self.abort_event.clear()
            self.manual = False
            with self.job_lock:
                waiting = len(self.queue)
            self.state = 'idle'
            self.job_event.set()
            self.say('Admin released control' + (f'; resuming {waiting} deliveries' if waiting else ''))
            return 200, {'ok': True, 'command': cmd, 'manual': False, 'resuming': waiting}
        if cmd in ('RETURN_HOME_NOW', 'RETURN_START_NOW'):
            # stop what the robot is doing, give the orders back, drive to the start point
            was_manual = self.manual
            self.manual = False
            self._manual_token += 1
            n = self.cancel_queue('Robot sent back to the starting point by the admin')
            with self.job_lock:
                running = bool(self.current)
            if running:
                self.abort_event.set()        # the worker cancels the running orders
            elif was_manual:
                self.abort_event.clear()
            job, pos = self.add_job('home')
            hx, hy = self.home[0], self.home[1]
            self.say(f'Returning to the starting point ({hx:.1f}, {hy:.1f}) now'
                     + (f'; {n} waiting orders cancelled' if n else '')
                     + ('; current delivery stopped' if running else ''))
            return 200, {'ok': True, 'command': cmd, 'jobId': job['jobId'],
                         'cancelledQueued': n, 'interrupted': running,
                         'home': {'x': hx, 'y': hy}}
        if cmd in ('RETURN_BASE', 'HOME', 'RETURN_HOME'):
            job, pos = self.add_job('home')
            return 200, {'ok': True, 'command': cmd, 'jobId': job['jobId'], 'queuePosition': pos}
        if cmd in MANUAL:
            if self.busy() and not self.manual:
                return 409, {'ok': False,
                             'error': 'robot is on a delivery; press Take control first'}
            if self.state.startswith('waiting') or self.state.startswith('no sensor'):
                return 409, {'ok': False, 'error': f'robot not ready: {self.state}'}
            lin, ang = MANUAL[cmd]
            self._manual_token += 1
            token = self._manual_token
            v, w = lin * self.gp('manual_speed'), ang * self.gp('manual_turn')
            duration = self.gp('manual_duration')

            def drive():
                end = wall.monotonic() + duration
                while wall.monotonic() < end and token == self._manual_token:
                    self._publish_cmd(v, w)
                    wall.sleep(0.1)
                if token == self._manual_token:
                    self._publish_cmd(0.0, 0.0)
            threading.Thread(target=drive, daemon=True).start()
            return 200, {'ok': True, 'command': cmd}
        if cmd in ('SET_HOME_POSE', 'POSE_HOME'):
            if self.busy():
                return 409, {'ok': False, 'error': 'robot is busy'}
            with self.lock:
                self.ekf.set_pose(self.home, sigma=(0.1, 0.1, 0.05))
            self.say('Pose set to home')
            return 200, {'ok': True, 'command': cmd}
        if cmd == 'RELOCALIZE':
            if self.busy():
                return 409, {'ok': False, 'error': 'robot is busy'}
            self.abort_event.clear()
            threading.Thread(target=self.recover_pose, daemon=True).start()
            return 200, {'ok': True, 'command': cmd}
        return 400, {'ok': False, 'error': f'unknown command {cmd!r}',
                     'commands': sorted(list(MANUAL) + ['STOP', 'EMERGENCY_STOP', 'RETURN_BASE',
                                                        'SET_HOME_POSE', 'RELOCALIZE',
                                                        'TAKEOVER', 'RELEASE',
                                                        'RETURN_HOME_NOW'])}

    # ------------------------------------------------------------ status
    def status(self):
        try:
            x, y, th = self.pose()
            pose = {'x': round(float(x), 3), 'y': round(float(y), 3),
                    'yawDeg': round(math.degrees(float(th)), 1)}
        except Exception:  # noqa: BLE001
            pose = None
        with self.job_lock:
            current = [self._job_public(j) for j in self.current]
            waiting = [self._job_public(j) for j in self.queue]
        return {'status': 'online', 'simulation': True, 'state': self.state,
                'ready': self.state not in ('starting', 'waiting for sensors')
                and not self.state.startswith('no sensor'),
                'pose': pose, 'currentOrders': current, 'queue': waiting,
                'manual': self.manual, 'route': self.route_pts,
                'lastMessage': self.last_message, 'log': list(self.log)[-15:],
                'mapDir': os.path.expanduser(self.gp('map_dir'))}

    def points_list(self):
        out = []
        for i, (n, dp) in enumerate(self.points.items(), 1):
            out.append({'number': i, 'name': n, 'markerId': dp.get('marker_id'),
                        'markerIds': dp.get('marker_ids'),
                        'x': round(float(dp['x']), 2), 'y': round(float(dp['y']), 2)})
        return out

    def sensors(self):
        """Closest lidar return in 4 sectors (+-25 deg), cm from the robot body."""
        with self.lock:
            pts = None if getattr(self, 'scan_base', None) is None else self.scan_base.copy()
            valid = None if getattr(self, 'scan_valid', None) is None else self.scan_valid.copy()
        if pts is None or valid is None or not valid.any():
            return {'front': None, 'left': None, 'right': None, 'back': None, 'error': 1}
        pts = pts[valid]
        ang = np.arctan2(pts[:, 1], pts[:, 0])
        dist = np.hypot(pts[:, 0], pts[:, 1])
        body = self.gp('body_radius')
        out = {'error': 0}
        for key, centre in (('front', 0.0), ('left', 90.0), ('right', -90.0), ('back', 180.0)):
            diff = np.abs((ang - math.radians(centre) + math.pi) % (2 * math.pi) - math.pi)
            sel = dist[diff < math.radians(25)]
            out[key] = int(round(max(float(sel.min()) - body, 0.0) * 100)) if sel.size else None
        return out

    # ------------------------------------------------------------ camera
    def _stream_cb(self, msg):
        now = wall.monotonic()
        if now - self._last_frame < 1.0 / max(self.gp('stream_fps'), 0.5):
            return
        self._last_frame = now
        try:
            bgr = image_to_bgr(msg)
        except ValueError:
            return
        with self.lock:
            obs = list(getattr(self, 'last_obs', []) or [])
            fresh = wall.monotonic() - getattr(self, 'last_obs_wall', 0.0) < 1.0
        if fresh and obs:
            text = 'markers: ' + ', '.join(f'{o.id} ({o.range:.1f} m)' for o in obs)
            cv2.putText(bgr, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(bgr, self.state, (10, bgr.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (255, 255, 255), 2)
        ok, jpg = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, int(self.gp('jpeg_quality'))])
        if ok:
            with self._jpeg_cond:
                self._jpeg = jpg.tobytes()
                self._jpeg_seq += 1
                self._jpeg_cond.notify_all()

    def next_jpeg(self, last_seq, timeout=2.0):
        with self._jpeg_cond:
            self._jpeg_cond.wait_for(lambda: self._jpeg_seq != last_seq, timeout=timeout)
            return self._jpeg_seq, self._jpeg


# ===================================================================== HTTP
def make_handler(node):

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, fmt, *args):      # keep the terminal quiet
            pass

        def _cors(self):
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')

        def _json(self, code, data):
            body = json.dumps(data).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def _raw_body(self):
            # Spring's RestTemplate sends POST bodies with chunked transfer encoding
            if 'chunked' in (self.headers.get('Transfer-Encoding') or '').lower():
                parts = []
                while True:
                    size = int(self.rfile.readline().split(b';')[0].strip() or b'0', 16)
                    if size == 0:
                        while self.rfile.readline() not in (b'\r\n', b'\n', b''):
                            pass                   # trailers
                        break
                    parts.append(self.rfile.read(size))
                    self.rfile.readline()          # CRLF after each chunk
                return b''.join(parts)
            n = int(self.headers.get('Content-Length') or 0)
            return self.rfile.read(n) if n > 0 else b''

        def _body(self):
            raw = self._raw_body()
            if not raw.strip():
                return {}
            try:
                data = json.loads(raw.decode() or '{}')
            except (ValueError, UnicodeDecodeError):
                return None
            return data if isinstance(data, dict) else None

        def do_OPTIONS(self):  # noqa: N802
            self.send_response(204)
            self._cors()
            self.send_header('Content-Length', '0')
            self.end_headers()

        def do_GET(self):  # noqa: N802
            path = urlparse(self.path).path.rstrip('/') or '/'
            if path in ('/', '/robot/status'):
                return self._json(200, node.status())
            if path == '/robot/points':
                return self._json(200, node.points_list())
            if path in ('/robot/map.png', '/robot/map-info'):
                try:
                    png, info = node.map_data()
                except Exception as exc:  # noqa: BLE001
                    return self._json(500, {'error': f'map not available: {exc}'})
                if path == '/robot/map-info':
                    return self._json(200, info)
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Content-Length', str(len(png)))
                self.send_header('Cache-Control', 'max-age=60')
                self._cors()
                self.end_headers()
                self.wfile.write(png)
                return None
            if path == '/robot/jobs':
                with node.job_lock:
                    jobs = [node._job_public(j) for j in node.history]
                return self._json(200, jobs[::-1])
            if path == '/robot/sensors/latest':
                return self._json(200, node.sensors())
            if path == '/robot/camera-snapshot':
                _, jpg = node.next_jpeg(-1, timeout=0.0)
                if jpg is None:
                    return self._json(503, {'error': f'no image on {node.gp("stream_topic")} yet'})
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', str(len(jpg)))
                self._cors()
                self.end_headers()
                self.wfile.write(jpg)
                return None
            if path == '/robot/camera-stream':
                return self._mjpeg()
            return self._json(404, {'error': f'unknown path {path}'})

        def _mjpeg(self):
            self.close_connection = True
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'close')
            self._cors()
            self.end_headers()
            seq = -1
            try:
                while not node._shutdown.is_set():
                    seq, jpg = node.next_jpeg(seq)
                    if jpg is None:
                        continue
                    self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '
                                     + str(len(jpg)).encode() + b'\r\n\r\n' + jpg + b'\r\n')
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

        def do_POST(self):  # noqa: N802
            path = urlparse(self.path).path.rstrip('/')
            body = self._body()
            if body is None:
                return self._json(400, {'ok': False, 'error': 'body must be a JSON object'})
            if path == '/robot/delivery':
                point, err = node.resolve_target(body)
                if point is None:
                    node.say(f'Order {body.get("orderID")} rejected: {err}')
                    return self._json(400, {'ok': False, 'accepted': False, 'error': err,
                                            'message': err})
                job, pos = node.add_job(point, body)
                msg = f'Order {job["orderID"]} queued for {point} (position {pos})'
                node.say(msg)
                return self._json(200, {'ok': True, 'accepted': True, 'jobId': job['jobId'],
                                        'deliveryPoint': point, 'queuePosition': pos,
                                        'message': msg})
            if path == '/robot/plan':
                stops = body.get('stops') or []
                try:
                    return self._json(200, node.plan(stops, body.get('end') or 'home'))
                except ValueError as exc:
                    return self._json(400, {'ok': False, 'error': str(exc)})
            if path == '/robot/mission':
                orders = body.get('orders') or []
                if not orders:
                    return self._json(400, {'ok': False, 'error': 'no orders in the mission'})
                items, errors = [], []
                for o in orders:
                    if not isinstance(o, dict):
                        errors.append(f'bad order entry {o!r}')
                        continue
                    point = o.get('deliveryPoint')
                    if point and point not in node.points:
                        errors.append(f'order {o.get("orderID")}: unknown delivery point {point!r}')
                        continue
                    if point not in node.points:
                        point, err = node.resolve_target(o)
                        if point is None:
                            errors.append(f'order {o.get("orderID")}: {err}')
                            continue
                    items.append((point, o))
                if errors:
                    return self._json(400, {'ok': False, 'error': '; '.join(errors)})
                jobs = node.add_jobs(items)
                stops = sorted({p for p, _ in items})
                msg = (f'Mission with {len(jobs)} orders to {len(stops)} delivery points queued'
                       + (' (robot is under manual control; starts on release)'
                          if node.manual else ''))
                node.say(msg)
                return self._json(200, {'ok': True, 'accepted': True, 'message': msg,
                                        'jobs': [node._job_public(j) for j in jobs]})
            if path == '/robot/command':
                code, data = node.command(body.get('command'))
                return self._json(code, data)
            return self._json(404, {'error': f'unknown path {path}'})

    return Handler


def main(args=None):
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = WebBridge()
    executor, _ = spin_in_background(node)
    host, port = node.gp('http_host'), int(node.gp('http_port'))
    httpd = ThreadingHTTPServer((host, port), make_handler(node))
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    node.get_logger().info(f'Web bridge listening on http://{host}:{port} '
                           f'(backend: {node.gp("backend_url") or "off"})')
    worker = threading.Thread(target=node.worker, daemon=True)
    worker.start()
    try:
        while rclpy.ok():
            wall.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        node._shutdown.set()
        node.abort_event.set()
        try:
            node.stop()
        except Exception:  # noqa: BLE001
            pass
        httpd.shutdown()
        executor.shutdown(timeout_sec=1.0)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
