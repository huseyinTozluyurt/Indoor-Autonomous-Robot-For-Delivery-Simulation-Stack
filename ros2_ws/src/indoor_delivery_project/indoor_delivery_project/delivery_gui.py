#!/usr/bin/env python3
"""PyQt5 delivery console on the ArUco SLAM map.

    ros2 run indoor_delivery_project delivery_gui --ros-args \
        -p map_dir:=~/ros2_jazzy_ws/maps/campus6

A mission is "start, stops..., end", for example 3 4 6 7 5:
go to delivery point 3, deliver at 4, 6 and 7, finish at 5. Dijkstra on the
saved occupancy grid gives the real driving distance between every pair of
points; the order of the stops with the shortest total is then found exactly
(Held-Karp). "Plan" only draws the route; "Start" drives it.

Everything robot-side is delivery_navigator.DeliveryNavigator: the same
localization (ArUco beacons + lidar matching on the map), planner and pure
pursuit as the terminal version.
"""
import math
import os
import queue
import re
import sys
import threading

import numpy as np
import rclpy
from rclpy.signals import SignalHandlerOptions

from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt5.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QPixmap, QPolygonF
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image

try:
    from indoor_delivery_project.delivery_navigator import DeliveryNavigator
    from indoor_delivery_project.aruco_slam_mapper import MissionAborted, spin_in_background
    from indoor_delivery_project.robot_vision import (
        StaticMap, VisionOverlay, bgr_to_qimage, image_to_bgr, make_detector)
except ImportError:                         # run as a plain script
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from delivery_navigator import DeliveryNavigator  # noqa: E402
    from aruco_slam_mapper import MissionAborted, spin_in_background  # noqa: E402
    from robot_vision import (  # noqa: E402
        StaticMap, VisionOverlay, bgr_to_qimage, image_to_bgr, make_detector)


class GuiNavigator(DeliveryNavigator):
    """DeliveryNavigator whose messages also go to the window."""

    def __init__(self, log_queue):
        self.log_queue = log_queue
        super().__init__()
        self.declare_parameter('detector', 'auto')       # auto | yolo | none
        self.declare_parameter('yolo_model', 'yolov8n.pt')

    def say(self, text):
        super().say(text)
        self.log_queue.put(text)


# =================================================================== map view
class MapView(QWidget):
    def __init__(self, node, parent=None):
        super().__init__(parent)
        self.node = node
        self.setMinimumSize(500, 400)
        g = node.static_grid
        r0, r1, c0, c1 = g.known_bbox(margin_cells=15)
        self.crop = (r0, r1, c0, c1)
        t = g.ternary()[r0:r1, c0:c1]
        img = np.full(t.shape, 200, np.uint8)
        img[t == 0] = 255
        img[t == 100] = 30
        img = np.ascontiguousarray(np.flipud(img))
        h, w = img.shape
        self._img_data = img
        self.pix = QPixmap.fromImage(QImage(img.data, w, h, w, QImage.Format_Grayscale8))
        self.route = []          # planned path (approach + tour), world xy
        self.approach_len = 0
        self.trail = []
        self.highlight = {}      # point name -> label like "1", "S", "E"
        self.numbers = {n: i for i, n in enumerate(node.points, 1)}
        self.on_click = None

    # world <-> widget
    def _geom(self):
        h, w = self._img_data.shape
        s = min(self.width() / w, self.height() / h)
        ox = (self.width() - w * s) / 2
        oy = (self.height() - h * s) / 2
        return s, ox, oy, h

    def to_px(self, x, y):
        g = self.node.static_grid
        r0, r1, c0, c1 = self.crop
        s, ox, oy, h = self._geom()
        col = (x - g.origin[0]) / g.res - c0
        row = (y - g.origin[1]) / g.res - r0
        return QPointF(ox + col * s, oy + (h - row) * s)

    def to_world(self, px, py):
        g = self.node.static_grid
        r0, r1, c0, c1 = self.crop
        s, ox, oy, h = self._geom()
        col = (px - ox) / s
        row = h - (py - oy) / s
        return (g.origin[0] + (col + c0) * g.res, g.origin[1] + (row + r0) * g.res)

    def mousePressEvent(self, ev):
        if self.on_click is None:
            return
        x, y = self.to_world(ev.x(), ev.y())
        best, bd = None, 1.5
        for name, p in self.node.points.items():
            d = math.hypot(p['x'] - x, p['y'] - y)
            if d < bd:
                best, bd = name, d
        if best:
            self.on_click(best)

    def paintEvent(self, _ev):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        qp.fillRect(self.rect(), QColor(200, 200, 200))
        s, ox, oy, h = self._geom()
        w = self._img_data.shape[1]
        qp.drawPixmap(QRectF(ox, oy, w * s, h * s), self.pix, QRectF(0, 0, w, h))
        # route: approach dashed, tour solid
        if len(self.route) > 1:
            for i, (a, b) in enumerate(zip(self.route, self.route[1:])):
                dashed = i < self.approach_len
                pen = QPen(QColor(120, 120, 255) if dashed else QColor(0, 110, 255), 3)
                if dashed:
                    pen.setStyle(Qt.DashLine)
                qp.setPen(pen)
                qp.drawLine(self.to_px(*a), self.to_px(*b))
        if len(self.trail) > 1:
            qp.setPen(QPen(QColor(0, 170, 0), 2))
            qp.drawPolyline(QPolygonF([self.to_px(*p) for p in self.trail]))
        # markers
        qp.setPen(Qt.NoPen)
        qp.setBrush(QBrush(QColor(220, 0, 0)))
        for m in self.node.lm.values():
            qp.drawEllipse(self.to_px(m['x'], m['y']), 4, 4)
        # delivery points
        f = QFont()
        f.setBold(True)
        f.setPointSize(9)
        qp.setFont(f)
        for name, p in self.node.points.items():
            c = self.to_px(p['x'], p['y'])
            tag = self.highlight.get(name)
            col = QColor(255, 140, 0) if tag is None else QColor(0, 110, 255)
            qp.setPen(QPen(Qt.black, 1))
            qp.setBrush(QBrush(col))
            qp.drawEllipse(c, 9, 9)
            qp.setPen(QPen(Qt.white))
            label = 'H' if name == 'home' else str(self.numbers[name])
            qp.drawText(QRectF(c.x() - 9, c.y() - 9, 18, 18), Qt.AlignCenter, label)
            if tag:
                qp.setPen(QPen(QColor(0, 70, 200)))
                qp.drawText(QPointF(c.x() + 11, c.y() - 8), tag)
        # robot
        try:
            x, y, th = self.node.pose()
        except Exception:  # noqa: BLE001
            return
        c = self.to_px(x, y)
        r = max(7.0, 0.35 / self.node.static_grid.res * s)
        tri = QPolygonF([QPointF(c.x() + r * math.cos(-th), c.y() + r * math.sin(-th)),
                         QPointF(c.x() + r * 0.7 * math.cos(-th + 2.4),
                                 c.y() + r * 0.7 * math.sin(-th + 2.4)),
                         QPointF(c.x() + r * 0.7 * math.cos(-th - 2.4),
                                 c.y() + r * 0.7 * math.sin(-th - 2.4))])
        qp.setPen(QPen(Qt.black, 1))
        qp.setBrush(QBrush(QColor(0, 200, 0)))
        qp.drawPolygon(tri)


# =================================================================== window
class DeliveryWindow(QMainWindow):
    def __init__(self, node, log_queue):
        super().__init__()
        self.node = node
        self.log_queue = log_queue
        self.worker = None
        self.ready = False
        self.names = list(node.points)
        self.setWindowTitle(f'Delivery missions - {os.path.basename(node.gp("map_dir").rstrip("/"))}')

        self.map = MapView(node)
        self.map.on_click = self.add_stop_from_map

        # ---- mission
        box = QGroupBox('Mission')
        grid = QGridLayout(box)
        self.quick = QLineEdit()
        self.quick.setPlaceholderText('e.g.  3 4 6 7 5   (start, stops..., end)')
        self.quick.returnPressed.connect(self.parse_quick)
        bq = QPushButton('Use')
        bq.clicked.connect(self.parse_quick)
        grid.addWidget(QLabel('Quick:'), 0, 0)
        grid.addWidget(self.quick, 0, 1)
        grid.addWidget(bq, 0, 2)
        self.start_cb = QComboBox()
        self.end_cb = QComboBox()
        self.start_cb.addItem('robot position', '')
        self.end_cb.addItem('same as start', '')
        for i, n in enumerate(self.names, 1):
            label = f'{"H" if n == "home" else i}. {n}'
            self.start_cb.addItem(label, n)
            self.end_cb.addItem(label, n)
        grid.addWidget(QLabel('Start (A):'), 1, 0)
        grid.addWidget(self.start_cb, 1, 1, 1, 2)
        self.stops_edit = QLineEdit()
        self.stops_edit.setPlaceholderText('4, 6, 7   (or click points on the map)')
        bc = QPushButton('Clear')
        bc.clicked.connect(lambda: self.stops_edit.clear())
        grid.addWidget(QLabel('Stops:'), 2, 0)
        grid.addWidget(self.stops_edit, 2, 1)
        grid.addWidget(bc, 2, 2)
        grid.addWidget(QLabel('End (B):'), 3, 0)
        grid.addWidget(self.end_cb, 3, 1, 1, 2)
        self.opt = QCheckBox('Shortest order of the stops (Dijkstra + exact order)')
        self.opt.setChecked(True)
        self.deliver_start = QCheckBox('Deliver at the start point too')
        self.deliver_start.setChecked(True)
        grid.addWidget(self.opt, 4, 0, 1, 3)
        grid.addWidget(self.deliver_start, 5, 0, 1, 3)

        # ---- buttons
        self.b_plan = QPushButton('Plan route')
        self.b_go = QPushButton('Start mission')
        self.b_stop = QPushButton('STOP')
        self.b_stop.setStyleSheet('background:#c62828;color:white;font-weight:bold')
        self.b_plan.clicked.connect(self.plan)
        self.b_go.clicked.connect(self.start_mission)
        self.b_stop.clicked.connect(self.stop_mission)
        self.b_home = QPushButton('Pose = home')
        self.b_auto = QPushButton('Find pose (markers)')
        self.b_home.clicked.connect(lambda: self.run_job('set pose', self._set_home))
        self.b_auto.clicked.connect(lambda: self.run_job('relocalize', self.node.relocalize))
        brow = QHBoxLayout()
        for b in (self.b_plan, self.b_go, self.b_stop):
            brow.addWidget(b)
        brow2 = QHBoxLayout()
        for b in (self.b_home, self.b_auto):
            brow2.addWidget(b)

        # ---- route table + log
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Leg', 'From -> to', 'Length (m)'])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.summary = QLabel('No route planned.')
        self.summary.setWordWrap(True)
        self.state = QLabel('Connecting to the robot...')
        self.state.setStyleSheet('font-weight:bold')
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.addWidget(self.state)
        rl.addWidget(box)
        rl.addLayout(brow)
        rl.addLayout(brow2)
        rl.addWidget(self.summary)
        rl.addWidget(self.table, 2)
        rl.addWidget(QLabel('Log'))
        rl.addWidget(self.log, 3)
        # ---- robot vision: camera with detections and navigation
        self.cam = QLabel('waiting for the camera ...')
        self.cam.setAlignment(Qt.AlignCenter)
        self.cam.setMinimumSize(320, 240)
        self.cam.setStyleSheet('background:#202020;color:#ddd')
        self.overlay = VisionOverlay(node.marker_info, node.doc.get('dictionary', 'DICT_4X4_50'),
                                     tuple(node.gp('camera_offset')))
        self.static_map = StaticMap.from_grid(node.static_grid)
        self.detector = make_detector(node.gp('detector'), node.gp('yolo_model'),
                                      log=lambda t: log_queue.put(t))
        self.cam_lock = threading.Lock()
        self.cam_img = None
        self.cam_new = False
        node.create_subscription(Image, node.gp('image_topic'), self._cam_cb,
                                 qos_profile_sensor_data)
        self.status_line = ''
        left = QSplitter(Qt.Vertical)
        left.addWidget(self.map)
        left.addWidget(self.cam)
        left.setStretchFactor(0, 3)
        left.setStretchFactor(1, 2)

        split = QSplitter()
        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        self.setCentralWidget(split)
        self.resize(1400, 850)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(100)
        self.set_busy(True)
        self.run_job('startup', self._startup)

    # ---------------------------------------------------------- helpers
    def name_of(self, token):
        token = token.strip()
        if not token:
            return None
        if token.lower() in ('h', 'home'):
            return 'home' if 'home' in self.node.points else None
        return self.node.resolve(token)

    def add_stop_from_map(self, name):
        if name == 'home':
            return
        cur = self.stops_edit.text().strip()
        num = str(self.names.index(name) + 1)
        self.stops_edit.setText(f'{cur}, {num}' if cur else num)

    def parse_quick(self):
        toks = [t for t in re.split(r'[\s,;>\-]+', self.quick.text()) if t]
        names = [self.name_of(t) for t in toks]
        bad = [t for t, n in zip(toks, names) if n is None]
        if bad or len(names) < 2:
            QMessageBox.warning(self, 'Mission', 'Give at least a start and an end, '
                                'e.g. "3 4 6 7 5".' + (f'\nUnknown: {", ".join(bad)}' if bad else ''))
            return
        self.start_cb.setCurrentIndex(self.start_cb.findData(names[0]))
        self.end_cb.setCurrentIndex(self.end_cb.findData(names[-1]))
        self.stops_edit.setText(', '.join(str(self.names.index(n) + 1) for n in names[1:-1]))
        self.plan()

    def mission(self):
        start = self.start_cb.currentData() or ''
        end = self.end_cb.currentData() or ''
        toks = [t for t in re.split(r'[\s,;]+', self.stops_edit.text()) if t]
        stops = []
        for t in toks:
            n = self.name_of(t)
            if n is None:
                raise ValueError(f'unknown stop {t!r}')
            if n != 'home' and n not in stops:
                stops.append(n)
        if not stops and not (start and end and start != end):
            raise ValueError('add at least one stop (or a different start and end)')
        return start, stops, end

    def set_busy(self, busy):
        for b in (self.b_plan, self.b_go, self.b_home, self.b_auto):
            b.setEnabled(not busy and self.ready)
        self.b_stop.setEnabled(True)

    def run_job(self, label, fn, *args):
        if self.worker is not None and self.worker.is_alive():
            QMessageBox.information(self, 'Busy', 'The robot is busy; press STOP first.')
            return

        def job():
            try:
                fn(*args)
            except MissionAborted:
                self.log_queue.put(f'{label}: STOPPED by the user')
            except Exception as exc:  # noqa: BLE001
                self.log_queue.put(f'{label} failed: {exc}')
            finally:
                try:
                    self.node.stop()
                except Exception:  # noqa: BLE001
                    pass
        self.node.abort_event.clear()
        self.worker = threading.Thread(target=job, daemon=True)
        self.worker.start()
        self.set_busy(True)

    # ---------------------------------------------------------- robot jobs
    def _startup(self):
        if not self.node.wait_for_sensors():
            self.log_queue.put('No sensor data: is the simulation running?')
            return
        self.node.set_initial_pose()
        self.ready = True
        self.log_queue.put('Ready. Enter a mission, e.g. 3 4 6 7 5, then Plan / Start.')

    def _set_home(self):
        with self.node.lock:
            self.node.ekf.set_pose(self.node.home, sigma=(0.1, 0.1, 0.05))
        self.log_queue.put('Pose set to home')

    def _show_tour(self, tour):
        self.map.route = list(tour['approach']) + list(tour['path'])
        self.map.approach_len = max(len(tour['approach']) - 1, 0)
        hl = {}
        if tour.get('start') in self.node.points:
            hl[tour['start']] = 'A'
        for i, n in enumerate(tour['order'], 1):
            hl[n] = f'#{i}'
        if tour.get('end') in self.node.points:
            hl[tour['end']] = (hl.get(tour['end'], '') + ' B').strip()
        self.map.highlight = hl
        rows = []
        if tour['approach_length'] > 0:
            rows.append(('0', f'robot -> {tour["start"]}', tour['approach_length']))
        for i, (a, b, d) in enumerate(tour['legs'], 1):
            rows.append((str(i), f'{a} -> {b}', d))
        self.table.setRowCount(len(rows))
        for r, (leg, txt, d) in enumerate(rows):
            for c, v in enumerate((leg, txt, f'{d:.1f}')):
                self.table.setItem(r, c, QTableWidgetItem(v))
        nums = ' -> '.join(str(self.names.index(n) + 1) if n in self.names else n
                           for n in [tour['start']] + tour['order'] + [tour['end']])
        self.summary.setText(
            f'Order: {nums}<br>Total {tour["total"] + tour["approach_length"]:.1f} m '
            f'(tour {tour["total"]:.1f} m; the stops in the typed order: '
            f'{tour["given_total"]:.1f} m). Dijkstra + exact order in {tour["seconds"]:.2f} s.')
        self.map.update()

    def plan(self):
        try:
            start, stops, end = self.mission()
            tour = self.node.preview_tour(start, stops, end, self.opt.isChecked())
        except ValueError as exc:
            QMessageBox.warning(self, 'Route', str(exc))
            return None
        self._show_tour(tour)
        return tour

    def start_mission(self):
        tour = self.plan()
        if tour is None:
            return
        start, stops, end = self.mission()
        self.map.trail = []
        self.run_job('mission', self.node.run_tour, start, stops, end,
                     self.opt.isChecked(), self.deliver_start.isChecked())

    def stop_mission(self):
        self.node.abort_event.set()
        threading.Thread(target=self.node.stop, daemon=True).start()
        self.log_queue.put('STOP pressed')

    # ---------------------------------------------------------- vision
    def _cam_cb(self, msg):
        try:
            bgr = image_to_bgr(msg)
        except ValueError:
            return
        with self.cam_lock:
            self.cam_img = bgr
            self.cam_new = True
        if self.detector:
            self.detector.push(bgr)

    def _ray(self, bearing):
        with self.node.lock:
            sb = self.node.scan_base
            ok = self.node.scan_valid
        if sb is None:
            return None
        pts = sb[ok]
        b = np.arctan2(pts[:, 1], pts[:, 0])
        k = np.abs(np.arctan2(np.sin(b - bearing), np.cos(b - bearing))) < 0.03
        return float(np.hypot(pts[k, 0], pts[k, 1]).min()) if k.any() else None

    def draw_camera(self):
        with self.cam_lock:
            if not self.cam_new or self.cam_img is None:
                return
            img, self.cam_new = self.cam_img, False
        node = self.node
        if node.K is None:
            return
        with node.lock:
            sb = None if node.scan_base is None else node.scan_base[node.scan_valid]
        path = list(node.current_path) if (self.worker and self.worker.is_alive()) else []
        try:
            pose = node.pose()
        except Exception:  # noqa: BLE001
            pose = None
        out, _ = self.overlay.draw(img, node.K, node.D, sb, pose, path,
                                   path[-1] if path else None, self.status_line,
                                   node.last_cmd,
                                   self.detector.boxes() if self.detector else None,
                                   self._ray, self.static_map)
        pix = QPixmap.fromImage(bgr_to_qimage(out))
        self.cam.setPixmap(pix.scaled(self.cam.width(), self.cam.height(), Qt.KeepAspectRatio,
                                      Qt.SmoothTransformation))

    # ---------------------------------------------------------- UI loop
    def tick(self):
        while True:
            try:
                msg = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log.appendPlainText(msg)
            self.status_line = msg.split('\n')[0]
        self.draw_camera()
        busy = self.worker is not None and self.worker.is_alive()
        self.set_busy(busy)
        try:
            x, y, th = self.node.pose()
            if busy and (not self.map.trail or
                         math.hypot(x - self.map.trail[-1][0], y - self.map.trail[-1][1]) > 0.1):
                self.map.trail.append((x, y))
            state = 'Driving / delivering' if busy and self.ready else \
                ('Ready' if self.ready else 'Connecting to the robot...')
            self.state.setText(f'{state}   |   pose ({x:.2f}, {y:.2f}, '
                               f'{math.degrees(th):.0f} deg)')
        except Exception:  # noqa: BLE001
            pass
        self.map.update()

    def closeEvent(self, ev):
        self.stop_mission()
        ev.accept()


def main(args=None):
    rclpy.init(args=args if args is not None else sys.argv,
               signal_handler_options=SignalHandlerOptions.NO)
    log_queue = queue.Queue()
    node = GuiNavigator(log_queue)
    executor, _ = spin_in_background(node)
    app = QApplication([sys.argv[0]])
    win = DeliveryWindow(node, log_queue)
    win.show()
    # Ctrl+C in the terminal closes the window
    import signal
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    keep = QTimer()
    keep.timeout.connect(lambda: None)      # lets Python see the signal
    keep.start(200)
    try:
        app.exec_()
    finally:
        node.abort_event.set()
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
