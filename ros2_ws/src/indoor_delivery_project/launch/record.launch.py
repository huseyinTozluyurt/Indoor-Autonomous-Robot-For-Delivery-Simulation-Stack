"""Record the robot's surroundings: rosbag2 of sensors + an .mp4 of the camera.

    ros2 launch indoor_delivery_project record.launch.py
    ros2 launch indoor_delivery_project record.launch.py bag:=false video_topic:=/aruco_detector/annotated

Files go to <output_dir>/bag_<time>/ and <output_dir>/robot_camera_<time>.mp4.
Stop with Ctrl+C (the bag and the video are closed cleanly).
"""
import os
from datetime import datetime

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

BAG_TOPICS = [
    '/robot/aruco_camera/image_raw',
    '/robot/aruco_camera/camera_info',
    '/robot/front_laser/scan',
    '/robot/imu/data',
    '/robot/diff_drive_controller/odom',
    '/aruco_detector/detections',
    '/aruco_detector/poses',
    '/robot/current_room',
    '/tf',
    '/tf_static',
    '/clock',
]


def _bag(context):
    out = os.path.expanduser(LaunchConfiguration('output_dir').perform(context))
    os.makedirs(out, exist_ok=True)
    bag_dir = os.path.join(out, 'bag_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    return [ExecuteProcess(
        cmd=['ros2', 'bag', 'record', '--use-sim-time', '-s', 'mcap',
             '-o', bag_dir] + BAG_TOPICS,
        output='screen',
        condition=IfCondition(LaunchConfiguration('bag')),
    )]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('output_dir', default_value='~/robot_recordings'),
        DeclareLaunchArgument('bag', default_value='true',
                              description='Record a rosbag2 (mcap) of the sensors'),
        DeclareLaunchArgument('video', default_value='true',
                              description='Record the camera to an .mp4'),
        DeclareLaunchArgument('video_topic',
                              default_value='/robot/aruco_camera/image_raw'),
        DeclareLaunchArgument('fps', default_value='15.0'),

        OpaqueFunction(function=_bag),
        Node(
            package='indoor_delivery_project',
            executable='video_recorder',
            name='video_recorder',
            output='screen',
            condition=IfCondition(LaunchConfiguration('video')),
            parameters=[{
                'use_sim_time': True,
                'image_topic': LaunchConfiguration('video_topic'),
                'output_dir': LaunchConfiguration('output_dir'),
                'fps': LaunchConfiguration('fps'),
            }],
        ),
    ])
