# %% [markdown]
# # ArUco scratchpad (VS Code "Run Cell" / Jupyter cells)
# Each `# %%` block is a cell: open this file in VS Code with the Python +
# Jupyter extensions and press "Run Cell", or run it top to bottom with python3.
# Start VS Code from a terminal where the workspace is sourced
# (`source ~/ros2_jazzy_ws/install/setup.bash && code .`) so rclpy imports work.

# %% Imports
import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__ if '__file__' in dir() else 'dev/aruco_scratch.py'))))
from indoor_delivery_project import aruco_utils  # noqa: E402

print('OpenCV', cv2.__version__, '| aruco:', aruco_utils.has_aruco())

# %% Get a frame: from the running sim, else a generated test marker
try:
    frame, K, D = aruco_utils.grab_ros_frame('/robot/aruco_camera/image_raw', timeout=3.0)
    print('frame from sim', frame.shape, '| camera_info:', K is not None)
except Exception as exc:  # sim not running / workspace not sourced
    print('no sim frame:', exc, '-> using a generated marker')
    frame = cv2.cvtColor(aruco_utils.generate_marker(7, 300), cv2.COLOR_GRAY2BGR)
    K = D = None

# %% Detect
detector = aruco_utils.MarkerDetector('DICT_4X4_50')
corners, ids, rejected = detector.detect(frame)
print('ids:', None if ids is None else ids.ravel().tolist(), '| rejected:', len(rejected))

# %% Show (matplotlib renders inline in notebooks; falls back to a cv2 window)
out = aruco_utils.draw(frame.copy(), corners, ids, K, D, marker_size=0.30)
try:
    import matplotlib.pyplot as plt
    plt.figure(figsize=(8, 6))
    plt.imshow(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
    plt.axis('off')
    plt.show()
except ImportError:
    cv2.imshow('scratch', out)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

# %% Save the frame for offline experiments (aruco_playground.py --source <file>)
os.makedirs('dev/snapshots', exist_ok=True)
cv2.imwrite('dev/snapshots/scratch_frame.png', frame)
