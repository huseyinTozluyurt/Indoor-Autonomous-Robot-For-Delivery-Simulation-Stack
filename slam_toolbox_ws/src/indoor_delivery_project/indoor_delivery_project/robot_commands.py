"""Built-in motion commands for the indoor delivery robot.

Blocking, easy-to-script functions that drive the robot by distance, angle or
time. Distances and angles are closed-loop on wheel odometry
(/robot/diff_drive_controller/odom), so `forward(1.0)` really stops after ~1 m.
If no odometry arrives, the commands fall back to timed (open-loop) motion.

Quick use (after `source install/setup.bash`, with sim.launch.py running):

    from indoor_delivery_project.robot_commands import Robot

    with Robot() as robot:
        robot.forward(1.0)        # metres
        robot.turn_left(90)       # degrees
        robot.backward(0.5)
        robot.turn_right(45)
        robot.forward_for(2.0)    # seconds
        print(robot.get_pose())   # (x, y, yaw_deg) in the odom frame

Or the module-level shortcuts, which share one hidden Robot:

    from indoor_delivery_project.robot_commands import (
        forward, backward, turn_left, turn_right, stop, shutdown)
    forward(1.0); turn_left(90); shutdown()

Velocity commands go to /cmd_vel (geometry_msgs/Twist); sim.launch.py's
twist_to_stamped_bridge forwards them to the diff drive controller. For the
real robot pass use_sim_time=False and its own cmd_vel/odom topics.
"""
import math
import time

import rclpy
from geometry_msgs.msg import Twist, TwistStamped
from nav_msgs.msg import Odometry
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data

__all__ = [
    'Robot', 'MotionTimeout',
    'forward', 'backward', 'turn_left', 'turn_right', 'turn', 'turn_to', 'go_to',
    'forward_for', 'backward_for', 'turn_left_for', 'turn_right_for', 'drive',
    'stop', 'get_pose', 'sleep', 'shutdown',
]

# Limits from config/rb1_diff_drive_controllers.yaml
MAX_LINEAR = 0.8    # m/s
MAX_ANGULAR = 1.5   # rad/s


class MotionTimeout(RuntimeError):
    """A command did not reach its goal in time (robot blocked, sim paused...)."""


def _yaw_from_quaternion(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def _wrap(angle):
    """Wrap an angle to [-pi, pi]."""
    return math.atan2(math.sin(angle), math.cos(angle))


def _clamp(value, low, high):
    return max(low, min(high, value))


class Robot:
    """Blocking motion commands. One instance = one small ROS 2 node.

    Args:
        cmd_vel_topic: where velocity commands go.
        odom_topic: nav_msgs/Odometry used for distance/angle feedback.
        use_sim_time: True for Gazebo, False on the real robot.
        linear_speed: default forward/backward speed in m/s.
        angular_speed: default turning speed in rad/s.
        stamped: publish TwistStamped instead of Twist (e.g. straight to
            /robot/diff_drive_controller/cmd_vel without the bridge).
        wait_for_odom: seconds to wait for odometry at start-up.
    """

    def __init__(self,
                 cmd_vel_topic='/cmd_vel',
                 odom_topic='/robot/diff_drive_controller/odom',
                 use_sim_time=True,
                 linear_speed=0.3,
                 angular_speed=0.6,
                 stamped=False,
                 rate_hz=20.0,
                 wait_for_odom=5.0,
                 node_name='robot_commands'):
        self._owns_rclpy = not rclpy.ok()
        if self._owns_rclpy:
            rclpy.init()
        self.node = Node(node_name, parameter_overrides=[
            Parameter('use_sim_time', Parameter.Type.BOOL, bool(use_sim_time))])
        self.log = self.node.get_logger()
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self.node)

        self.linear_speed = linear_speed
        self.angular_speed = angular_speed
        self.period = 1.0 / rate_hz
        self.distance_tolerance = 0.01            # m
        self.angle_tolerance = math.radians(1.0)  # rad
        self.min_linear = 0.04                    # m/s, creeping speed near goal
        self.min_angular = 0.12                   # rad/s
        self.heading_gain = 1.5                   # keeps straight lines straight

        self._stamped = stamped
        self._pub = self.node.create_publisher(
            TwistStamped if stamped else Twist, cmd_vel_topic, 10)
        self._pose = None   # (x, y, yaw) in the odom frame
        self.node.create_subscription(
            Odometry, odom_topic, self._odom_cb, qos_profile_sensor_data)

        self._closed = False
        self._use_sim_time = bool(use_sim_time)
        if self._use_sim_time:
            self._wait(lambda: self.node.get_clock().now().nanoseconds > 0, 5.0,
                       'No /clock yet: is the simulation running?')
        self.has_odom = self._wait(lambda: self._pose is not None, wait_for_odom,
                                   f'No odometry on {odom_topic}: distance/angle '
                                   'commands will be timed (open loop).')
        self.log.info(f'Robot ready: cmd_vel={cmd_vel_topic} odom={odom_topic} '
                      f'(odometry {"ok" if self.has_odom else "missing"})')

    # ------------------------------------------------------------------ ROS
    def _odom_cb(self, msg):
        p = msg.pose.pose
        self._pose = (p.position.x, p.position.y, _yaw_from_quaternion(p.orientation))

    def _spin_for(self, seconds):
        """Process callbacks for `seconds` of wall time."""
        end = time.monotonic() + seconds
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                return
            self._executor.spin_once(timeout_sec=remaining)

    def _wait(self, condition, timeout, warning):
        end = time.monotonic() + timeout
        while not condition():
            if time.monotonic() > end:
                self.log.warning(warning)
                return False
            self._executor.spin_once(timeout_sec=0.05)
        return True

    def _now(self):
        """Seconds on the node clock (sim time in Gazebo)."""
        return self.node.get_clock().now().nanoseconds * 1e-9

    def _publish(self, linear, angular):
        linear = _clamp(linear, -MAX_LINEAR, MAX_LINEAR)
        angular = _clamp(angular, -MAX_ANGULAR, MAX_ANGULAR)
        if self._stamped:
            msg = TwistStamped()
            msg.header.stamp = self.node.get_clock().now().to_msg()
            msg.header.frame_id = 'base_link'
            twist = msg.twist
        else:
            msg = twist = Twist()
        twist.linear.x = float(linear)
        twist.angular.z = float(angular)
        self._pub.publish(msg)

    def _check_timeout(self, start_wall, timeout, what):
        if time.monotonic() - start_wall > timeout:
            self.stop()
            raise MotionTimeout(f'{what} did not finish within {timeout:.1f} s')

    # -------------------------------------------------------------- queries
    def get_pose(self):
        """(x, y, yaw_degrees) in the odom frame, or None without odometry."""
        self._executor.spin_once(timeout_sec=0.0)
        if self._pose is None:
            return None
        x, y, yaw = self._pose
        return (x, y, math.degrees(yaw))

    # ------------------------------------------------------- basic commands
    def stop(self):
        """Stop the robot (sends zero velocity a few times to be sure)."""
        for _ in range(3):
            self._publish(0.0, 0.0)
            self._spin_for(0.03)

    def sleep(self, seconds):
        """Wait while keeping ROS callbacks (odometry) running."""
        self._spin_for(seconds)

    def drive(self, linear, angular, duration):
        """Drive with velocity (m/s, rad/s) for `duration` seconds, then stop."""
        if self._use_sim_time:
            # Sim seconds, so the result does not depend on the real-time factor.
            t0 = self._now()
            wall0 = time.monotonic()
            while self._now() - t0 < duration:
                self._publish(linear, angular)
                self._spin_for(self.period)
                self._check_timeout(wall0, 10.0 * duration + 10.0, 'drive()')
        else:
            end = time.monotonic() + duration
            while time.monotonic() < end:
                self._publish(linear, angular)
                self._spin_for(self.period)
        self.stop()

    def forward_for(self, seconds, speed=None):
        self.drive(abs(speed or self.linear_speed), 0.0, seconds)

    def backward_for(self, seconds, speed=None):
        self.drive(-abs(speed or self.linear_speed), 0.0, seconds)

    def turn_left_for(self, seconds, speed=None):
        self.drive(0.0, abs(speed or self.angular_speed), seconds)

    def turn_right_for(self, seconds, speed=None):
        self.drive(0.0, -abs(speed or self.angular_speed), seconds)

    # ---------------------------------------------- distance / angle (odom)
    def forward(self, distance, speed=None, timeout=None):
        """Drive `distance` metres forward. Returns the distance travelled."""
        return self.move(abs(distance), speed, timeout)

    def backward(self, distance, speed=None, timeout=None):
        """Drive `distance` metres backward. Returns the distance travelled."""
        return -self.move(-abs(distance), speed, timeout)

    def move(self, distance, speed=None, timeout=None):
        """Drive a signed distance (positive = forward), holding the heading."""
        speed = _clamp(abs(speed or self.linear_speed), self.min_linear, MAX_LINEAR)
        direction = 1.0 if distance >= 0 else -1.0
        distance = abs(distance)
        if distance < 1e-3:
            return 0.0
        if not self.has_odom:
            self.drive(direction * speed, 0.0, distance / speed)
            return direction * distance

        timeout = timeout or 3.0 * distance / speed + 5.0
        x0, y0, yaw0 = self._pose
        wall0 = time.monotonic()
        try:
            while True:
                x, y, yaw = self._pose
                travelled = math.hypot(x - x0, y - y0)
                remaining = distance - travelled
                if remaining <= self.distance_tolerance:
                    break
                self._check_timeout(wall0, timeout, f'move({direction * distance:.2f} m)')
                v = _clamp(1.5 * remaining, self.min_linear, speed)
                w = _clamp(-self.heading_gain * _wrap(yaw - yaw0), -0.3, 0.3)
                self._publish(direction * v, w)
                self._spin_for(self.period)
        finally:
            self.stop()
        x, y, _ = self._pose
        return direction * math.hypot(x - x0, y - y0)

    def turn_left(self, degrees=90.0, speed=None, timeout=None):
        """Turn counter-clockwise by `degrees`. Returns degrees turned."""
        return self.turn(abs(degrees), speed, timeout)

    def turn_right(self, degrees=90.0, speed=None, timeout=None):
        """Turn clockwise by `degrees`. Returns degrees turned (negative)."""
        return self.turn(-abs(degrees), speed, timeout)

    def turn(self, degrees, speed=None, timeout=None):
        """Turn in place by a signed angle (positive = left / CCW).

        Angles above 180 work too (turn(360) does a full circle).
        """
        speed = _clamp(abs(speed or self.angular_speed), self.min_angular, MAX_ANGULAR)
        target = math.radians(degrees)
        if abs(target) < 1e-3:
            return 0.0
        if not self.has_odom:
            self.drive(0.0, math.copysign(speed, target), abs(target) / speed)
            return degrees

        timeout = timeout or 3.0 * abs(target) / speed + 5.0
        last_yaw = self._pose[2]
        turned = 0.0
        wall0 = time.monotonic()
        try:
            while True:
                yaw = self._pose[2]
                turned += _wrap(yaw - last_yaw)
                last_yaw = yaw
                remaining = target - turned
                if abs(remaining) <= self.angle_tolerance:
                    break
                self._check_timeout(wall0, timeout, f'turn({degrees:.1f} deg)')
                w = math.copysign(_clamp(2.0 * abs(remaining), self.min_angular, speed),
                                  remaining)
                self._publish(0.0, w)
                self._spin_for(self.period)
        finally:
            self.stop()
        return math.degrees(turned)

    def turn_to(self, heading_degrees, speed=None, timeout=None):
        """Turn to an absolute heading in the odom frame (0 = start heading)."""
        if not self.has_odom:
            raise RuntimeError('turn_to() needs odometry')
        error = _wrap(math.radians(heading_degrees) - self._pose[2])
        return self.turn(math.degrees(error), speed, timeout)

    def go_to(self, x, y, speed=None, timeout=None):
        """Turn towards (x, y) in the odom frame and drive there."""
        if not self.has_odom:
            raise RuntimeError('go_to() needs odometry')
        x0, y0, _ = self._pose
        dx, dy = x - x0, y - y0
        if math.hypot(dx, dy) < self.distance_tolerance:
            return
        self.turn_to(math.degrees(math.atan2(dy, dx)), timeout=timeout)
        x0, y0, _ = self._pose
        self.forward(math.hypot(x - x0, y - y0), speed, timeout)

    # ------------------------------------------------------------ cleanup
    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.stop()
        finally:
            self._executor.remove_node(self.node)
            self.node.destroy_node()
            if self._owns_rclpy and rclpy.ok():
                rclpy.shutdown()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


# ------------------------------------------------- module-level shortcuts
_default_robot = None


def _robot():
    global _default_robot
    if _default_robot is None:
        _default_robot = Robot()
    return _default_robot


def forward(distance, speed=None):
    return _robot().forward(distance, speed)


def backward(distance, speed=None):
    return _robot().backward(distance, speed)


def turn_left(degrees=90.0, speed=None):
    return _robot().turn_left(degrees, speed)


def turn_right(degrees=90.0, speed=None):
    return _robot().turn_right(degrees, speed)


def turn(degrees, speed=None):
    return _robot().turn(degrees, speed)


def turn_to(heading_degrees, speed=None):
    return _robot().turn_to(heading_degrees, speed)


def go_to(x, y, speed=None):
    return _robot().go_to(x, y, speed)


def forward_for(seconds, speed=None):
    return _robot().forward_for(seconds, speed)


def backward_for(seconds, speed=None):
    return _robot().backward_for(seconds, speed)


def turn_left_for(seconds, speed=None):
    return _robot().turn_left_for(seconds, speed)


def turn_right_for(seconds, speed=None):
    return _robot().turn_right_for(seconds, speed)


def drive(linear, angular, duration):
    return _robot().drive(linear, angular, duration)


def stop():
    return _robot().stop()


def get_pose():
    return _robot().get_pose()


def sleep(seconds):
    return _robot().sleep(seconds)


def shutdown():
    """Stop the robot and release the shared node."""
    global _default_robot
    if _default_robot is not None:
        _default_robot.close()
        _default_robot = None
