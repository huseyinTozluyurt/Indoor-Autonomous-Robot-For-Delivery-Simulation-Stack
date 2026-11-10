from setuptools import find_packages, setup
from glob import glob
import os

package_name = 'indoor_delivery_project'


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
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Huseyin',
    maintainer_email='huseyintozluyurt@hotmail.com',
    description='Indoor delivery robot SLAM test workspace (Gazebo world, RB1, lidar/IMU/odom, slam_toolbox).',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'twist_to_stamped_bridge = indoor_delivery_project.twist_to_stamped_bridge:main',
            'pyqt_teleop = indoor_delivery_project.pyqt_teleop:main',
            # Example for later:
            # 'delivery_waypoint_node = indoor_delivery_project.delivery_waypoint_node:main',
        ],
    },
)