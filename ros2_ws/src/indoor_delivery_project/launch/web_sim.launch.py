"""Everything in one command: Gazebo simulation + web_bridge + DeliveryBot web
application (Spring Boot backend + React/Vite frontend).

    ros2 launch indoor_delivery_project web_sim.launch.py

Then open http://localhost:5173 , Robot Settings -> "Use Gazebo Simulation".
Ctrl+C stops everything (Gazebo, the bridge, the backend and the frontend).

Arguments (name:=value):
  world        two_buildings      world of the map (campus_full_map7 was made in two_buildings)
  map_dir      ~/ros2_jazzy_ws/maps/campus_full_map7   (run_web_sim.sh passes <repo>/maps/campus_full_map7)
  webapp_dir   ~/Downloads/WebApplication/Back-Front   (run_web_sim.sh passes <repo>/web_app;
                                                        needs backend/ and frontend/)
  webapp       true               false = only simulation + web_bridge (run the app yourself)
  gui          true               false = Gazebo without window (faster)
  rtf          1.0                simulation speed (real_time_factor)
  aruco        true               extra ArUco detector node (only for its annotated image)
  bridge_port  5000               port of the web_bridge REST API
  backend_url  http://localhost:8080/api   where web_bridge reports order status
  bridge_delay 8.0                seconds to wait for Gazebo before starting web_bridge
  webapp_delay 20.0               seconds to wait before starting backend + frontend, so that
                                  Maven/Java/Vite do not slow down Gazebo while the robot
                                  controllers are being activated

MySQL must be running (the backend uses deliverybot_db on localhost:3306).
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription,
                            LogInfo, OpaqueFunction, TimerAction)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _session(cmd):
    """Run a shell command in its own process group, so that Ctrl+C also stops
    the processes it starts (mvnw starts a second JVM, npm starts node)."""
    script = f'trap "trap - INT TERM EXIT; kill 0" INT TERM EXIT; {cmd} & wait'
    return ['setsid', 'bash', '-c', script]


def _webapp(context):
    if LaunchConfiguration('webapp').perform(context).lower() not in ('true', '1', 'yes'):
        return [LogInfo(msg='webapp:=false: start the backend and the frontend yourself')]
    root = os.path.expanduser(LaunchConfiguration('webapp_dir').perform(context))
    backend = os.path.join(root, 'backend')
    frontend = os.path.join(root, 'frontend')
    if not os.path.isdir(frontend):  # older layout of the web app folder
        frontend = os.path.join(root, 'robotProjectApp', 'robotProjectApp')
    actions = []
    if not os.path.isfile(os.path.join(backend, 'mvnw')):
        actions.append(LogInfo(msg=f'[web_sim] backend not found in {backend} (set webapp_dir:=...)'))
    else:
        actions.append(ExecuteProcess(
            cmd=_session('chmod +x ./mvnw; ./mvnw -q spring-boot:run'),
            cwd=backend, name='backend', output='screen', sigterm_timeout='10'))
    if not os.path.isfile(os.path.join(frontend, 'package.json')):
        actions.append(LogInfo(msg=f'[web_sim] frontend not found in {frontend}'))
    else:
        install = '' if os.path.isdir(os.path.join(frontend, 'node_modules')) else 'npm install && '
        actions.append(ExecuteProcess(
            cmd=_session(f'{install}npm run dev -- --port 5173 --strictPort'),
            cwd=frontend, name='frontend', output='screen', sigterm_timeout='5'))
    actions.append(LogInfo(msg='[web_sim] Web app: http://localhost:5173  '
                               '(Robot Settings -> Use Gazebo Simulation)'))
    return actions


def generate_launch_description():
    pkg = get_package_share_directory('indoor_delivery_project')

    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg, 'launch', 'sim.launch.py')),
        launch_arguments={
            'world': LaunchConfiguration('world'),
            'gui': LaunchConfiguration('gui'),
            'rtf': LaunchConfiguration('rtf'),
            'aruco': LaunchConfiguration('aruco'),
        }.items())

    bridge = Node(
        package='indoor_delivery_project',
        executable='web_bridge',
        name='delivery_navigator',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'map_dir': LaunchConfiguration('map_dir'),
            'http_port': LaunchConfiguration('bridge_port'),
            'backend_url': LaunchConfiguration('backend_url'),
            'interactive': False,
        }])

    return LaunchDescription([
        DeclareLaunchArgument('world', default_value='two_buildings'),
        DeclareLaunchArgument('map_dir', default_value='~/ros2_jazzy_ws/maps/campus_full_map7'),
        DeclareLaunchArgument('webapp_dir', default_value='~/Downloads/WebApplication/Back-Front'),
        DeclareLaunchArgument('webapp', default_value='true'),
        DeclareLaunchArgument('gui', default_value='true'),
        DeclareLaunchArgument('rtf', default_value='1.0'),
        DeclareLaunchArgument('aruco', default_value='true'),
        DeclareLaunchArgument('bridge_port', default_value='5000'),
        DeclareLaunchArgument('backend_url', default_value='http://localhost:8080/api'),
        DeclareLaunchArgument('bridge_delay', default_value='8.0'),
        DeclareLaunchArgument('webapp_delay', default_value='20.0'),
        sim,
        TimerAction(period=LaunchConfiguration('webapp_delay'),
                    actions=[OpaqueFunction(function=_webapp)]),
        TimerAction(period=LaunchConfiguration('bridge_delay'), actions=[bridge]),
    ])
