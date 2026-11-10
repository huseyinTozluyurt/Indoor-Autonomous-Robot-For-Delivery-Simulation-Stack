"""Gazebo sim + slam_toolbox (online async mapping) + RViz.

    ros2 launch indoor_delivery_project slam.launch.py
    ros2 run indoor_delivery_project pyqt_teleop      # drive to build the map
    ros2 run nav2_map_server map_saver_cli -f ~/maps/campus --ros-args -p use_sim_time:=true

Set sim:=false to run only slam_toolbox + RViz (e.g. against a bag or the
real robot; then also pass use_sim_time:=false).
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    project_pkg = get_package_share_directory('indoor_delivery_project')
    slam_pkg = get_package_share_directory('slam_toolbox')

    use_sim_time = LaunchConfiguration('use_sim_time')
    slam_params_file = LaunchConfiguration('slam_params_file')

    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(project_pkg, 'launch', 'sim.launch.py')
        ),
        condition=IfCondition(LaunchConfiguration('sim')),
    )

    # slam_toolbox's own launch handles the lifecycle configure/activate.
    slam = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(slam_pkg, 'launch', 'online_async_launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'slam_params_file': slam_params_file,
        }.items()
    )

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', os.path.join(project_pkg, 'config', 'slam.rviz')],
        parameters=[{'use_sim_time': use_sim_time}],
        condition=IfCondition(LaunchConfiguration('rviz')),
    )

    return LaunchDescription([
        DeclareLaunchArgument('sim', default_value='true',
                              description='Also start Gazebo + robot (sim.launch.py)'),
        DeclareLaunchArgument('rviz', default_value='true',
                              description='Start RViz with config/slam.rviz'),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument(
            'slam_params_file',
            default_value=os.path.join(project_pkg, 'config', 'slam_toolbox_mapping.yaml'),
            description='slam_toolbox parameters'),
        sim,
        slam,
        rviz,
    ])
