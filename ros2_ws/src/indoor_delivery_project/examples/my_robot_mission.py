#!/usr/bin/env python3
"""Example: script your own robot mission with the built-in commands.

Run (simulation already started with `ros2 launch indoor_delivery_project sim.launch.py`):

    cd ~/ros2_jazzy_ws && source install/setup.bash
    python3 src/indoor_delivery_project/examples/my_robot_mission.py

Copy this file anywhere and edit it: it only needs the workspace sourced.
"""
from indoor_delivery_project.robot_commands import MotionTimeout, Robot


def main():
    # use_sim_time=True for Gazebo. On the real robot: Robot(use_sim_time=False,
    # odom_topic='/odom') or whatever topics the real base publishes.
    with Robot(linear_speed=0.3, angular_speed=0.6) as robot:
        print('start pose (x, y, yaw_deg):', robot.get_pose())

        # 1) Drive a 1 m square
        for _ in range(4):
            robot.forward(1.0)        # metres
            robot.turn_left(90)       # degrees

        # 2) Back up a bit, turn right, timed moves
        robot.backward(0.5)
        robot.turn_right(45)
        robot.forward_for(2.0)        # seconds at linear_speed
        robot.turn_left_for(1.0, speed=0.5)

        # 3) Go back to where we started (odom frame) and face the start heading
        robot.go_to(0.0, 0.0)
        robot.turn_to(0.0)

        # 4) ArUco: look around for marker 10 (needs aruco_detector, on by default)
        det = robot.search_marker(10, max_degrees=360)
        if det:
            print(f"found marker {det['id']} ({det['name']}) "
                  f"at {det.get('distance_m', '?')} m")
        else:
            print('marker 10 not visible from here')

        print('end pose:', robot.get_pose())


if __name__ == '__main__':
    try:
        main()
    except MotionTimeout as exc:
        print('motion timed out:', exc)
    except KeyboardInterrupt:
        pass  # Robot.__exit__ already stopped the robot
