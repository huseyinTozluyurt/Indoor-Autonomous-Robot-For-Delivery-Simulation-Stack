import os
import re
import tempfile

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    AppendEnvironmentVariable,
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
    RegisterEventHandler,
)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


# Worlds selectable by name: world:=campus_area (default) or world:=two_buildings.
# world:= also still accepts a full path to any .sdf file (then the campus spawn
# pose and markers apply unless x_pose/y_pose/yaw are given).
WORLDS = {
    'campus_area': dict(spawn=(-25.0, 0.0, 0.0), markers='aruco_markers.yaml'),
    'two_buildings': dict(spawn=(-17.0, -17.0, 0.0), markers='aruco_markers_two_buildings.yaml'),
}


def _world_entry(context, project_pkg):
    """(world sdf path, WORLDS entry) for the world:= launch argument."""
    world = LaunchConfiguration('world').perform(context)
    name = os.path.splitext(os.path.basename(world))[0]
    if os.sep not in world:                     # a name: worlds/<name>.sdf
        world = os.path.join(project_pkg, 'worlds', name + '.sdf')
    return world, WORLDS.get(name, WORLDS['campus_area'])


def _gazebo(context, ros_gz_sim_pkg, project_pkg):
    """Start Gazebo. rtf != 1 or another physics_step: run a copy of the world
    with a <physics> block (real_time_factor = simulation speed). gui:=false
    runs the server only, which is faster."""
    world, _ = _world_entry(context, project_pkg)
    rtf = float(LaunchConfiguration('rtf').perform(context))
    step = float(LaunchConfiguration('physics_step').perform(context))
    gui = LaunchConfiguration('gui').perform(context).lower() in ('true', '1', 'yes')
    if rtf != 1.0 or step != 0.001:
        with open(world) as f:
            sdf = f.read()
        sdf = re.sub(r'\s*<physics\b.*?</physics>', '', sdf, flags=re.S)
        physics = ('\n    <physics name="speed" type="ignored">'
                   f'\n      <max_step_size>{step}</max_step_size>'
                   f'\n      <real_time_factor>{rtf}</real_time_factor>'
                   '\n    </physics>')
        sdf = re.sub(r'(<world\b[^>]*>)', lambda m: m.group(1) + physics, sdf, count=1)
        name = os.path.splitext(os.path.basename(world))[0]
        world = os.path.join(tempfile.gettempdir(), f'{name}_rtf{rtf:g}.sdf')
        with open(world, 'w') as f:
            f.write(sdf)
        print(f'[sim.launch] Gazebo speed: real_time_factor {rtf:g}, '
              f'max_step_size {step:g} s ({world})')
    gz_args = '-r ' + ('' if gui else '-s --headless-rendering ') + world
    return [IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim_pkg, 'launch', 'gz_sim.launch.py')),
        launch_arguments={'gz_args': gz_args, 'on_exit_shutdown': 'true'}.items())]


def generate_launch_description():
    project_pkg = get_package_share_directory('indoor_delivery_project')
    description_pkg = get_package_share_directory('indoor_delivery_robot_description')
    ros_gz_sim_pkg = get_package_share_directory('ros_gz_sim')

    z_pose = LaunchConfiguration('z_pose')
    namespace = LaunchConfiguration('namespace')

    bridge_config = os.path.join(project_pkg, 'config', 'gz_bridge.yaml')
    robot_xacro = os.path.join(
        description_pkg, 'urdf', 'indoor_delivery_rb1.urdf.xacro'
    )

    robot_description_content = ParameterValue(
        Command([
            'xacro ',
            robot_xacro,
            ' namespace:=', namespace,
            ' prefix:=',
            ' gazebo_ignition:=true'
        ]),
        value_type=str
    )

    # Lets the world find model://aruco_marker_<id> (models/ in this package).
    gz_models_path = AppendEnvironmentVariable(
        'GZ_SIM_RESOURCE_PATH', os.path.join(project_pkg, 'models'))

    gazebo = OpaqueFunction(function=_gazebo, args=[ros_gz_sim_pkg, project_pkg])

    # Gazebo <-> ROS bridge: /clock (needed for use_sim_time) + sensors.
    gz_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='gz_bridge',
        output='screen',
        parameters=[{
            'config_file': bridge_config,
            'use_sim_time': True,
        }]
    )

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        namespace=namespace,
        output='screen',
        parameters=[{
            'use_sim_time': True,
            'robot_description': robot_description_content
        }]
    )

    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=[
            'joint_state_broadcaster',
            '--controller-manager', ['/', namespace, '/controller_manager'],
            '--controller-manager-timeout', '60',
        ],
        output='screen'
    )

    diff_drive_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=[
            'diff_drive_controller',
            '--controller-manager', ['/', namespace, '/controller_manager'],
            '--controller-manager-timeout', '60',
        ],
        output='screen'
    )

    # /cmd_vel (Twist, from the PyQt5 app or teleop) ->
    # /<ns>/diff_drive_controller/cmd_vel (TwistStamped, what Jazzy expects)
    twist_bridge = Node(
        package='indoor_delivery_project',
        executable='twist_to_stamped_bridge',
        name='twist_to_stamped_bridge',
        output='screen',
        parameters=[{
            'use_sim_time': True,
            'input_topic': '/cmd_vel',
            'output_topic': ['/', namespace, '/diff_drive_controller/cmd_vel'],
            'frame_id': 'base_link',
        }]
    )

    # Optional: record bag + video from the start (see record.launch.py)
    recording = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(project_pkg, 'launch', 'record.launch.py')
        ),
        condition=IfCondition(LaunchConfiguration('record')),
    )

    def _robot_and_detector(context):
        """Spawn pose and marker config depend on the chosen world."""
        _, entry = _world_entry(context, project_pkg)
        spawn = [LaunchConfiguration(n).perform(context) or str(v)
                 for n, v in zip(('x_pose', 'y_pose', 'yaw'), entry['spawn'])]
        markers_file = os.path.join(project_pkg, 'config', entry['markers'])
        print(f'[sim.launch] spawn x={spawn[0]} y={spawn[1]} yaw={spawn[2]}, '
              f'markers {markers_file}')

        spawn_robot = Node(
            package='ros_gz_sim',
            executable='create',
            output='screen',
            arguments=[
                '-name', 'indoor_delivery_rb1',
                '-topic', 'robot_description',
                '-x', spawn[0],
                '-y', spawn[1],
                '-z', z_pose,
                '-Y', spawn[2],
            ],
            remappings=[
                ('/robot_description', ['/', namespace, '/robot_description'])
            ]
        )

        # ArUco detection on the mast camera (markers: the world's marker YAML)
        aruco_detector = Node(
            package='indoor_delivery_project',
            executable='aruco_detector',
            name='aruco_detector',
            output='screen',
            condition=IfCondition(LaunchConfiguration('aruco')),
            parameters=[{
                'use_sim_time': True,
                'image_topic': '/robot/aruco_camera/image_raw',
                'camera_info_topic': '/robot/aruco_camera/camera_info',
                'markers_file': markers_file,
            }]
        )

        # Start controllers only after the robot exists in Gazebo,
        # and the diff drive only after the joint_state_broadcaster is up.
        return [
            spawn_robot,
            aruco_detector,
            RegisterEventHandler(OnProcessExit(
                target_action=spawn_robot,
                on_exit=[joint_state_broadcaster_spawner])),
            RegisterEventHandler(OnProcessExit(
                target_action=joint_state_broadcaster_spawner,
                on_exit=[diff_drive_controller_spawner])),
        ]

    return LaunchDescription([
        DeclareLaunchArgument(
            'world',
            default_value='campus_area',
            description='World name (campus_area | two_buildings) or full path to a .sdf'
        ),
        DeclareLaunchArgument('x_pose', default_value='',
                              description='Spawn x; empty = the world default'),
        DeclareLaunchArgument('y_pose', default_value='',
                              description='Spawn y; empty = the world default'),
        DeclareLaunchArgument('z_pose', default_value='0.20'),
        DeclareLaunchArgument('yaw', default_value='',
                              description='Spawn yaw; empty = the world default'),
        DeclareLaunchArgument(
            'namespace',
            default_value='robot',
            description='Robot namespace (gz_bridge.yaml and the controller '
                        'YAML assume "robot")'
        ),

        DeclareLaunchArgument('aruco', default_value='true',
                              description='Run the ArUco detector'),
        DeclareLaunchArgument('record', default_value='false',
                              description='Record rosbag + camera video'),
        DeclareLaunchArgument('rtf', default_value='1.0',
                              description='Simulation speed (real_time_factor), '
                                          'e.g. 10.0 = 10x faster than real time'),
        DeclareLaunchArgument('physics_step', default_value='0.001',
                              description='Physics step (max_step_size) in seconds'),
        DeclareLaunchArgument('gui', default_value='true',
                              description='false = Gazebo server only, no window (faster)'),

        gz_models_path,
        gazebo,
        gz_bridge,
        robot_state_publisher,
        twist_bridge,
        OpaqueFunction(function=_robot_and_detector),
        recording,
    ])
