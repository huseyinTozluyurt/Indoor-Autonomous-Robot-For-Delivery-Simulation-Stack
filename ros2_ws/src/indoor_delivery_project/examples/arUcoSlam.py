import json
import math
from indoor_delivery_project.robot_commands import Robot

def perform_slam_scan(robot, scan_steps=12, step_angle=30.0, global_map=None):
    if global_map is None:
        global_map = {}
        
    print(f"Initiating 360-degree SLAM scan from current pose: {robot.get_pose()}")
    
    for _ in range(scan_steps):
        robot.turn_left(step_angle)
        robot.sleep(0.5)  # Pause for aruco_detector to process a fresh frame
        
        detections = robot.visible_markers(max_age=1.0)
        pose = robot.get_pose()
        
        if not pose or not detections:
            continue
            
        rx, ry, ryaw_deg = pose
        
        for det in detections:
            marker_id = det.get('id')
            distance = det.get('distance_m')
            
            if distance and marker_id not in global_map:
                marker_x = rx + distance * math.cos(math.radians(ryaw_deg))
                marker_y = ry + distance * math.sin(math.radians(ryaw_deg))
                
                global_map[marker_id] = {
                    'name': det.get('name', 'unknown'),
                    'kind': det.get('kind', 'unknown'),
                    'x': round(marker_x, 2),
                    'y': round(marker_y, 2)
                }
                print(f"Mapped Marker {marker_id} at X:{marker_x:.2f}, Y:{marker_y:.2f}")
                
    return global_map

def save_slam_map(slam_map, filepath='slam_map.json'):
    """Exports the dictionary to a JSON file for later navigation."""
    with open(filepath, 'w') as f:
        json.dump(slam_map, f, indent=4)
    print(f"\nSLAM map successfully saved to {filepath}")

def main():
    with Robot(angular_speed=0.4, linear_speed=0.3) as robot:
        slam_map = {}
        
        # Phase 1: Scan the starting area
        perform_slam_scan(robot, global_map=slam_map)
        
        # Phase 2: Relocate to expand the map
        print("Navigating to new sector to expand map...")
        robot.forward(3.0)
        perform_slam_scan(robot, global_map=slam_map)
        
        # Export the final map
        save_slam_map(slam_map, 'slam_map.json')

if __name__ == '__main__':
    main()