#!/usr/bin/env bash
# Start the Gazebo delivery simulation, the web_bridge and the DeliveryBot web
# application (Spring Boot + React) together. Ctrl+C stops all of them.
#
#   ros2_ws/run_web_sim.sh                 # everything
#   ros2_ws/run_web_sim.sh --build         # colcon build first (after code changes)
#   ros2_ws/run_web_sim.sh gui:=false rtf:=3.0
#   ros2_ws/run_web_sim.sh webapp:=false   # only simulation + web_bridge
#
# Any name:=value is passed to: ros2 launch indoor_delivery_project web_sim.launch.py
# (world, map_dir, webapp_dir, gui, rtf, aruco, bridge_port, backend_url, bridge_delay)
set -e
WS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$WS")"
cd "$WS"

BUILD=0
ARGS=()
for a in "$@"; do
    case "$a" in
        --build) BUILD=1 ;;
        -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
        *) ARGS+=("$a") ;;
    esac
done

set +u
source /opt/ros/jazzy/setup.bash
if [ "$BUILD" = 1 ] || [ ! -x install/indoor_delivery_project/lib/indoor_delivery_project/web_bridge ]; then
    echo "[run_web_sim] colcon build indoor_delivery_project ..."
    colcon build --symlink-install --packages-select indoor_delivery_project
fi
source install/setup.bash

port_open() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

if [[ " ${ARGS[*]} " != *" webapp:=false "* ]]; then
    if ! port_open 3306; then
        echo "[run_web_sim] WARNING: MySQL is not running on port 3306; the backend will fail."
        echo "              Start it with:  sudo systemctl start mysql"
    fi
    for p in 8080 5173; do
        if port_open $p; then
            echo "[run_web_sim] WARNING: port $p is already in use (an old backend/frontend still running?)"
        fi
    done
fi
if port_open 5000; then
    echo "[run_web_sim] WARNING: port 5000 is already in use (an old web_bridge still running?)"
fi

echo "[run_web_sim] Starting simulation + web_bridge + web app. Open http://localhost:5173"
# Use the map and the web app from this repository unless given on the command line.
[[ " ${ARGS[*]} " == *" map_dir:="* ]] || ARGS+=("map_dir:=$REPO/maps/campus_full_map7")
[[ " ${ARGS[*]} " == *" webapp_dir:="* ]] || ARGS+=("webapp_dir:=$REPO/web_app")
exec ros2 launch indoor_delivery_project web_sim.launch.py "${ARGS[@]}"
