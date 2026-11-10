#!/usr/bin/env python3
"""Generate Gazebo (gz sim Harmonic) ArUco marker models for the delivery world.

Run from the package root (src/indoor_delivery_project):
    python3 scripts/generate_aruco_models.py

It writes:
    models/aruco_marker_<id>/   model.config, model.sdf, meshes/marker.dae,
                                meshes/aruco_<id>.png
    config/aruco_markers.yaml   id -> name, kind, world pose, size
    scripts/aruco_world_includes.sdf.snippet  <include> block pasted into the world

Each marker is a 1x1 m textured quad (scaled in model.sdf) that faces the
model's +X axis, with a thin white backing plate. The PNG holds the marker plus
a white quiet zone, so `size` below is the black square edge length that the
detector should be configured with (marker_size parameter).
"""
import math
import os

import cv2
import numpy as np

DICTIONARY = 'DICT_4X4_50'
MARKER_PX = 400          # black square resolution in the PNG
MARGIN_PX = 50           # white quiet zone on each side
QUAD_SCALE = (MARKER_PX + 2 * MARGIN_PX) / MARKER_PX  # quad edge / marker edge

# Walls (see campus_area.sdf): west wall inner face x=-34.85, east wall inner
# face x=34.85, doorway walls room-side faces x=-15.15 / 15.15.
# yaw=0 -> marker faces +X, yaw=pi -> marker faces -X.
MARKERS = [
    # Delivery points: on the wall behind each yellow pad, at camera height.
    dict(id=1, name='left_delivery_point_1', kind='delivery', size=0.30, x=-34.84, y=-18.0, z=0.60, yaw=0.0),
    dict(id=2, name='left_delivery_point_2', kind='delivery', size=0.30, x=-34.84, y=-6.0, z=0.60, yaw=0.0),
    dict(id=3, name='left_delivery_point_3', kind='delivery', size=0.30, x=-34.84, y=6.0, z=0.60, yaw=0.0),
    dict(id=4, name='left_delivery_point_4', kind='delivery', size=0.30, x=-34.84, y=18.0, z=0.60, yaw=0.0),
    dict(id=5, name='right_delivery_point_1', kind='delivery', size=0.30, x=34.84, y=-18.0, z=0.60, yaw=math.pi),
    dict(id=6, name='right_delivery_point_2', kind='delivery', size=0.30, x=34.84, y=-6.0, z=0.60, yaw=math.pi),
    dict(id=7, name='right_delivery_point_3', kind='delivery', size=0.30, x=34.84, y=6.0, z=0.60, yaw=math.pi),
    dict(id=8, name='right_delivery_point_4', kind='delivery', size=0.30, x=34.84, y=18.0, z=0.60, yaw=math.pi),
    # Room identifiers. *_far: big marker on the far wall, seen straight ahead
    # when entering from the bridge. *_door: beside the doorway, seen from
    # inside the room when heading back to the bridge.
    dict(id=10, name='left_room_far', kind='room', room='left_room', size=1.00, x=-34.84, y=0.0, z=1.50, yaw=0.0),
    dict(id=11, name='left_room_door', kind='room', room='left_room', size=0.60, x=-15.16, y=-4.0, z=1.50, yaw=math.pi),
    dict(id=20, name='right_room_far', kind='room', room='right_room', size=1.00, x=34.84, y=0.0, z=1.50, yaw=math.pi),
    dict(id=21, name='right_room_door', kind='room', room='right_room', size=0.60, x=15.16, y=-4.0, z=1.50, yaw=0.0),
]

DAE = """<?xml version="1.0" encoding="utf-8"?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
  <asset><unit name="meter" meter="1"/><up_axis>Z_UP</up_axis></asset>
  <library_images>
    <image id="marker_png"><init_from>{png}</init_from></image>
  </library_images>
  <library_effects>
    <effect id="marker_effect">
      <profile_COMMON>
        <newparam sid="surf"><surface type="2D"><init_from>marker_png</init_from></surface></newparam>
        <newparam sid="samp"><sampler2D><source>surf</source></sampler2D></newparam>
        <technique sid="common">
          <lambert>
            <emission><color>0.25 0.25 0.25 1</color></emission>
            <ambient><color>1 1 1 1</color></ambient>
            <diffuse><texture texture="samp" texcoord="UVMap"/></diffuse>
          </lambert>
        </technique>
      </profile_COMMON>
    </effect>
  </library_effects>
  <library_materials>
    <material id="marker_mat"><instance_effect url="#marker_effect"/></material>
  </library_materials>
  <library_geometries>
    <geometry id="quad">
      <mesh>
        <source id="pos">
          <float_array id="pos_a" count="12">0 -0.5 -0.5  0 0.5 -0.5  0 0.5 0.5  0 -0.5 0.5</float_array>
          <technique_common><accessor source="#pos_a" count="4" stride="3">
            <param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>
          </accessor></technique_common>
        </source>
        <source id="nrm">
          <float_array id="nrm_a" count="3">1 0 0</float_array>
          <technique_common><accessor source="#nrm_a" count="1" stride="3">
            <param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>
          </accessor></technique_common>
        </source>
        <source id="uv">
          <float_array id="uv_a" count="8">0 0  1 0  1 1  0 1</float_array>
          <technique_common><accessor source="#uv_a" count="4" stride="2">
            <param name="S" type="float"/><param name="T" type="float"/>
          </accessor></technique_common>
        </source>
        <vertices id="verts"><input semantic="POSITION" source="#pos"/></vertices>
        <triangles material="marker_mat" count="2">
          <input semantic="VERTEX" source="#verts" offset="0"/>
          <input semantic="NORMAL" source="#nrm" offset="1"/>
          <input semantic="TEXCOORD" source="#uv" offset="2" set="0"/>
          <p>0 0 0  1 0 1  2 0 2   0 0 0  2 0 2  3 0 3</p>
        </triangles>
      </mesh>
    </geometry>
  </library_geometries>
  <library_visual_scenes>
    <visual_scene id="scene">
      <node id="marker" name="marker">
        <instance_geometry url="#quad">
          <bind_material><technique_common>
            <instance_material symbol="marker_mat" target="#marker_mat">
              <bind_vertex_input semantic="UVMap" input_semantic="TEXCOORD" input_set="0"/>
            </instance_material>
          </technique_common></bind_material>
        </instance_geometry>
      </node>
    </visual_scene>
  </library_visual_scenes>
  <scene><instance_visual_scene url="#scene"/></scene>
</COLLADA>
"""

MODEL_SDF = """<?xml version="1.0" ?>
<sdf version="1.8">
  <model name="aruco_marker_{id}">
    <static>true</static>
    <!-- {dictionary} id {id}, black square {size:.2f} m. Faces +X. -->
    <link name="link">
      <visual name="marker">
        <pose>0.002 0 0 0 0 0</pose>
        <geometry>
          <mesh>
            <uri>model://aruco_marker_{id}/meshes/marker.dae</uri>
            <scale>{quad:.4f} {quad:.4f} {quad:.4f}</scale>
          </mesh>
        </geometry>
        <cast_shadows>false</cast_shadows>
      </visual>
      <visual name="backing">
        <pose>-0.003 0 0 0 0 0</pose>
        <geometry><box><size>0.006 {back:.4f} {back:.4f}</size></box></geometry>
        <material>
          <ambient>1 1 1 1</ambient><diffuse>1 1 1 1</diffuse>
        </material>
      </visual>
    </link>
  </model>
</sdf>
"""

MODEL_CONFIG = """<?xml version="1.0" ?>
<model>
  <name>aruco_marker_{id}</name>
  <version>1.0</version>
  <sdf version="1.8">model.sdf</sdf>
  <description>ArUco {dictionary} marker id {id}</description>
</model>
"""


def marker_image(dictionary, marker_id):
    if hasattr(cv2.aruco, 'generateImageMarker'):        # OpenCV >= 4.7
        img = cv2.aruco.generateImageMarker(dictionary, marker_id, MARKER_PX)
    else:                                                 # OpenCV 4.6 (Ubuntu 24.04)
        img = cv2.aruco.drawMarker(dictionary, marker_id, MARKER_PX)
    return cv2.copyMakeBorder(img, MARGIN_PX, MARGIN_PX, MARGIN_PX, MARGIN_PX,
                              cv2.BORDER_CONSTANT, value=255)


def main():
    pkg = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dict_id = getattr(cv2.aruco, DICTIONARY)
    if hasattr(cv2.aruco, 'getPredefinedDictionary'):
        dictionary = cv2.aruco.getPredefinedDictionary(dict_id)
    else:
        dictionary = cv2.aruco.Dictionary_get(dict_id)

    includes = ['    <!-- ================= ARUCO MARKERS ({}) ================= -->'.format(DICTIONARY),
                '    <!-- Generated by scripts/generate_aruco_models.py; ids and poses are in config/aruco_markers.yaml -->']
    yaml_lines = [
        '# ArUco markers placed in worlds/campus_area.sdf.',
        '# Generated by scripts/generate_aruco_models.py: edit MARKERS there and rerun.',
        '# size = black square edge in metres (use it as the detector marker_size).',
        '# pose = marker centre in the world frame; the marker faces along yaw.',
        'dictionary: {}'.format(DICTIONARY),
        'markers:',
    ]
    for m in MARKERS:
        mid = m['id']
        mdir = os.path.join(pkg, 'models', 'aruco_marker_{}'.format(mid))
        os.makedirs(os.path.join(mdir, 'meshes'), exist_ok=True)
        png = 'aruco_{}.png'.format(mid)
        cv2.imwrite(os.path.join(mdir, 'meshes', png), marker_image(dictionary, mid))
        with open(os.path.join(mdir, 'meshes', 'marker.dae'), 'w') as f:
            f.write(DAE.format(png=png))
        quad = m['size'] * QUAD_SCALE
        with open(os.path.join(mdir, 'model.sdf'), 'w') as f:
            f.write(MODEL_SDF.format(id=mid, size=m['size'], quad=quad,
                                     back=quad + 0.02, dictionary=DICTIONARY))
        with open(os.path.join(mdir, 'model.config'), 'w') as f:
            f.write(MODEL_CONFIG.format(id=mid, dictionary=DICTIONARY))

        includes.append(
            '    <include>\n'
            '      <uri>model://aruco_marker_{id}</uri>\n'
            '      <name>aruco_{name}</name>\n'
            '      <pose>{x} {y} {z} 0 0 {yaw:.5f}</pose>\n'
            '    </include>'.format(**m))
        yaml_lines += [
            '  - id: {}'.format(mid),
            '    name: {}'.format(m['name']),
            '    kind: {}'.format(m['kind']),
            '    room: {}'.format(m.get('room', 'left_room' if m['x'] < 0 else 'right_room')),
            '    size: {}'.format(m['size']),
            '    pose: {{x: {}, y: {}, z: {}, yaw: {:.5f}}}'.format(m['x'], m['y'], m['z'], m['yaw']),
        ]

    with open(os.path.join(pkg, 'config', 'aruco_markers.yaml'), 'w') as f:
        f.write('\n'.join(yaml_lines) + '\n')
    with open(os.path.join(pkg, 'scripts', 'aruco_world_includes.sdf.snippet'), 'w') as f:
        f.write('\n'.join(includes) + '\n')
    print('Wrote {} marker models to {}'.format(len(MARKERS), os.path.join(pkg, 'models')))


if __name__ == '__main__':
    main()
