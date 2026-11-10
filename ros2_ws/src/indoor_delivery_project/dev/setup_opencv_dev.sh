#!/usr/bin/env bash
# OpenCV / ArUco development setup for ROS 2 Jazzy on Ubuntu 24.04.
#
#   bash dev/setup_opencv_dev.sh            # ROS + OpenCV packages (apt)
#   bash dev/setup_opencv_dev.sh --notebook # + Jupyter kernel and matplotlib
#
# Uses apt only, on purpose: Ubuntu's python3-opencv (4.6) already includes the
# contrib "aruco" module and is built against the same numpy as cv_bridge.
# `pip install opencv-contrib-python` system-wide pulls in numpy 2.x and a second
# cv2, which breaks cv_bridge / rclpy imports. If you ever need OpenCV >= 4.7,
# do it in a venv: see the end of this file.
set -euo pipefail

PKGS=(
  python3-opencv            # cv2 incl. cv2.aruco (contrib)
  python3-numpy
  ros-jazzy-cv-bridge       # sensor_msgs/Image <-> cv2
  ros-jazzy-vision-opencv
  ros-jazzy-image-transport
  ros-jazzy-rqt-image-view  # view /aruco_detector/annotated
)
if [[ "${1:-}" == "--notebook" ]]; then
  PKGS+=(python3-matplotlib python3-ipykernel jupyter-notebook)
fi

sudo apt update
sudo apt install -y "${PKGS[@]}"

echo
echo "Installed. Checking the environment:"
source /opt/ros/jazzy/setup.bash
python3 "$(dirname "$0")/check_opencv_env.py"

# --- Optional: newer OpenCV in an isolated venv (only for experiments) -------
#   python3 -m venv --system-site-packages ~/venvs/cv
#   ~/venvs/cv/bin/pip install "opencv-contrib-python<4.11" "numpy<2"
#   source ~/venvs/cv/bin/activate   # then source the ROS workspace as usual
# Deactivate it before `colcon build` so nodes keep using the apt OpenCV.
