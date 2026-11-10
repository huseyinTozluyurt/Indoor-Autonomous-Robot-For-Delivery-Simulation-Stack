"""PyQt5 teleoperation GUI for the indoor delivery robot.

Publishes geometry_msgs/Twist on /cmd_vel (twist_to_stamped_bridge forwards it
to the diff_drive_controller) and shows odometry from the controller.

ROS is serviced from a QTimer with spin_once(), so everything runs in the Qt
main thread: no locks, no cross-thread widget access.
"""
import math
import sys

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QSlider, QVBoxLayout, QWidget,
)

# Must stay within config/rb1_diff_drive_controllers.yaml limits.
MAX_LINEAR = 0.8   # m/s
MAX_ANGULAR = 1.5  # rad/s
PUBLISH_HZ = 20    # keep well above 1 / cmd_vel_timeout (0.5 s)


class TeleopNode(Node):
    def __init__(self):
        super().__init__('pyqt_teleop')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('odom_topic', '/robot/diff_drive_controller/odom')
        cmd_topic = self.get_parameter('cmd_vel_topic').value
        odom_topic = self.get_parameter('odom_topic').value

        self.cmd_pub = self.create_publisher(Twist, cmd_topic, 10)
        self.odom = None
        self.create_subscription(
            Odometry, odom_topic, self._odom_cb, qos_profile_sensor_data)
        self.get_logger().info(
            f'Publishing Twist on {cmd_topic}, reading odom from {odom_topic}')

    def _odom_cb(self, msg: Odometry):
        self.odom = msg

    def send(self, linear: float, angular: float):
        msg = Twist()
        msg.linear.x = float(linear)
        msg.angular.z = float(angular)
        self.cmd_pub.publish(msg)


class TeleopWindow(QWidget):
    # (linear sign, angular sign) per button
    DIRECTIONS = {
        'forward': (1, 0), 'backward': (-1, 0),
        'left': (0, 1), 'right': (0, -1),
        'fwd_left': (1, 1), 'fwd_right': (1, -1),
    }
    KEYS = {
        Qt.Key_W: 'forward', Qt.Key_Up: 'forward',
        Qt.Key_S: 'backward', Qt.Key_Down: 'backward',
        Qt.Key_A: 'left', Qt.Key_Left: 'left',
        Qt.Key_D: 'right', Qt.Key_Right: 'right',
        Qt.Key_Q: 'fwd_left', Qt.Key_E: 'fwd_right',
    }

    def __init__(self, node: TeleopNode):
        super().__init__()
        self.node = node
        self.active = None       # direction currently held, or None
        self.estopped = False

        self.setWindowTitle('Indoor Delivery Robot - Teleop')
        self.setFocusPolicy(Qt.StrongFocus)
        layout = QVBoxLayout(self)

        # Direction pad (press and hold)
        pad_box = QGroupBox('Drive (hold a button, or W/A/S/D/Q/E / arrow keys)')
        pad = QGridLayout(pad_box)
        buttons = {
            'fwd_left': ('↖', 0, 0), 'forward': ('↑', 0, 1),
            'fwd_right': ('↗', 0, 2), 'left': ('←', 1, 0),
            'right': ('→', 1, 2), 'backward': ('↓', 2, 1),
        }
        for name, (label, row, col) in buttons.items():
            btn = QPushButton(label)
            btn.setMinimumSize(70, 55)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.pressed.connect(lambda n=name: self._set_active(n))
            btn.released.connect(lambda: self._set_active(None))
            pad.addWidget(btn, row, col)
        stop_btn = QPushButton('■')
        stop_btn.setMinimumSize(70, 55)
        stop_btn.setFocusPolicy(Qt.NoFocus)
        stop_btn.clicked.connect(lambda: self._set_active(None))
        pad.addWidget(stop_btn, 1, 1)
        layout.addWidget(pad_box)

        # Speed sliders
        speed_box = QGroupBox('Speed limits')
        speed = QGridLayout(speed_box)
        self.lin_slider, self.lin_label = self._slider(40)
        self.ang_slider, self.ang_label = self._slider(40)
        speed.addWidget(QLabel('Linear'), 0, 0)
        speed.addWidget(self.lin_slider, 0, 1)
        speed.addWidget(self.lin_label, 0, 2)
        speed.addWidget(QLabel('Angular'), 1, 0)
        speed.addWidget(self.ang_slider, 1, 1)
        speed.addWidget(self.ang_label, 1, 2)
        layout.addWidget(speed_box)

        # E-stop
        row = QHBoxLayout()
        self.estop_btn = QPushButton('EMERGENCY STOP')
        self.estop_btn.setCheckable(True)
        self.estop_btn.setFocusPolicy(Qt.NoFocus)
        self.estop_btn.setMinimumHeight(45)
        self.estop_btn.setStyleSheet(
            'QPushButton{background:#c62828;color:white;font-weight:bold}'
            'QPushButton:checked{background:#555;}')
        self.estop_btn.toggled.connect(self._toggle_estop)
        row.addWidget(self.estop_btn)
        layout.addLayout(row)

        # Status
        self.cmd_label = QLabel()
        self.odom_label = QLabel('Odometry: waiting for /robot/diff_drive_controller/odom ...')
        layout.addWidget(self.cmd_label)
        layout.addWidget(self.odom_label)

        # Timers: ROS servicing + fixed-rate command publishing
        self.ros_timer = QTimer(self)
        self.ros_timer.timeout.connect(self._spin_ros)
        self.ros_timer.start(10)
        self.pub_timer = QTimer(self)
        self.pub_timer.timeout.connect(self._publish)
        self.pub_timer.start(int(1000 / PUBLISH_HZ))
        self._update_slider_labels()

    def _slider(self, initial_percent):
        s = QSlider(Qt.Horizontal)
        s.setRange(0, 100)
        s.setValue(initial_percent)
        s.setFocusPolicy(Qt.NoFocus)
        s.valueChanged.connect(self._update_slider_labels)
        return s, QLabel()

    def _update_slider_labels(self):
        self.lin_label.setText(f'{self._lin_speed():.2f} m/s')
        self.ang_label.setText(f'{self._ang_speed():.2f} rad/s')

    def _lin_speed(self):
        return MAX_LINEAR * self.lin_slider.value() / 100.0

    def _ang_speed(self):
        return MAX_ANGULAR * self.ang_slider.value() / 100.0

    def _set_active(self, direction):
        self.active = direction

    def _toggle_estop(self, on):
        self.estopped = on
        self.active = None
        self.estop_btn.setText('E-STOP ACTIVE (click to release)' if on else 'EMERGENCY STOP')
        self.node.send(0.0, 0.0)

    def _spin_ros(self):
        if rclpy.ok():
            rclpy.spin_once(self.node, timeout_sec=0.0)
        odom = self.node.odom
        if odom is not None:
            p = odom.pose.pose.position
            q = odom.pose.pose.orientation
            yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                             1.0 - 2.0 * (q.y * q.y + q.z * q.z))
            v = odom.twist.twist
            self.odom_label.setText(
                f'Odom  x={p.x:.2f} m  y={p.y:.2f} m  yaw={math.degrees(yaw):.1f}°   '
                f'v={v.linear.x:.2f} m/s  w={v.angular.z:.2f} rad/s')

    def _publish(self):
        lin = ang = 0.0
        if self.active and not self.estopped:
            ls, as_ = self.DIRECTIONS[self.active]
            lin, ang = ls * self._lin_speed(), as_ * self._ang_speed()
        self.node.send(lin, ang)
        state = 'E-STOP' if self.estopped else (self.active or 'stopped')
        self.cmd_label.setText(f'Command: {state}   linear={lin:.2f}  angular={ang:.2f}')

    # Keyboard control
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.active = None
        elif event.key() in self.KEYS and not event.isAutoRepeat():
            self.active = self.KEYS[event.key()]
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() in self.KEYS and not event.isAutoRepeat():
            if self.active == self.KEYS[event.key()]:
                self.active = None
        else:
            super().keyReleaseEvent(event)

    def focusOutEvent(self, event):
        # Never keep driving if the window loses focus mid key-press.
        self.active = None
        super().focusOutEvent(event)

    def closeEvent(self, event):
        self.pub_timer.stop()
        self.ros_timer.stop()
        for _ in range(3):
            self.node.send(0.0, 0.0)
        super().closeEvent(event)


def main(args=None):
    rclpy.init(args=args)
    node = TeleopNode()
    app = QApplication(sys.argv)
    window = TeleopWindow(node)
    window.show()
    try:
        exit_code = app.exec_()
    finally:
        node.send(0.0, 0.0)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
