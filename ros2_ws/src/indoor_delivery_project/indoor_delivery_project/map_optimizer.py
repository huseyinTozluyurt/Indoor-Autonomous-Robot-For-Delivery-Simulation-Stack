#!/usr/bin/env python3
"""Correct the whole trajectory after mapping, then redraw the map.

aruco_slam_mapper runs this when it finishes only with post_correction:=true
(default false). It can also be run on any saved map folder:

    ros2 run indoor_delivery_project optimize_map ~/ros2_jazzy_ws/maps/campus3

Method (graph SLAM, solved offline on everything that was recorded):

  * Nodes: robot keyframes every ~0.3 m / 10 deg, plus every ArUco marker.
  * Odometry edges between consecutive keyframes: wheel distance and gyro
    heading (dead reckoning recorded by the mapper).
  * Marker edges: every detection (range, bearing) ties a keyframe to its
    marker. Marker IDs make the data association exact.
  * Lidar loop edges: the scans are split into time chunks. Each keyframe scan
    is matched against the map drawn by all the *other* chunks, so when the
    robot comes back to a place, the old and new scans pull together.
  * Gauss-Newton with robust (Cauchy) weights; the block-tridiagonal structure
    is solved exactly with numpy only (no scipy needed). Three rounds of
    "draw map -> match scans -> optimize".

Writes into a sub-folder <map_dir>/corrected/ and never touches the live map
(map.pgm/map.yaml, aruco_landmarks.yaml, map_preview.png in <map_dir> stay
exactly as the mapper drew them). The sub-folder holds map.pgm/map.yaml,
aruco_landmarks.yaml, map_preview.png, trajectory_corrected.csv and
correction_report.txt, so the navigator can use it directly with
map_dir:=<map_dir>/corrected if the corrected map is the better one.
"""
import argparse
import csv
import math
import os
import sys

import cv2
import numpy as np
import yaml

try:
    from indoor_delivery_project.aruco_slam_mapper import (
        OccupancyGrid2D, ScanMatcher, compose, inverse, wrap)
except ImportError:                         # run as a plain script
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from aruco_slam_mapper import (  # noqa: E402
        OccupancyGrid2D, ScanMatcher, compose, inverse, wrap)


# --------------------------------------------------------------- helpers
def _rt(th):
    c, s = math.cos(th), math.sin(th)
    return np.array([[c, s], [-s, c]])                  # R(th)^T


def _drt(th):
    c, s = math.cos(th), math.sin(th)
    return np.array([[-s, c], [-c, -s]])                # d R(th)^T / d th


def _new_grid(origin, shape, res):
    g = OccupancyGrid2D.__new__(OccupancyGrid2D)
    g.res = res
    g.origin = origin
    g.logodds = np.zeros(shape, np.float32)
    g.seen = np.zeros(shape, bool)
    return g


def _draw(grid, pose, pts, hit, lo):
    c, s = math.cos(pose[2]), math.sin(pose[2])
    world = np.stack([pose[0] + c * pts[:, 0] - s * pts[:, 1],
                      pose[1] + s * pts[:, 0] + c * pts[:, 1]], 1)
    origin = (pose[0] + c * lo[0] - s * lo[1], pose[1] + s * lo[0] + c * lo[1])
    grid.update_scan(origin, world, hit)


def solve_block_tridiagonal(D, U, R):
    """Solve A X = R for SPD block-tridiagonal A (diag blocks D[i], upper U[i]).
    R: (K, 3, m). Returns X with the same shape."""
    K = len(D)
    S = np.empty_like(D)
    Y = np.empty_like(R)
    S[0] = D[0]
    Y[0] = R[0]
    for i in range(1, K):
        G = np.linalg.solve(S[i - 1], U[i - 1]).T       # U^T S^-1 (S symmetric)
        S[i] = D[i] - G @ U[i - 1]
        Y[i] = R[i] - G @ Y[i - 1]
    X = np.empty_like(R)
    X[K - 1] = np.linalg.solve(S[K - 1], Y[K - 1])
    for i in range(K - 2, -1, -1):
        X[i] = np.linalg.solve(S[i], Y[i] - U[i] @ X[i + 1])
    return X


# --------------------------------------------------------------- the graph
class PoseGraph:
    def __init__(self, poses, landmarks):
        self.x = np.array(poses, float)                 # (K, 3)
        self.lm_ids = sorted(landmarks)
        self.lm_index = {m: j for j, m in enumerate(self.lm_ids)}
        self.L = np.array([landmarks[m] for m in self.lm_ids], float).reshape(-1, 2)
        self.odom = []          # (i, z(3), info(3x3))
        self.marks = []         # (i, lm j, p(2), info(2x2))
        self.unary = []         # (i, z(3), info(3x3))
        self.anchor = None      # (i, z, info)

    def solve(self, iterations=8, robust=3.0, log=None):
        K, M = len(self.x), len(self.L)
        for it in range(iterations):
            D = np.zeros((K, 3, 3))
            U = np.zeros((max(K - 1, 1), 3, 3))
            B = np.zeros((K, 3, 2 * M))
            C = np.zeros((2 * M, 2 * M))
            gp = np.zeros((K, 3))
            gl = np.zeros(2 * M)
            chi = 0.0

            def weight(e, info):
                m2 = float(e @ info @ e)
                return 1.0 / (1.0 + m2 / robust ** 2), m2

            for i, z, info in self.odom:
                j = i + 1
                xi, xj = self.x[i], self.x[j]
                dt = xj[:2] - xi[:2]
                e = np.r_[_rt(xi[2]) @ dt - z[:2], wrap(xj[2] - xi[2] - z[2])]
                Ji = np.zeros((3, 3))
                Ji[:2, :2] = -_rt(xi[2])
                Ji[:2, 2] = _drt(xi[2]) @ dt
                Ji[2, 2] = -1.0
                Jj = np.zeros((3, 3))
                Jj[:2, :2] = _rt(xi[2])
                Jj[2, 2] = 1.0
                w, m2 = weight(e, info)
                chi += m2
                W = w * info
                D[i] += Ji.T @ W @ Ji
                D[j] += Jj.T @ W @ Jj
                U[i] += Ji.T @ W @ Jj
                gp[i] -= Ji.T @ W @ e
                gp[j] -= Jj.T @ W @ e
            for i, j, p, info in self.marks:
                xi = self.x[i]
                d = self.L[j] - xi[:2]
                e = _rt(xi[2]) @ d - p
                Ji = np.zeros((2, 3))
                Ji[:, :2] = -_rt(xi[2])
                Ji[:, 2] = _drt(xi[2]) @ d
                Jl = _rt(xi[2])
                w, m2 = weight(e, info)
                chi += m2
                W = w * info
                D[i] += Ji.T @ W @ Ji
                B[i, :, 2 * j:2 * j + 2] += Ji.T @ W @ Jl
                C[2 * j:2 * j + 2, 2 * j:2 * j + 2] += Jl.T @ W @ Jl
                gp[i] -= Ji.T @ W @ e
                gl[2 * j:2 * j + 2] -= Jl.T @ W @ e
            for i, z, info in self.unary + ([self.anchor] if self.anchor else []):
                e = self.x[i] - z
                e[2] = wrap(e[2])
                w, m2 = weight(e, info)
                if info[0, 0] > 1e6:            # the anchor is never down-weighted
                    w = 1.0
                chi += m2
                D[i] += w * info
                gp[i] -= w * info @ e
            # tiny damping keeps every block invertible
            D += np.eye(3) * 1e-6
            C += np.eye(2 * M) * 1e-6 if M else 0.0
            if M:
                rhs = np.concatenate([gp[:, :, None], B], axis=2)       # (K, 3, 1+2M)
                X = solve_block_tridiagonal(D, U, rhs)
                Ainv_g, Ainv_B = X[:, :, 0], X[:, :, 1:]
                Bf = B.reshape(3 * K, 2 * M)
                S = C - Bf.T @ Ainv_B.reshape(3 * K, 2 * M)
                dl = np.linalg.solve(S, gl - Bf.T @ Ainv_g.reshape(-1))
                dp = Ainv_g - (Ainv_B.reshape(3 * K, 2 * M) @ dl).reshape(K, 3)
                self.L += dl.reshape(M, 2)
            else:
                dp = solve_block_tridiagonal(D, U, gp[:, :, None])[:, :, 0]
            self.x += dp
            self.x[:, 2] = np.arctan2(np.sin(self.x[:, 2]), np.cos(self.x[:, 2]))
            step = float(np.abs(dp[:, :2]).max()) if K else 0.0
            if log:
                log(f'    iteration {it + 1}: cost {chi:.0f}, largest step {step:.3f} m')
            if step < 1e-3:
                break


# --------------------------------------------------------------- main work
def load_folder(d):
    z = np.load(os.path.join(d, 'scans.npz'))
    traj = z['traj']
    if traj.shape[1] >= 10:
        dr = traj[:, 7:10]
    else:                                   # older mapper: wheel odometry only
        dr = traj[:, 4:7]
    obs = []
    path = os.path.join(d, 'observations.csv')
    if os.path.isfile(path):
        with open(path) as f:
            for row in csv.DictReader(f):
                o = {k: (v if k == 'name' else float(v)) for k, v in row.items() if v != ''}
                if 'dr_x' not in o:
                    o['dr_x'], o['dr_y'] = o['odom_x'], o['odom_y']
                    o['dr_yaw_deg'] = o['odom_yaw_deg']
                obs.append(o)
    lm_file = os.path.join(d, 'aruco_landmarks_online.yaml')
    if not os.path.isfile(lm_file):
        lm_file = os.path.join(d, 'aruco_landmarks.yaml')
    with open(lm_file) as f:
        doc = yaml.safe_load(f)
    return z, traj, dr, obs, doc


def optimize_map_dir(d, log=print, chunks=8, rounds=3, kf_dist=0.3, kf_angle=0.17):
    d = os.path.expanduser(d)
    z, traj, dr, obs, doc = load_folder(d)
    pts_all = z['points'].astype(np.float32)
    hit_all = z['hit']
    off = z['offsets']
    lo = z['laser_origin']
    n = len(traj)
    if n < 5:
        log('Too few scans to optimize.')
        return None

    cd = os.path.join(d, 'corrected')     # the live map in d is never overwritten
    os.makedirs(cd, exist_ok=True)

    # ---- keyframes
    kf = [0]
    for k in range(1, n):
        a = dr[kf[-1]]
        b = dr[k]
        if math.hypot(b[0] - a[0], b[1] - a[1]) >= kf_dist or \
                abs(wrap(b[2] - a[2])) >= kf_angle:
            kf.append(k)
    if kf[-1] != n - 1:
        kf.append(n - 1)
    kf = np.array(kf)
    K = len(kf)
    log(f'Trajectory correction: {n} scans, {K} keyframes, {len(obs)} marker detections')

    online = traj[:, 1:4]
    start = doc.get('start_pose') or {'x': online[0, 0], 'y': online[0, 1], 'yaw': online[0, 2]}
    lms = {int(m['id']): (m['x'], m['y']) for m in doc.get('markers', [])}
    g = PoseGraph(online[kf], lms)
    g.anchor = (0, np.array([start['x'], start['y'], start['yaw']], float),
                np.diag([1e8, 1e8, 1e8]))

    # ---- odometry edges (wheel distance + gyro heading)
    odom_yaw = traj[:, 6]
    gyro = not np.allclose(np.cos(dr[:, 2] - odom_yaw), 1.0, atol=1e-6)
    turn_noise = 0.02 if gyro else 0.15     # without a gyro the wheels slip in turns
    if not gyro:
        log('  no gyro heading in this run: turns are trusted less')
    for i in range(K - 1):
        zz = np.array(compose(inverse(tuple(dr[kf[i]])), tuple(dr[kf[i + 1]])))
        dist = math.hypot(zz[0], zz[1])
        sxy = 0.01 + 0.03 * dist
        sth = 0.003 + turn_noise * abs(zz[2]) + 0.005 * dist
        g.odom.append((i, zz, np.diag([1 / sxy ** 2, 1 / sxy ** 2, 1 / sth ** 2])))

    # ---- marker edges
    kf_t = traj[kf, 0]
    n_marks = n_spin = 0
    # turn rate at each detection (gyro heading of the path): during fast spins a
    # little camera timing error is a large bearing error, so those count less
    t_all = traj[:, 0]
    yaw_unw = np.unwrap(dr[:, 2])

    def turn_rate(t):
        return abs(np.interp(t + 0.1, t_all, yaw_unw) - np.interp(t - 0.1, t_all, yaw_unw)) / 0.2
    for o in obs:
        mid = int(o['marker_id'])
        if mid not in g.lm_index:
            continue
        rate = turn_rate(o['t'])
        if rate > 0.5:
            n_spin += 1
            continue
        i = int(np.clip(np.searchsorted(kf_t, o['t'], side='right') - 1, 0, K - 1))
        dr_o = (o['dr_x'], o['dr_y'], math.radians(o['dr_yaw_deg']))
        delta = compose(inverse(tuple(dr[kf[i]])), dr_o)
        r, b = o['range_2d_m'], math.radians(o['bearing_deg'])
        ang = delta[2] + b
        p = np.array([delta[0] + r * math.cos(ang), delta[1] + r * math.sin(ang)])
        sr = max(0.05, 0.02 * r)
        sb = 0.015 * r + 0.02 + 0.03 * math.hypot(delta[0], delta[1]) + 0.1 * rate * r
        Rm = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
        cov = Rm @ np.diag([sr ** 2, sb ** 2]) @ Rm.T
        g.marks.append((i, g.lm_index[mid], p, np.linalg.inv(cov)))
        n_marks += 1
    log(f'  {K - 1} odometry edges, {n_marks} marker edges, {len(g.lm_ids)} markers'
        f' ({n_spin} detections during fast turns left out)')

    # ---- map frame for drawing: everything the lidar can reach from the path
    res = 0.1
    if os.path.isfile(os.path.join(d, 'map.yaml')):
        with open(os.path.join(d, 'map.yaml')) as f:
            res = float(yaml.safe_load(f).get('resolution', 0.1))
    # laser reach (points are in base_link) + room for the correction itself
    reach = float(np.hypot(pts_all[:, 0], pts_all[:, 1]).max()) + 5.0 if len(pts_all) else 25.0
    lo_xy = online[:, :2].min(axis=0) - reach
    hi_xy = online[:, :2].max(axis=0) + reach
    origin = (math.floor(lo_xy[0]), math.floor(lo_xy[1]))
    shape = (int(math.ceil((hi_xy[1] - origin[1]) / res)), int(math.ceil((hi_xy[0] - origin[0]) / res)))

    def scan(k):
        return pts_all[off[k]:off[k + 1]], hit_all[off[k]:off[k + 1]]

    chunk_of = np.minimum((np.arange(K) * chunks) // K, chunks - 1)
    fine = ScanMatcher()
    coarse = ScanMatcher(search_xy=0.6, step_xy=0.1, search_th=0.2, step_th=0.02,
                         min_quality=0.35)
    g.solve(iterations=6, log=log)               # odometry + markers first
    n_loops = 0
    for rnd in range(rounds):
        # draw one grid per time chunk from the keyframe scans
        grids = [_new_grid(origin, shape, res) for _ in range(chunks)]
        for i in range(K):
            p, h = scan(kf[i])
            _draw(grids[chunk_of[i]], g.x[i], p, h, lo)
        total = np.sum([gr.logodds for gr in grids], axis=0)
        g.unary = []
        n_loops = 0
        for c in range(chunks):
            other = _new_grid(origin, shape, res)
            other.logodds = np.clip(total - grids[c].logodds, -4.0, 4.0)
            field = fine.field(other)
            if field is None:
                continue
            for i in np.nonzero(chunk_of == c)[0]:
                p, h = scan(kf[i])
                hits = p[h]
                if len(hits) < 40:
                    continue
                pose = tuple(g.x[i])
                res_c = coarse.match(field, pose, hits) if rnd == 0 else None
                start_pose = res_c[0] if res_c is not None else pose
                res_f = fine.match(field, start_pose, hits)
                if res_f is None:
                    continue
                cov = res_f[1] + np.diag([0.03 ** 2, 0.03 ** 2, 0.008 ** 2])
                g.unary.append((i, np.array(res_f[0]), np.linalg.inv(cov)))
                n_loops += 1
        log(f'  round {rnd + 1}/{rounds}: {n_loops} keyframes matched against the '
            f'other parts of the map')
        g.solve(iterations=6, log=log)

    # ---- corrected pose for every scan (blend of both neighbouring keyframes)
    corrected = np.zeros((n, 3))
    seg = np.clip(np.searchsorted(kf, np.arange(n), side='right') - 1, 0, K - 1)
    for k in range(n):
        i = seg[k]
        a = compose(tuple(g.x[i]), compose(inverse(tuple(dr[kf[i]])), tuple(dr[k])))
        if i + 1 < K and kf[i + 1] > kf[i]:
            j = i + 1
            b = compose(tuple(g.x[j]), compose(inverse(tuple(dr[kf[j]])), tuple(dr[k])))
            f = (k - kf[i]) / float(kf[j] - kf[i])
            th = math.atan2((1 - f) * math.sin(a[2]) + f * math.sin(b[2]),
                            (1 - f) * math.cos(a[2]) + f * math.cos(b[2]))
            a = ((1 - f) * a[0] + f * b[0], (1 - f) * a[1] + f * b[1], th)
        corrected[k] = a

    # ---- redraw the map with every scan
    grid = _new_grid(origin, shape, res)
    for k in range(n):
        p, h = scan(k)
        _draw(grid, corrected[k], p, h, lo)
        grid.clear_disk(corrected[k, :2], 0.3)
    grid.save(cd, 'map')

    # ---- markers and delivery points
    facing = {}
    for o in obs:
        mid = int(o['marker_id'])
        if mid not in g.lm_index:
            continue
        k = int(np.clip(np.searchsorted(traj[:, 0], o['t']), 0, n - 1))
        pose_o = compose(tuple(corrected[k]), compose(
            inverse(tuple(dr[k])), (o['dr_x'], o['dr_y'], math.radians(o['dr_yaw_deg']))))
        fy = pose_o[2] + math.radians(o['marker_facing_deg'])
        w = 1.0 / max(o['range_2d_m'], 1.0) ** 2
        f = facing.setdefault(mid, [0.0, 0.0])
        f[0] += w * math.cos(fy)
        f[1] += w * math.sin(fy)
    standoff = float(doc.get('delivery_standoff', 2.3))
    old = {int(m['id']): m for m in doc.get('markers', [])}
    markers, delivery, lines = [], {}, []
    for mid in g.lm_ids:
        x, y = (float(v) for v in g.L[g.lm_index[mid]])
        m = dict(old[mid])
        yaw = math.atan2(facing[mid][1], facing[mid][0]) if mid in facing else m.get('yaw')
        lines.append(f'  id {mid:>3} {m.get("name", "")}: moved '
                     f'{math.hypot(x - m["x"], y - m["y"]):.2f} m by the correction')
        m.update({'x': round(x, 3), 'y': round(y, 3),
                  'yaw': round(float(yaw), 4) if yaw is not None else None})
        markers.append(m)
        if m.get('kind') == 'delivery' and yaw is not None:
            so = float(m.get('standoff', standoff))
            delivery[m['name']] = {'x': round(x + so * math.cos(yaw), 3),
                                   'y': round(y + so * math.sin(yaw), 3),
                                   'yaw': round(wrap(yaw + math.pi), 4), 'marker_id': mid}
    delivery['home'] = (doc.get('delivery_points') or {}).get(
        'home', {'x': start['x'], 'y': start['y'], 'yaw': start['yaw'], 'marker_id': None})
    out = dict(doc)
    out.update({'occupancy_map': 'map.yaml', 'markers': markers, 'delivery_points': delivery,
                'trajectory_corrected': True})
    with open(os.path.join(cd, 'aruco_landmarks.yaml'), 'w') as f:
        f.write('# ArUco landmark map (trajectory corrected after mapping by map_optimizer).\n'
                '# x, y in metres (map frame); yaw = direction the marker faces.\n'
                '# The live map in the parent folder is left unchanged.\n')
        yaml.safe_dump(out, f, sort_keys=False)

    with open(os.path.join(cd, 'trajectory_corrected.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['t', 'x', 'y', 'yaw', 'online_x', 'online_y', 'online_yaw'])
        for k in range(n):
            w.writerow([f'{traj[k, 0]:.3f}'] + [f'{v:.4f}' for v in corrected[k]] +
                       [f'{v:.4f}' for v in online[k]])
    shift = np.hypot(*(corrected[:, :2] - online[:, :2]).T)
    dyaw = np.degrees(np.abs(np.arctan2(np.sin(corrected[:, 2] - online[:, 2]),
                                        np.cos(corrected[:, 2] - online[:, 2]))))
    report = [f'Trajectory corrected after mapping: {cd} (the live map in {d} is unchanged)',
              f'{n} scans, {K} keyframes, {n_marks} marker detections, '
              f'{n_loops} lidar loop matches',
              f'Online path vs corrected: mean {shift.mean():.2f} m / {dyaw.mean():.1f} deg, '
              f'max {shift.max():.2f} m / {dyaw.max():.1f} deg',
              'Markers:'] + lines
    with open(os.path.join(cd, 'correction_report.txt'), 'w') as f:
        f.write('\n'.join(report) + '\n')
    for line in report:
        log(line)
    _preview(cd, grid, corrected, online, markers, delivery)
    return corrected


def _preview(d, grid, corrected, online, markers, delivery):
    r0, r1, c0, c1 = grid.known_bbox()
    t = grid.ternary()[r0:r1, c0:c1]
    img = np.full(t.shape + (3,), 205, np.uint8)
    img[t == 0] = (255, 255, 255)
    img[t == 100] = (0, 0, 0)
    scale = max(1, int(round(1200 / max(t.shape))))
    img = cv2.resize(img, (t.shape[1] * scale, t.shape[0] * scale),
                     interpolation=cv2.INTER_NEAREST)

    def px(x, y):
        return (int(((x - grid.origin[0]) / grid.res - c0) * scale),
                int(((y - grid.origin[1]) / grid.res - r0) * scale))

    for i in range(1, len(corrected)):
        cv2.line(img, px(*online[i - 1, :2]), px(*online[i, :2]), (150, 150, 255), 1)
    for i in range(1, len(corrected)):
        cv2.line(img, px(*corrected[i - 1, :2]), px(*corrected[i, :2]), (220, 120, 0), 1)
    for m in markers:
        cv2.circle(img, px(m['x'], m['y']), 5, (0, 0, 255), -1)
    for p in delivery.values():
        cv2.drawMarker(img, px(p['x'], p['y']), (0, 160, 255), cv2.MARKER_STAR, 12, 2)
    img = np.ascontiguousarray(np.flipud(img))
    img = cv2.copyMakeBorder(img, 50, 0, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    cv2.putText(img, 'blue: corrected path   pink: live (online) path   red: markers',
                (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    cv2.putText(img, 'stars: delivery points', (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (0, 0, 0), 1)
    cv2.imwrite(os.path.join(d, 'map_preview.png'), img)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Correct the whole trajectory of a saved '
                                             'aruco_slam_mapper run and redraw its map.')
    ap.add_argument('map_dir', help='folder written by aruco_slam_mapper (with scans.npz)')
    ap.add_argument('--rounds', type=int, default=3, help='draw/match/optimize rounds')
    ap.add_argument('--chunks', type=int, default=8, help='time chunks for loop matching')
    a = ap.parse_args(argv)
    d = os.path.expanduser(a.map_dir)
    if not os.path.isfile(os.path.join(d, 'scans.npz')):
        sys.exit(f'{d}/scans.npz not found: map with the current aruco_slam_mapper first.')
    optimize_map_dir(d, rounds=a.rounds, chunks=a.chunks)


if __name__ == '__main__':
    main()
