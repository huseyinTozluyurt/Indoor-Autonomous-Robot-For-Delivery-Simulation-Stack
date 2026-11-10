"""sensor_msgs/Image <-> OpenCV conversion without cv_bridge (rgb8/bgr8/mono8)."""
import numpy as np
from sensor_msgs.msg import Image

import cv2


def image_to_bgr(msg: Image):
    """Return a BGR uint8 array for rgb8, bgr8, rgba8, bgra8 or mono8 images."""
    channels = {'rgb8': 3, 'bgr8': 3, 'rgba8': 4, 'bgra8': 4, 'mono8': 1}
    enc = msg.encoding.lower()
    if enc not in channels:
        raise ValueError(f'unsupported image encoding {msg.encoding!r}')
    ch = channels[enc]
    buf = np.frombuffer(msg.data, dtype=np.uint8)
    img = buf.reshape(msg.height, msg.step)[:, :msg.width * ch]
    img = img.reshape(msg.height, msg.width, ch) if ch > 1 else img.reshape(msg.height, msg.width)
    if enc == 'rgb8':
        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    if enc == 'rgba8':
        return cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    if enc == 'bgra8':
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    if enc == 'mono8':
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img.copy()


def bgr_to_image(img, header) -> Image:
    msg = Image()
    msg.header = header
    msg.height, msg.width = img.shape[:2]
    msg.encoding = 'bgr8'
    msg.is_bigendian = 0
    msg.step = msg.width * 3
    msg.data = np.ascontiguousarray(img).tobytes()
    return msg
