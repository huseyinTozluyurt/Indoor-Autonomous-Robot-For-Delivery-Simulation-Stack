#!/usr/bin/env python3
"""Check the OpenCV / ArUco / cv_bridge setup. Run with the workspace sourced."""
import importlib
import sys

ok = True


def report(label, good, detail=''):
    global ok
    ok &= good
    print(f'  [{"OK" if good else "!!"}] {label}{(": " + detail) if detail else ""}')


print('python', sys.version.split()[0], sys.executable)

try:
    import numpy as np
    report('numpy', True, f'{np.__version__}  ({np.__file__})')
except ImportError as exc:
    report('numpy', False, str(exc))

try:
    import cv2
    report('opencv', True, f'{cv2.__version__}  ({cv2.__file__})')
    if '/usr/local/' in cv2.__file__ or '/.local/' in cv2.__file__:
        report('opencv source', False, 'cv2 comes from pip, not apt. It can clash with '
               'cv_bridge; consider `pip uninstall opencv-python opencv-contrib-python` '
               'and using python3-opencv')
    has = hasattr(cv2, 'aruco')
    api = ('ArucoDetector (>=4.7)' if has and hasattr(cv2.aruco, 'ArucoDetector')
           else 'legacy detectMarkers (4.6)' if has else 'missing')
    report('cv2.aruco', has, api)
    if has:
        sys.path.insert(0, __file__.rsplit('/dev/', 1)[0])
        from indoor_delivery_project import aruco_utils
        img = aruco_utils.generate_marker(7, 200)
        _, ids, _ = aruco_utils.MarkerDetector('DICT_4X4_50').detect(img)
        found = [] if ids is None else ids.ravel().tolist()
        report('detect generated marker 7', found == [7], f'found {found}')
except ImportError as exc:
    report('opencv', False, str(exc))

for mod in ('rclpy', 'cv_bridge', 'sensor_msgs.msg'):
    try:
        importlib.import_module(mod)
        report(mod, True)
    except ImportError as exc:
        report(mod, False, f'{exc} (source /opt/ros/jazzy/setup.bash?)')

try:
    import numpy as np
    from cv_bridge import CvBridge
    b = CvBridge()
    m = b.cv2_to_imgmsg(np.zeros((4, 4, 3), np.uint8), 'bgr8')
    report('cv_bridge round trip', b.imgmsg_to_cv2(m, 'bgr8').shape == (4, 4, 3))
except Exception as exc:  # noqa: BLE001
    report('cv_bridge round trip', False, str(exc))

for mod in ('indoor_delivery_project.robot_commands',):
    try:
        importlib.import_module(mod)
        report(mod, True)
    except Exception as exc:  # noqa: BLE001
        report(mod, False, f'{exc} (colcon build + source install/setup.bash?)')

print('\nAll good.' if ok else '\nSome checks failed (see !! lines).')
sys.exit(0 if ok else 1)
