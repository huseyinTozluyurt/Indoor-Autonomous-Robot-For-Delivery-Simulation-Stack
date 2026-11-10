#!/usr/bin/env python3
"""Generate the two-building delivery world and its ArUco marker config.

Run from the package root (src/indoor_delivery_project):
    python3 scripts/generate_two_buildings_world.py

It writes:
    worlds/two_buildings.sdf               the Gazebo world
    config/aruco_markers_two_buildings.yaml  id -> name, kind, room, world pose, size
    models/aruco_marker_<id>/              only for marker ids that do not exist yet

Layout (top view, x to the right, y up, all sizes are CLEAR inside sizes; the
0.3 m walls sit outside these rectangles):

    building A 15 x 40      short corridors 3 x 7   cross corridor 10 x 28  right corridors 6 x 28  building B 7.5 x 40
    x -28 .. -13            x -13 .. -6             x -6 .. 4               x 4 .. 32               x 32 .. 39.5
    y -20 .. 20             y 7.5..10.5, -10.5..-7.5 y -14 .. 14           y 6..12, -12..-6        y -20 .. 20

Building A has 10 table groups (table + 2 chairs) in two columns; each table
carries a delivery marker on its front face (a_delivery_point_1..10): the left
column faces east, the right column faces west, so both are served from the
aisle between them. The cross corridor has two small desks against its right
(east) wall at y = +-3.5 (middle section), two delivery markers each (c_delivery_point_1..4).
The right corridors (twice as long and wide as before) have 2 desks each on
their outer wall (r_delivery_point_1..4). Building B (a thin 7.5 m wide hall)
keeps 4 wall delivery points (b_delivery_point_1..4). Table markers carry
`standoff: 1.2` so the robot stops 1.2 m in front of the table instead of the
default 2.3 m.

                 +--------+          +------+                                +----+
                 | T    T |          |     T|=====T==========T===============|    |
                 | T    T |==========|      |                                |    |
                 | T    T |          |      |                                | B  |
                 | T    T |==========|      |                                |    |
                 | T    T |          |     T|=====T==========T===============|    |
                 +--------+          +------+                                +----+

The robot spawns in building A at (-17, -17) facing +x (south-east, next to table a10).
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
sys.path.insert(0, HERE)

T = 0.3          # wall thickness
H = 3.0          # wall height
SPAWN = (-17.0, -17.0, 0.0)

BLUE = '0.3 0.3 0.8'
RED = '0.8 0.3 0.3'
GREEN = '0.2 0.7 0.2'
ORANGE = '0.9 0.55 0.15'

# ---- Geometry (clear inside sizes, metres)
AX0, AX1 = -28.0, -13.0          # building A, y -20..20
SX1 = -6.0                       # short corridors x -13..-6 (3 x 7), y bands +-(7.5..10.5)
CX1 = 4.0                        # cross corridor x -6..4 (10 wide), y -14..14 (28 long)
CY = 14.0
RX1 = 32.0                       # right corridors x 4..32 (6 x 28), y bands +-(6..12)
BX = 39.5                        # building B x 32..39.5 (7.5 x 40)
S_IN, S_OUT = 7.5, 10.5          # short corridor band (moved apart, size unchanged)
R_IN, R_OUT = 6.0, 12.0          # right corridor band (moved apart, size unchanged)

# Floors: name, x0, x1, y0, y1, grey level
FLOORS = [
    ('building_a_floor', AX0, AX1, -20, 20, 0.85),
    ('short_corridor_north_floor', AX1, SX1, S_IN, S_OUT, 0.65),
    ('short_corridor_south_floor', AX1, SX1, -S_OUT, -S_IN, 0.65),
    ('cross_corridor_floor', SX1, CX1, -CY, CY, 0.75),
    ('right_corridor_north_floor', CX1, RX1, R_IN, R_OUT, 0.65),
    ('right_corridor_south_floor', CX1, RX1, -R_OUT, -R_IN, 0.65),
    ('building_b_floor', RX1, BX, -20, 20, 0.85),
]

# Walls. The given line is the INSIDE face of the wall; the wall body lies on
# the `out` side of it. ext = (extend start, extend end) by T to close the
# outer corners. Horizontal: ('h', y, x0, x1, out); vertical: ('v', x, y0, y1, out).
WALLS = [
    # ---- building A
    ('building_a_south_wall', 'h', -20, AX0, AX1, -1, (1, 1), BLUE),
    ('building_a_north_wall', 'h', 20, AX0, AX1, +1, (1, 1), BLUE),
    ('building_a_west_wall', 'v', AX0, -20, 20, -1, (1, 1), BLUE),
    ('building_a_east_wall_south', 'v', AX1, -20, -S_OUT, +1, (1, 0), BLUE),
    ('building_a_east_wall_middle', 'v', AX1, -S_IN, S_IN, +1, (0, 0), BLUE),
    ('building_a_east_wall_north', 'v', AX1, S_OUT, 20, +1, (0, 1), BLUE),
    # ---- short corridors (A -> cross corridor), unchanged 3 x 7
    ('short_corridor_north_n_wall', 'h', S_OUT, AX1, SX1, +1, (0, 0), GREEN),
    ('short_corridor_north_s_wall', 'h', S_IN, AX1, SX1, -1, (0, 0), GREEN),
    ('short_corridor_south_n_wall', 'h', -S_IN, AX1, SX1, +1, (0, 0), GREEN),
    ('short_corridor_south_s_wall', 'h', -S_OUT, AX1, SX1, -1, (0, 0), GREEN),
    # ---- cross corridor 10 x 30
    ('cross_corridor_north_wall', 'h', CY, SX1, CX1, +1, (1, 1), ORANGE),
    ('cross_corridor_south_wall', 'h', -CY, SX1, CX1, -1, (1, 1), ORANGE),
    ('cross_corridor_west_wall_south', 'v', SX1, -CY, -S_OUT, -1, (1, 0), ORANGE),
    ('cross_corridor_west_wall_middle', 'v', SX1, -S_IN, S_IN, -1, (0, 0), ORANGE),
    ('cross_corridor_west_wall_north', 'v', SX1, S_OUT, CY, -1, (0, 1), ORANGE),
    ('cross_corridor_east_wall_south', 'v', CX1, -CY, -R_OUT, +1, (1, 0), ORANGE),
    ('cross_corridor_east_wall_middle', 'v', CX1, -R_IN, R_IN, +1, (0, 0), ORANGE),
    ('cross_corridor_east_wall_north', 'v', CX1, R_OUT, CY, +1, (0, 1), ORANGE),
    # ---- right corridors 6 x 28 (cross corridor -> B)
    ('right_corridor_north_n_wall', 'h', R_OUT, CX1, RX1, +1, (0, 0), GREEN),
    ('right_corridor_north_s_wall', 'h', R_IN, CX1, RX1, -1, (0, 0), GREEN),
    ('right_corridor_south_n_wall', 'h', -R_IN, CX1, RX1, +1, (0, 0), GREEN),
    ('right_corridor_south_s_wall', 'h', -R_OUT, CX1, RX1, -1, (0, 0), GREEN),
    # ---- building B
    ('building_b_south_wall', 'h', -20, RX1, BX, -1, (1, 1), RED),
    ('building_b_north_wall', 'h', 20, RX1, BX, +1, (1, 1), RED),
    ('building_b_east_wall', 'v', BX, -20, 20, +1, (1, 1), RED),
    ('building_b_west_wall_south', 'v', RX1, -20, -R_OUT, -1, (1, 0), RED),
    ('building_b_west_wall_middle', 'v', RX1, -R_IN, R_IN, -1, (0, 0), RED),
    ('building_b_west_wall_north', 'v', RX1, R_OUT, 20, -1, (0, 1), RED),
]

E = 0.01   # markers sit 1 cm in front of the wall / table face
PI = math.pi

# ---- Furniture. A table group = solid desk (lidar sees it) + chairs.
# ('name', table centre x, y, size_x, size_y, [chair (x, y) offsets from the table centre])
TABLE_H = 0.75
CHAIR = 0.45
A_COLUMNS = [-25.5, -19.5]          # table centres; desks 0.8 x 1.6
A_ROWS = [16.0, 8.0, 0.0, -8.0, -16.0]
# Left column: delivery side (marker) east, chairs west. Right column: delivery
# side west (both columns are served from the aisle between them), chairs east.
A_FRONT = [+1, -1]                  # +1 = marker on the east face, -1 = west face
TABLES = []
for c, tx in enumerate(A_COLUMNS):
    for r, ty in enumerate(A_ROWS):
        n = c * len(A_ROWS) + r + 1
        cx = -A_FRONT[c] * 0.95
        TABLES.append(('a_table_%d' % n, tx, ty, 0.8, 1.6, [(cx, 0.45), (cx, -0.45)]))
# Cross corridor: two small desks against its right (east) wall in the end
# middle section between the right corridors (y = +-3.5, not at the very middle), each
# 0.5 x 1.2 with a chair at its outer end and two delivery markers on its west face.
CROSS_TABLES = [('c_table_north', CX1 - 0.3, 3.5, 0.5, 1.2, [(0.0, 0.95)]),
                ('c_table_south', CX1 - 0.3, -3.5, 0.5, 1.2, [(0.0, -0.95)])]
# Right corridors: 2 desks in the upper (north) corridor against its north wall
# and 2 in the lower (south) corridor against its south wall, 1.2 x 0.6, chair
# at the east end, marker on the corridor-facing side.
R_TABLE_X = [CX1 + 28 / 3, CX1 + 2 * 28 / 3]          # x = 13.3 and 22.7
R_TABLES = ([('r_table_%d' % (i + 1), x, R_OUT - 0.35, 1.2, 0.6, [(0.85, 0.0)])
             for i, x in enumerate(R_TABLE_X)] +
            [('r_table_%d' % (i + 3), x, -R_OUT + 0.35, 1.2, 0.6, [(0.85, 0.0)])
             for i, x in enumerate(R_TABLE_X)])
TABLES += CROSS_TABLES + R_TABLES

MARKERS = []
# Building A: one delivery marker on the front face of each desk, ids 40-49
for i, (name, tx, ty, sx, sy, _) in enumerate(TABLES[:10]):
    f = A_FRONT[i // len(A_ROWS)]
    MARKERS.append(dict(id=40 + i, name='a_delivery_point_%d' % (i + 1), kind='delivery',
                        room='building_a', size=0.30, x=tx + f * (sx / 2 + E), y=ty, z=0.40,
                        yaw=0.0 if f > 0 else PI, standoff=1.2))
# Cross corridor desks: 2 markers each on the west face, ids 36-39
# (c1, c2 = north desk north/south seat; c3, c4 = south desk north/south seat)
k = 0
for name, tx, ty, sx, sy, _ in CROSS_TABLES:
    for dy in (0.3, -0.3):
        MARKERS.append(dict(id=36 + k, name='c_delivery_point_%d' % (k + 1), kind='delivery',
                            room='cross_corridor', size=0.30, x=tx - sx / 2 - E, y=ty + dy,
                            z=0.40, yaw=PI, standoff=1.2))
        k += 1
# Right corridor desks: r1, r2 = upper corridor (west, east); r3, r4 = lower; ids 12-15
for i, (name, tx, ty, sx, sy, _) in enumerate(R_TABLES):
    up = ty > 0
    MARKERS.append(dict(id=12 + i, name='r_delivery_point_%d' % (i + 1), kind='delivery',
                        room='right_corridor_north' if up else 'right_corridor_south',
                        size=0.30, x=tx, y=ty - sy / 2 - E if up else ty + sy / 2 + E,
                        z=0.40, yaw=-PI / 2 if up else PI / 2, standoff=1.2))
MARKERS += [
    # Building B (thin hall) delivery points: east wall, facing -x (default standoff)
    dict(id=5, name='b_delivery_point_1', kind='delivery', room='building_b', size=0.30, x=BX - E, y=-15.0, z=0.60, yaw=PI),
    dict(id=6, name='b_delivery_point_2', kind='delivery', room='building_b', size=0.30, x=BX - E, y=-5.0, z=0.60, yaw=PI),
    dict(id=7, name='b_delivery_point_3', kind='delivery', room='building_b', size=0.30, x=BX - E, y=5.0, z=0.60, yaw=PI),
    dict(id=8, name='b_delivery_point_4', kind='delivery', room='building_b', size=0.30, x=BX - E, y=15.0, z=0.60, yaw=PI),
    # Room identifiers (same ids/sizes as the campus world, models shared)
    dict(id=10, name='building_a_far', kind='room', room='building_a', size=1.00, x=AX0 + E, y=4.0, z=1.50, yaw=0.0),
    dict(id=11, name='building_a_door', kind='room', room='building_a', size=0.60, x=AX1 - E, y=0.0, z=1.50, yaw=PI),
    dict(id=20, name='building_b_far', kind='room', room='building_b', size=1.00, x=BX - E, y=0.0, z=1.50, yaw=PI),
    dict(id=21, name='building_b_door', kind='room', room='building_b', size=0.60, x=RX1 + E, y=0.0, z=1.50, yaw=0.0),
    # Corridor landmarks (help SLAM in the long corridors)
    dict(id=30, name='cross_corridor_north_end', kind='corridor', room='cross_corridor', size=0.60, x=-1.0, y=CY - E, z=1.20, yaw=-PI / 2),
    dict(id=31, name='cross_corridor_south_end', kind='corridor', room='cross_corridor', size=0.60, x=-1.0, y=-CY + E, z=1.20, yaw=PI / 2),
    dict(id=32, name='cross_corridor_east_mid', kind='corridor', room='cross_corridor', size=0.60, x=CX1 - E, y=0.0, z=1.20, yaw=PI),
    dict(id=33, name='cross_corridor_west_mid', kind='corridor', room='cross_corridor', size=0.60, x=SX1 + E, y=0.0, z=1.20, yaw=0.0),
    dict(id=34, name='right_corridor_north_mid', kind='corridor', room='right_corridor_north', size=0.40, x=18.0, y=R_IN + E, z=1.00, yaw=PI / 2),
    dict(id=35, name='right_corridor_south_mid', kind='corridor', room='right_corridor_south', size=0.40, x=18.0, y=-R_IN - E, z=1.00, yaw=-PI / 2),
]

# Yellow delivery pads 2.35 m in front of each delivery marker (same as campus)
PAD_OFFSET = 2.35


def box_model(name, cx, cy, cz, sx, sy, sz, rgb, collide=True):
    col = ('\n        <collision name="collision"><geometry><box><size>{sx:g} {sy:g} {sz:g}</size></box></geometry></collision>'
           if collide else '')
    return ('    <model name="{name}">\n'
            '      <static>true</static>\n'
            '      <pose>{cx:g} {cy:g} {cz:g} 0 0 0</pose>\n'
            '      <link name="link">' + col + '\n'
            '        <visual name="visual">\n'
            '          <geometry><box><size>{sx:g} {sy:g} {sz:g}</size></box></geometry>\n'
            '          <material><ambient>{rgb} 1</ambient><diffuse>{rgb} 1</diffuse></material>\n'
            '        </visual>\n'
            '      </link>\n'
            '    </model>\n').format(name=name, cx=cx, cy=cy, cz=cz, sx=sx, sy=sy, sz=sz, rgb=rgb)


def wall_model(name, ori, c, a0, a1, out, ext, rgb):
    a0 -= T * ext[0]
    a1 += T * ext[1]
    mid, length = (a0 + a1) / 2, a1 - a0
    off = c + out * T / 2
    if ori == 'h':
        return box_model(name, mid, off, H / 2, length, T, H, rgb)
    return box_model(name, off, mid, H / 2, T, length, H, rgb)


def pad_model(m):
    x = m['x'] + PAD_OFFSET * math.cos(m['yaw'])
    y = m['y'] + PAD_OFFSET * math.sin(m['yaw'])
    return ('    <model name="{name}">\n'
            '      <static>true</static>\n'
            '      <pose>{x:.2f} {y:.2f} 0.06 0 0 0</pose>\n'
            '      <link name="link">\n'
            '        <visual name="visual">\n'
            '          <geometry><cylinder><radius>0.8</radius><length>0.02</length></cylinder></geometry>\n'
            '          <material>\n'
            '            <ambient>1.0 0.85 0.1 1</ambient>\n'
            '            <diffuse>1.0 0.85 0.1 1</diffuse>\n'
            '            <emissive>0.15 0.12 0.02 1</emissive>\n'
            '          </material>\n'
            '        </visual>\n'
            '      </link>\n'
            '    </model>\n').format(name=m['name'], x=x, y=y)


WOOD = '0.55 0.35 0.18'
SEAT = '0.25 0.25 0.3'


def table_group(name, tx, ty, sx, sy, chairs):
    """Solid desk (body down to the floor so the low lidar sees it) + chairs."""
    links = ['      <link name="table">',
             '        <pose>0 0 0 0 0 0</pose>']
    links += _box('top', 0, 0, TABLE_H - 0.025, sx + 0.1, sy + 0.1, 0.05, WOOD)
    links += _box('body', 0, 0, (TABLE_H - 0.05) / 2, sx, sy, TABLE_H - 0.05, WOOD)
    links.append('      </link>')
    for i, (dx, dy) in enumerate(chairs):
        links += ['      <link name="chair_%d">' % (i + 1), '        <pose>0 0 0 0 0 0</pose>']
        links += _box('seat', dx, dy, 0.225, CHAIR, CHAIR, 0.45, SEAT)
        b = CHAIR / 2 - 0.03                         # backrest on the side away from the table
        if abs(dx) >= abs(dy):
            links += _box('back', dx + math.copysign(b, dx), dy, 0.68, 0.06, CHAIR, 0.45, SEAT)
        else:
            links += _box('back', dx, dy + math.copysign(b, dy), 0.68, CHAIR, 0.06, 0.45, SEAT)
        links.append('      </link>')
    return ('    <model name="{n}">\n      <static>true</static>\n'
            '      <pose>{x:g} {y:g} 0.05 0 0 0</pose>\n{body}\n    </model>\n').format(
                n=name, x=tx, y=ty, body='\n'.join(links))


def _box(name, x, y, z, sx, sy, sz, rgb):
    g = '<geometry><box><size>{:g} {:g} {:g}</size></box></geometry>'.format(sx, sy, sz)
    p = '<pose>{:g} {:g} {:g} 0 0 0</pose>'.format(x, y, z)
    return ['        <collision name="{}_c">{}{}</collision>'.format(name, p, g),
            '        <visual name="{}_v">{}{}<material><ambient>{} 1</ambient>'
            '<diffuse>{} 1</diffuse></material></visual>'.format(name, p, g, rgb, rgb)]


HEADER = """<?xml version="1.0" ?>
<!-- Generated by scripts/generate_two_buildings_world.py: edit it there and rerun. -->
<sdf version="1.8">
  <world name="two_buildings_world">

    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <!-- IMU sensors only publish when this system is loaded (gyro for the mapper) -->
    <plugin filename="gz-sim-imu-system" name="gz::sim::systems::Imu"/>
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">
      <render_engine>ogre2</render_engine>
    </plugin>

    <gravity>0 0 -9.8</gravity>

    <scene>
      <ambient>0.6 0.6 0.6 1</ambient>
      <background>0.7 0.7 0.7 1</background>
    </scene>

    <light type="directional" name="fill_light">
      <cast_shadows>false</cast_shadows>
      <pose>0 0 10 0 0 0</pose>
      <diffuse>0.5 0.5 0.5 1</diffuse>
      <specular>0.05 0.05 0.05 1</specular>
      <direction>0.5 -0.1 -0.6</direction>
    </light>

    <light type="directional" name="sun">
      <cast_shadows>true</cast_shadows>
      <pose>0 0 10 0 0 0</pose>
      <diffuse>0.8 0.8 0.8 1</diffuse>
      <specular>0.2 0.2 0.2 1</specular>
      <direction>-0.5 0.1 -0.9</direction>
    </light>

    <model name="ground_plane">
      <static>true</static>
      <link name="link">
        <collision name="collision">
          <geometry><plane><normal>0 0 1</normal><size>200 200</size></plane></geometry>
        </collision>
        <visual name="visual">
          <geometry><plane><normal>0 0 1</normal><size>200 200</size></plane></geometry>
          <material><ambient>0.7 0.7 0.7 1</ambient><diffuse>0.7 0.7 0.7 1</diffuse></material>
        </visual>
      </link>
    </model>

    <!-- =========================================================
         Building A 15 x 40 m  (x -28..-13, y -20..20)  robot spawn (-17, -17)
         Short corridors 3 x 7 m (x -13..-6) at y 7.5..10.5 and -10.5..-7.5
         Cross corridor 10 x 28 m (x -6..4, y -14..14)
         Right corridors 6 x 28 m (x 4..32) at y 6..12 and -12..-6
         Building B 7.5 x 40 m thin hall (x 32..39.5, y -20..20)
         10 table groups in A, 2 desks in the cross corridor, 4 in the right corridors
         Clear inside sizes; walls 0.3 m thick, 3 m high, outside the rectangles.
         ========================================================= -->

"""


def main():
    parts = [HEADER, '    <!-- ================= FLOORS ================= -->\n']
    for name, x0, x1, y0, y1, g in FLOORS:
        parts.append(box_model(name, (x0 + x1) / 2, (y0 + y1) / 2, 0.025,
                               x1 - x0, y1 - y0, 0.05, f'{g} {g} {g}'))
    parts.append('\n    <!-- ================= WALLS ================= -->\n')
    for name, ori, c, a0, a1, out, ext, rgb in WALLS:
        parts.append(wall_model(name, ori, c, a0, a1, out, ext, rgb))
    parts.append('\n    <!-- ================= DELIVERY PADS ================= -->\n')
    for m in MARKERS:
        if m['kind'] == 'delivery' and 'standoff' not in m:
            parts.append(pad_model(m))
    parts.append('\n    <!-- ================= TABLES AND CHAIRS ================= -->\n')
    for t in TABLES:
        parts.append(table_group(*t))
    parts.append('\n    <!-- ================= ARUCO MARKERS (DICT_4X4_50) ================= -->\n'
                 '    <!-- ids and poses: config/aruco_markers_two_buildings.yaml -->\n')
    for m in MARKERS:
        parts.append('    <include>\n'
                     '      <uri>model://aruco_marker_{id}</uri>\n'
                     '      <name>aruco_{name}</name>\n'
                     '      <pose>{x:g} {y:g} {z:g} 0 0 {yaw:.5f}</pose>\n'
                     '    </include>\n'.format(**m))
    parts.append('\n  </world>\n</sdf>\n')
    with open(os.path.join(PKG, 'worlds', 'two_buildings.sdf'), 'w') as f:
        f.write(''.join(parts))

    lines = [
        '# ArUco markers placed in worlds/two_buildings.sdf.',
        '# Generated by scripts/generate_two_buildings_world.py: edit MARKERS there and rerun.',
        '# size = black square edge in metres; pose = marker centre in the world frame,',
        '# the marker faces along yaw. kind: delivery | room | corridor.',
        '# standoff = how far in front of the marker the delivery point is (default 2.3 m).',
        'dictionary: DICT_4X4_50',
        'markers:',
    ]
    for m in MARKERS:
        lines += ['  - id: {}'.format(m['id']),
                  '    name: {}'.format(m['name']),
                  '    kind: {}'.format(m['kind']),
                  '    room: {}'.format(m['room']),
                  '    size: {}'.format(m['size']),
                  '    pose: {{x: {:g}, y: {:g}, z: {:g}, yaw: {:.5f}}}'.format(
                      m['x'], m['y'], m['z'], m['yaw'])]
        if 'standoff' in m:
            lines.append('    standoff: {}'.format(m['standoff']))
    with open(os.path.join(PKG, 'config', 'aruco_markers_two_buildings.yaml'), 'w') as f:
        f.write('\n'.join(lines) + '\n')

    # Marker models: create only the ids that are missing (existing campus
    # models are shared, and their sizes match the ones used here).
    missing = [m for m in MARKERS
               if not os.path.isdir(os.path.join(PKG, 'models', 'aruco_marker_{}'.format(m['id'])))]
    if missing:
        import cv2
        import generate_aruco_models as g
        dictionary = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, g.DICTIONARY))
        for m in missing:
            mid = m['id']
            mdir = os.path.join(PKG, 'models', 'aruco_marker_{}'.format(mid))
            os.makedirs(os.path.join(mdir, 'meshes'), exist_ok=True)
            png = 'aruco_{}.png'.format(mid)
            cv2.imwrite(os.path.join(mdir, 'meshes', png), g.marker_image(dictionary, mid))
            with open(os.path.join(mdir, 'meshes', 'marker.dae'), 'w') as f:
                f.write(g.DAE.format(png=png))
            quad = m['size'] * g.QUAD_SCALE
            with open(os.path.join(mdir, 'model.sdf'), 'w') as f:
                f.write(g.MODEL_SDF.format(id=mid, size=m['size'], quad=quad,
                                           back=quad + 0.02, dictionary=g.DICTIONARY))
            with open(os.path.join(mdir, 'model.config'), 'w') as f:
                f.write(g.MODEL_CONFIG.format(id=mid, dictionary=g.DICTIONARY))
        print('Created marker models:', ', '.join(str(m['id']) for m in missing))
    print('Wrote worlds/two_buildings.sdf and config/aruco_markers_two_buildings.yaml '
          '({} markers)'.format(len(MARKERS)))


if __name__ == '__main__':
    main()
