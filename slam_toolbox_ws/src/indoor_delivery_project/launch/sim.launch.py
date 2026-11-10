import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    RegisterEventHandler,
)
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    project_pkg = get_package_share_directory('indoor_delivery_project')
    description_pkg = get_package_share_directory('indoor_delivery_robot_description')
    ros_gz_sim_pkg = get_package_share_directory('ros_gz_sim')

    world = LaunchConfiguration('world')
    x_pose = LaunchConfiguration('x_pose')
    y_pose = LaunchConfiguration('y_pose')
    z_pose = LaunchConfiguration('z_pose')
    yaw = LaunchConfiguration('yaw')
    namespace = LaunchConfiguration('namespace')

    default_world = os.path.join(project_pkg, 'worlds', 'campus_area.sdf')
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

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim_pkg, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={
            'gz_args': ['-r ', world],
            'on_exit_shutdown': 'true',
        }.items()
    )

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

    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        output='screen',
        arguments=[
            '-name', 'indoor_delivery_rb1',
            '-topic', 'robot_description',
            '-x', x_pose,
            '-y', y_pose,
            '-z', z_pose,
            '-Y', yaw
        ],
        remappings=[
            ('/robot_description', ['/', namespace, '/robot_description'])
        ]
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

    # Start controllers only after the robot exists in Gazebo,
    # and the diff drive only after the joint_state_broadcaster is up.
    start_jsb_after_spawn = RegisterEventHandler(
        OnProcessExit(
            target_action=spawn_robot,
            on_exit=[joint_state_broadcaster_spawner],
        )
    )
    start_diff_drive_after_jsb = RegisterEventHandler(
        OnProcessExit(
            target_action=joint_state_broadcaster_spawner,
            on_exit=[diff_drive_controller_spawner],
        )
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'world',
            default_value=default_world,
            description='Full path to world file'
        ),
        DeclareLaunchArgument('x_pose', default_value='-25.0'),
        DeclareLaunchArgument('y_pose', default_value='0.0'),
        DeclareLaunchArgument('z_pose', default_value='0.20'),
        DeclareLaunchArgument('yaw', default_value='0.0'),
        DeclareLaunchArgument(
            'namespace',
            default_value='robot',
            description='Robot namespace (gz_bridge.yaml and the controller '
                        'YAML assume "robot")'
        ),

        gazebo,
        gz_bridge,
        robot_state_publisher,
        spawn_robot,
        twist_bridge,
        start_jsb_after_spawn,
        start_diff_drive_after_jsb,
    ])
