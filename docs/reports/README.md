# Project reports

Six PDF reports on the simulation stack (November 2026):

1. `01_Web_Application.pdf`
2. `02_Object_Detection_ArUco.pdf`
3. `03_Indoor_Navigation_SLAM.pdf`
4. `04_Dijkstra_Shortest_Path.pdf`
5. `05_WebApp_Gazebo_Connection.pdf`
6. `06_Map_Evolution_Comparison.pdf`

`figures/` holds every figure used. `src/` holds the report sources: `build.py` regenerates all six PDFs
(needs google-chrome), `scripts/` the analysis scripts that produced the measured figures
(map metrics against the world files, ArUco accuracy test, offline Dijkstra/Held-Karp runs; run them with
`/opt/ros/jazzy` and `~/ros2_jazzy_ws/install` sourced), and `data/` their JSON results.
