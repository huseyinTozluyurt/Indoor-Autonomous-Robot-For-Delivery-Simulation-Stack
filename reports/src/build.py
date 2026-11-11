#!/usr/bin/env python3
"""Build the six project reports: python3 build.py  (needs google-chrome or chromium)."""
import os, subprocess, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r1_webapp, r2_aruco, r3_slam, r4_dijkstra, r5_link, r6_maps
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
REPORTS = [('01_Web_Application', r1_webapp), ('02_Object_Detection_ArUco', r2_aruco),
           ('03_Indoor_Navigation_SLAM', r3_slam), ('04_Dijkstra_Shortest_Path', r4_dijkstra),
           ('05_WebApp_Gazebo_Connection', r5_link), ('06_Map_Evolution_Comparison', r6_maps)]
chrome = shutil.which('google-chrome') or shutil.which('chromium') or shutil.which('chromium-browser')
for name, mod in REPORTS:
    html_path = os.path.join(HERE, name + '.html')
    with open(html_path, 'w') as f:
        f.write(mod.build())
    pdf = os.path.join(OUT, name + '.pdf')
    subprocess.run([chrome, '--headless', '--no-sandbox', '--disable-gpu', '--no-pdf-header-footer',
                    '--allow-file-access-from-files', f'--print-to-pdf={pdf}', 'file://' + html_path],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print('wrote', pdf)
