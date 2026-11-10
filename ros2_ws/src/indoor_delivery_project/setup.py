from setuptools import find_packages, setup
from glob import glob
import os

package_name = 'indoor_delivery_project'


def tree(src):
    """data_files entries that install src/ recursively under share/<pkg>/."""
    out = []
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        if files:
            out.append((os.path.join('share', package_name, root),
                        [os.path.join(root, f) for f in files]))
    return out


setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), [f for f in glob('launch/*') if os.path.isfile(f)]),
        (os.path.join('share', package_name, 'worlds'), [f for f in glob('worlds/*') if os.path.isfile(f)]),
        (os.path.join('share', package_name, 'config'), [f for f in glob('config/*') if os.path.isfile(f)]),
    ] + tree('models'),
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Huseyin',
    maintainer_email='huseyintozluyurt@hotmail.com',
    description='Indoor autonomous delivery project with Gazebo world and RB1 robot.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'twist_to_stamped_bridge = indoor_delivery_project.twist_to_stamped_bridge:main',
            'pyqt_teleop = indoor_delivery_project.pyqt_teleop:main',
            'aruco_detector = indoor_delivery_project.aruco_detector:main',
            'video_recorder = indoor_delivery_project.video_recorder:main',
            'aruco_slam_mapper = indoor_delivery_project.aruco_slam_mapper:main',
            'delivery_navigator = indoor_delivery_project.delivery_navigator:main',
            'correct_map = indoor_delivery_project.correct_map:main',
            'optimize_map = indoor_delivery_project.map_optimizer:main',
            'delivery_gui = indoor_delivery_project.delivery_gui:main',
            'robot_vision = indoor_delivery_project.robot_vision:main',
            'web_bridge = indoor_delivery_project.web_bridge:main',
            # Example for later:
            # 'delivery_waypoint_node = indoor_delivery_project.delivery_waypoint_node:main',
        ],
    },
)