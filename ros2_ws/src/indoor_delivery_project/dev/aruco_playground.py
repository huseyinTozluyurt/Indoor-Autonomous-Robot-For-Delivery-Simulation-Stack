#!/usr/bin/env python3
"""Live ArUco playground: try detection ideas on the sim camera, a webcam or files.

    python3 dev/aruco_playground.py                       # sim mast camera (ROS)
    python3 dev/aruco_playground.py --source 0            # webcam 0 (real-world tests)
    python3 dev/aruco_playground.py --source dev/snapshots/frame_0001.png
    python3 dev/aruco_playground.py --source some_video.mp4

Keys:  q quit | s save raw frame to dev/snapshots | space pause | r show rejected
       candidates | t show threshold image

Edit `process()` below to experiment. It runs on every frame; whatever image it
returns is shown. No colcon build needed for edits here: just re-run the script.
For ROS sources, source the workspace first (`source install/setup.bash`).
"""
import argparse
import os
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))   # package root -> import without building
from indoor_delivery_project import aruco_utils  # noqa: E402

SNAPSHOT_DIR = os.path.join(HERE, 'snapshots')


# =========================== EXPERIMENT HERE ===============================
DETECTOR = aruco_utils.MarkerDetector(
    'DICT_4X4_50',
    # Tuning examples (uncomment to try):
    # adaptiveThreshWinSizeMin=3, adaptiveThreshWinSizeMax=53,
    # minMarkerPerimeterRate=0.02,
    # cornerRefinementMethod=cv2.aruco.CORNER_REFINE_SUBPIX,
)
MARKER_SIZE = 0.30      # metres; 1.0 for ids 10/20, 0.6 for 11/21 (docs/aruco_and_camera.md)


def process(frame, K, D, state):
    """Called for every frame. Return the image to display."""
    out = frame.copy()
    corners, ids, rejected = DETECTOR.detect(frame)
    aruco_utils.draw(out, corners, ids, K, D, MARKER_SIZE,
                     rejected if state['show_rejected'] else None)
    if state['show_threshold']:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY_INV, 23, 7)
        out = np.hstack([out, cv2.cvtColor(th, cv2.COLOR_GRAY2BGR)])
    found = [] if ids is None else ids.ravel().tolist()
    state['last_ids'] = found
    return out
# ===========================================================================


class RosSource:
    """Latest frame from a ROS image topic (uses cv_bridge if installed)."""

    def __init__(self, topic, info_topic):
        import rclpy
        from rclpy.qos import qos_profile_sensor_data
        from sensor_msgs.msg import CameraInfo, Image
        self.rclpy = rclpy
        rclpy.init()
        self.node = rclpy.create_node('aruco_playground')
        try:
            from cv_bridge import CvBridge
            bridge = CvBridge()
            self.convert = lambda m: bridge.imgmsg_to_cv2(m, 'bgr8')
            how = 'cv_bridge'
        except ImportError:
            from indoor_delivery_project.image_utils import image_to_bgr
            self.convert = image_to_bgr
            how = 'image_utils (cv_bridge not installed)'
        self.msg = None
        self.K = self.D = None
        self.node.create_subscription(Image, topic, self._img, qos_profile_sensor_data)
        self.node.create_subscription(CameraInfo, info_topic, self._info,
                                      qos_profile_sensor_data)
        print(f'[ros] {topic} via {how}')

    def _img(self, msg):
        self.msg = msg

    def _info(self, msg):
        self.K, self.D = aruco_utils.camera_info_to_kd(msg)

    def read(self):
        self.rclpy.spin_once(self.node, timeout_sec=0.05)
        if self.msg is None:
            return None
        msg, self.msg = self.msg, None
        return self.convert(msg)

    def close(self):
        self.node.destroy_node()
        self.rclpy.shutdown()


class CvSource:
    """Webcam index, video file or a single image (repeated)."""

    def __init__(self, source):
        self.still = None
        self.K = self.D = None
        if not source.isdigit() and os.path.splitext(source)[1].lower() in (
                '.png', '.jpg', '.jpeg', '.bmp'):
            self.still = cv2.imread(source)
            if self.still is None:
                raise SystemExit(f'cannot read {source}')
        else:
            self.cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
            if not self.cap.isOpened():
                raise SystemExit(f'cannot open {source}')

    def read(self):
        if self.still is not None:
            time.sleep(0.03)
            return self.still.copy()
        ok, frame = self.cap.read()
        return frame if ok else None

    def close(self):
        if self.still is None:
            self.cap.release()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', default='ros',
                    help='"ros", a webcam index, a video or an image file')
    ap.add_argument('--topic', default='/robot/aruco_camera/image_raw')
    ap.add_argument('--info-topic', default='/robot/aruco_camera/camera_info')
    ap.add_argument('--headless', action='store_true',
                    help='no window: print detected ids (for SSH / CI)')
    args = ap.parse_args()

    src = RosSource(args.topic, args.info_topic) if args.source == 'ros' else CvSource(args.source)
    state = {'show_rejected': False, 'show_threshold': False, 'paused': False,
             'last_ids': []}
    frame, n_saved, t_last, fps = None, 0, time.monotonic(), 0.0
    try:
        while True:
            if not state['paused']:
                new = src.read()
                if new is not None:
                    frame = new
                    now = time.monotonic()
                    fps = 0.9 * fps + 0.1 / max(now - t_last, 1e-3)
                    t_last = now
            if frame is None:
                if args.headless:
                    continue
                if cv2.waitKey(30) & 0xFF == ord('q'):
                    break
                continue

            out = process(frame, src.K, src.D, state)
            if args.headless:
                print(f'ids={state["last_ids"]}', flush=True)
                continue
            cv2.putText(out, f'{fps:4.1f} fps  ids={state["last_ids"]}'
                        f'{"  K ok" if src.K is not None else "  no camera_info"}',
                        (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.imshow('aruco_playground', out)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            if key == ord('s'):
                os.makedirs(SNAPSHOT_DIR, exist_ok=True)
                n_saved += 1
                path = os.path.join(SNAPSHOT_DIR, f'frame_{int(time.time())}_{n_saved:03d}.png')
                cv2.imwrite(path, frame)
                print('saved', path)
            elif key == ord(' '):
                state['paused'] = not state['paused']
            elif key == ord('r'):
                state['show_rejected'] = not state['show_rejected']
            elif key == ord('t'):
                state['show_threshold'] = not state['show_threshold']
    except KeyboardInterrupt:
        pass
    finally:
        src.close()
        if not args.headless:
            cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
