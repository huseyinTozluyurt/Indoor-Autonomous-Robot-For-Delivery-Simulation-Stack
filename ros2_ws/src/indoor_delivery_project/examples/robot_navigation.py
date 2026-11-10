from indoor_delivery_project.robot_commands import Robot

def navigate_by_marker(robot, target_id):
    detection = robot.search_marker(target_id, max_degrees=180)

    if not detection:
        print(f"Targeted ArUco marker {target_id} not found in the operational area. Halting")
        robot.stop()
        return


    marker_id = detection.get('id')
    distance = detection.get('distance_m', 0.0)
    room = detection.get('room', 'unknown')

    print("Heelo")
    

def main():
    with Robot() as robot:

if __name__ == '__main__':
    main()