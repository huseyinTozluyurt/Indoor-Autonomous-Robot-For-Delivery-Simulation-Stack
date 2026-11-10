"""Record a camera topic to an .mp4 file (one file per recording session).

Parameters:
  image_topic      default /robot/aruco_camera/image_raw
                   (use /aruco_detector/annotated to record the overlay)
  output_dir       default ~/robot_recordings
  fps              default 15.0 (should match the camera update_rate)
  start_recording  default true
  overlay_time     default true, stamps the sim time on each frame

Service ~/set_recording (std_srvs/SetBool): true starts a new file,
false closes the current one.
"""
import os
from datetime import datetime

import cv2
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_srvs.srv import SetBool

from indoor_delivery_project.image_utils import image_to_bgr


class VideoRecorder(Node):
    def __init__(self):
        super().__init__('video_recorder')
        self.declare_parameter('image_topic', '/robot/aruco_camera/image_raw')
        self.declare_parameter('output_dir', '~/robot_recordings')
        self.declare_parameter('fps', 15.0)
        self.declare_parameter('start_recording', True)
        self.declare_parameter('overlay_time', True)

        self.output_dir = os.path.expanduser(self.get_parameter('output_dir').value)
        os.makedirs(self.output_dir, exist_ok=True)
        self.fps = float(self.get_parameter('fps').value)
        self.overlay = bool(self.get_parameter('overlay_time').value)
        self.recording = bool(self.get_parameter('start_recording').value)
        self.writer = None
        self.path = None
        self.frames = 0

        topic = self.get_parameter('image_topic').value
        self.create_subscription(Image, topic, self._image_cb, qos_profile_sensor_data)
        self.create_service(SetBool, '~/set_recording', self._set_recording)
        self.get_logger().info(
            f'Recording {topic} -> {self.output_dir} '
            f'({"on" if self.recording else "paused"})')

    def _open(self, width, height):
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.path = os.path.join(self.output_dir, f'robot_camera_{stamp}.mp4')
        self.writer = cv2.VideoWriter(
            self.path, cv2.VideoWriter_fourcc(*'mp4v'), self.fps, (width, height))
        if not self.writer.isOpened():
            self.get_logger().error(f'Could not open video writer for {self.path}')
            self.writer = None
            self.recording = False
            return
        self.frames = 0
        self.get_logger().info(f'Started {self.path}')

    def _close(self):
        if self.writer is not None:
            self.writer.release()
            self.get_logger().info(f'Saved {self.path} ({self.frames} frames)')
        self.writer = None

    def _set_recording(self, request, response):
        if request.data and not self.recording:
            self.recording = True
            response.message = 'recording started'
        elif not request.data and self.recording:
            self.recording = False
            self._close()
            response.message = f'saved {self.path}'
        else:
            response.message = 'no change'
        response.success = True
        return response

    def _image_cb(self, msg: Image):
        if not self.recording:
            return
        try:
            img = image_to_bgr(msg)
        except ValueError as exc:
            self.get_logger().warn(str(exc), throttle_duration_sec=5.0)
            return
        if self.writer is None:
            self._open(img.shape[1], img.shape[0])
            if self.writer is None:
                return
        if self.overlay:
            t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            cv2.putText(img, f't={t:8.2f}s', (10, 22), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (255, 255, 255), 2)
        self.writer.write(img)
        self.frames += 1

    def destroy_node(self):
        self._close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = VideoRecorder()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
