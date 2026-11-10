#!/usr/bin/env bash
# One-time setup of this ROS 2 workspace:
#   1. clone the pinned Robotnik RB1 packages (dependencies.repos) into src/
#   2. patch rb1_control.urdf.xacro so the robot uses this project's controller YAML
#   3. install system dependencies with rosdep
#   4. colcon build
#
#   ./setup_workspace.sh            # everything
#   ./setup_workspace.sh --no-build # skip colcon build
set -e
WS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$WS"
set +u; source /opt/ros/jazzy/setup.bash; set -u

command -v vcs >/dev/null || { echo "Install vcstool: sudo apt install python3-vcstool"; exit 1; }

mkdir -p src
vcs import src < dependencies.repos

XACRO=src/indoor_autonomous_robot/robotnik_description/simulators/gazebo_ignition/rb1/rb1_control.urdf.xacro
if grep -q 'rb1_diff_drive_controllers.yaml' "$XACRO"; then
    echo "[setup] robotnik_description already patched"
else
    patch -p1 -d src/indoor_autonomous_robot/robotnik_description \
        < patches/robotnik_description_rb1_controller_params.patch
fi

rosdep install --from-paths src --ignore-src -r -y || \
    echo "[setup] rosdep reported problems (see above); continuing"

if [ "${1:-}" != "--no-build" ]; then
    colcon build --symlink-install
    echo "[setup] Done. Now run:  source $WS/install/setup.bash"
fi
