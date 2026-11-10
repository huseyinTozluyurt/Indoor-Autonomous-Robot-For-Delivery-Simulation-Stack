#!/usr/bin/env python3
"""Correct a later mapping run using the first (trusted) map as the base.

The first good map is the reference and has priority. A later run (made with
aruco_slam_mapper.py, which saves scans.npz) is re-processed offline:

  1. Every saved lidar scan is re-aligned onto the base map. The prediction is
     the run's own wheel odometry; correlative scan matching against the base
     occupancy grid gives the corrected pose. Where the run leaves the area
     the base map knows, the scan is matched against what this run has
     already mapped instead (plain SLAM), so new areas can be added too.
  2. Slips are detected by comparing, over a short window, how far and how
     much the robot turned according to the wheels and according to the
     corrected trajectory. Every place where they disagree by more than the
     thresholds is reported as a slip event (time, position, size).
  3. The run is redrawn with the corrected poses and merged:
       * cells the base map knows keep the base value (base wins);
       * cells only this run has seen are added;
       * cells where the run disagrees strongly with the base are counted
         and drawn as "changes" (with --accept-changes they are applied,
         e.g. for furniture that was moved).
     Markers: base markers keep their position; markers the base does not
     have are added from the corrected run, and delivery points with them.

Usage (no simulation needed, only the files):

    ros2 run indoor_delivery_project correct_map \
        --base ~/ros2_jazzy_ws/maps/campus \
        --run  ~/ros2_jazzy_ws/maps/campus2 \
        --out  ~/ros2_jazzy_ws/maps/campus_corrected

The output folder is a normal map folder: delivery_navigator can use it with
-p map_dir:=... . It also holds slip_events.csv, corrected_trajectory.csv,
correction_report.txt and correction_preview.png.
"""
import argparse
import csv
import math
import os
import sys
from datetime import datetime

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


def load_map_dir(d):
    d = os.path.expanduser(d)
    with open(os.path.join(d, 'aruco_landmarks.yaml')) as f:
        doc = yaml.safe_load(f)
    grid = OccupancyGrid2D.load(os.path.join(d, doc.get('occupancy_map', 'map.yaml')))
    return doc, grid


def load_run(d):
    d = os.path.expanduser(d)
    path = os.path.join(d, 'scans.npz')
    if not os.path.isfile(path):
        sys.exit(f'{path} not found: map the run with the current aruco_slam_mapper '
                 '(save_scans:=true, the default) first.')
    z = np.load(path)
    obs = []
    op = os.path.join(d, 'observations.csv')
    if os.path.isfile(op):
        with open(op) as f:
            for row in csv.DictReader(f):
                obs.append({k: (v if k == 'name' else float(v)) for k, v in row.items()})
    return z, obs


def expanded_grid(base, margin_m):
    """Empty grid with the base resolution, base cells aligned, plus a margin."""
    m = int(round(margin_m / base.res))
    g = OccupancyGrid2D.__new__(OccupancyGrid2D)
    g.res = base.res
    g.origin = (base.origin[0] - m * base.res, base.origin[1] - m * base.res)
    h, w = base.shape
    g.logodds = np.zeros((h + 2 * m, w + 2 * m), np.float32)
    g.seen = np.zeros(g.logodds.shape, bool)
    return g, m


def to_world(pose, pts):
    c, s = math.cos(pose[2]), math.sin(pose[2])
    return np.stack([pose[0] + c * pts[:, 0] - s * pts[:, 1],
                     pose[1] + s * pts[:, 0] + c * pts[:, 1]], 1)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--base', required=True, help='folder of the first, trusted map')
    ap.add_argument('--run', required=True, help='folder of the later run (with scans.npz)')
    ap.add_argument('--out', required=True, help='folder for the corrected map')
    ap.add_argument('--initial-pose', type=float, nargs=3, default=None,
                    help='start pose of the run in the base map frame '
                         '(default: the run\'s own start pose)')
    ap.add_argument('--slip-yaw-deg', type=float, default=3.0,
                    help='heading disagreement over the window that counts as a slip')
    ap.add_argument('--slip-dist', type=float, default=0.20,
                    help='position disagreement (m) over the window that counts as a slip')
    ap.add_argument('--odom-yaw-noise', type=float, default=0.3,
                    help='expected heading slip as a fraction of each turn (fusion weight)')
    ap.add_argument('--window', type=int, default=10, help='scans per slip window')
    ap.add_argument('--accept-changes', action='store_true',
                    help='let the run overwrite base cells it clearly disagrees with')
    ap.add_argument('--margin', type=float, default=20.0,
                    help='metres added around the base map for new areas')
    a = ap.parse_args(argv)

    base_doc, base = load_map_dir(a.base)
    run_z, run_obs = load_run(a.run)
    with open(os.path.join(os.path.expanduser(a.run), 'aruco_landmarks.yaml')) as f:
        run_doc = yaml.safe_load(f)
    out = os.path.expanduser(a.out)
    os.makedirs(out, exist_ok=True)

    traj = run_z['traj']                    # t, slam x y yaw, odom x y yaw
    pts_all = run_z['points'].astype(np.float32)
    hit_all = run_z['hit']
    off = run_z['offsets']
    lo = run_z['laser_origin']
    n = len(traj)
    print(f'Run: {n} scans over {traj[-1, 0] - traj[0, 0]:.0f} s; base map '
          f'{base.shape[1] * base.res:.0f} x {base.shape[0] * base.res:.0f} m')

    fine = ScanMatcher()
    coarse = ScanMatcher(search_xy=0.8, step_xy=0.1, search_th=0.25, step_th=0.025,
                         min_quality=0.3)
    base_field = fine.field(base)
    new, m = expanded_grid(base, a.margin)
    base_known = np.zeros(new.shape, bool)
    base_lo = np.zeros(new.shape, np.float32)
    h, w = base.shape
    base_known[m:m + h, m:m + w] = np.abs(base.logodds) > 0.3
    base_lo[m:m + h, m:m + w] = base.logodds

    def scan(k):
        p = pts_all[off[k]:off[k + 1]]
        return p, hit_all[off[k]:off[k + 1]]

    # ---- initial alignment (coarse search around the given start pose)
    sp = run_doc.get('start_pose', {'x': 0, 'y': 0, 'yaw': 0})
    start = tuple(a.initial_pose) if a.initial_pose else (sp['x'], sp['y'], sp['yaw'])
    odom0 = tuple(traj[0, 4:7])
    p0, h0 = scan(0)
    pose = start
    for matcher in (coarse, fine):
        res = matcher.match(base_field, pose, p0[h0])
        if res is not None:
            pose = res[0]
    print(f'Start pose {tuple(round(v, 3) for v in start)} -> aligned '
          f'{tuple(round(v, 3) for v in pose)}')

    corrected = np.zeros((n, 3))
    source = []                              # 'base', 'run', 'odom' per scan
    prev_odom = odom0
    P = np.diag([0.05 ** 2, 0.05 ** 2, 0.02 ** 2])
    for k in range(n):
        odom = tuple(traj[k, 4:7])
        inc = compose(inverse(prev_odom), odom)
        prev_odom = odom
        pred = compose(pose, inc) if k else pose
        # odometry uncertainty: generous on heading, because that is where slips are
        d = math.hypot(inc[0], inc[1])
        c0_, s0_ = math.cos(pose[2]), math.sin(pose[2])
        J = np.array([[1, 0, -s0_ * inc[0] - c0_ * inc[1]],
                      [0, 1, c0_ * inc[0] - s0_ * inc[1]], [0, 0, 1]])
        sd, sth = 0.03 * d + 0.002, a.odom_yaw_noise * abs(inc[2]) + 0.01 * d + 0.001
        Q = np.diag([sd ** 2, sd ** 2, sth ** 2])
        P = J @ P @ J.T + Q
        p, hm = scan(k)
        hits = p[hm]
        used = 'odom'
        res = None
        if len(hits) >= 30:
            # how much of this scan lands on cells the base map knows?
            wpts = to_world(pred, hits)
            r, c = new.to_cell(wpts)
            ok = (r >= 0) & (r < new.shape[0]) & (c >= 0) & (c < new.shape[1])
            frac_base = float(base_known[r[ok], c[ok]].mean()) if ok.any() else 0.0
            if frac_base > 0.5:
                res = fine.match(base_field, pred, hits) or \
                    coarse.match(base_field, pred, hits)
                used = 'base' if res else used
            if res is None and (new.logodds > 0.6).sum() > 300:
                res = fine.match(fine.field(new, pred, half=20.0), pred, hits)
                used = 'run' if res else used
        if res is not None:
            # Kalman fusion: a corridor match only corrects across the corridor
            z, R = np.array(res[0]), res[1]
            nu = z - np.array(pred)
            nu[2] = wrap(nu[2])
            K = P @ np.linalg.inv(P + R)
            x = np.array(pred) + K @ nu
            pose = (float(x[0]), float(x[1]), wrap(float(x[2])))
            IK = np.eye(3) - K
            P = IK @ P @ IK.T + K @ R @ K.T
        else:
            pose = pred
        corrected[k] = pose
        source.append(used)
        # redraw this scan at the corrected pose
        c_, s_ = math.cos(pose[2]), math.sin(pose[2])
        origin = (pose[0] + c_ * lo[0] - s_ * lo[1], pose[1] + s_ * lo[0] + c_ * lo[1])
        new.update_scan(origin, to_world(pose, p), hm)
        new.clear_disk(pose[:2], 0.3)
        if k % 500 == 0:
            print(f'  scan {k}/{n}  pose ({pose[0]:.2f}, {pose[1]:.2f}, '
                  f'{math.degrees(pose[2]):.1f} deg)  matched on {used}')

    # ---- slip detection: wheels vs corrected motion over a sliding window
    W = max(2, a.window)
    events, cur = [], None
    for k in range(W, n):
        o_inc = compose(inverse(traj[k - W, 4:7]), traj[k, 4:7])
        c_inc = compose(inverse(corrected[k - W]), corrected[k])
        dyaw = math.degrees(wrap(c_inc[2] - o_inc[2]))
        dxy = math.hypot(c_inc[0] - o_inc[0], c_inc[1] - o_inc[1])
        slip = abs(dyaw) > a.slip_yaw_deg or dxy > a.slip_dist
        if slip:
            if cur is None:
                cur = dict(k0=k - W, k1=k, yaw=dyaw, dist=dxy)
            else:
                cur['k1'] = k
                if abs(dyaw) > abs(cur['yaw']):
                    cur['yaw'] = dyaw
                cur['dist'] = max(cur['dist'], dxy)
        elif cur is not None:
            events.append(cur)
            cur = None
    if cur is not None:
        events.append(cur)
    for e in events:
        # total disagreement over the whole event
        o_inc = compose(inverse(traj[e['k0'], 4:7]), traj[e['k1'], 4:7])
        c_inc = compose(inverse(corrected[e['k0']]), corrected[e['k1']])
        e['total_yaw'] = math.degrees(wrap(c_inc[2] - o_inc[2]))
        e['total_dist'] = math.hypot(c_inc[0] - o_inc[0], c_inc[1] - o_inc[1])

    # ---- merge: base has priority
    run_known = np.abs(new.logodds) > 0.3
    merged = np.where(base_known, base_lo, new.logodds)
    disagree = base_known & run_known & (np.sign(base_lo) != np.sign(new.logodds)) & \
        (np.abs(new.logodds) > 2.0)
    added = run_known & ~base_known
    if a.accept_changes:
        merged[disagree] = new.logodds[disagree]
    final = OccupancyGrid2D.__new__(OccupancyGrid2D)
    final.res, final.origin = new.res, new.origin
    final.logodds = merged.astype(np.float32)
    final.seen = np.zeros(final.shape, bool)
    final.save(out, 'map')
    new.save(out, 'run_corrected')           # the run alone, redrawn at corrected poses

    # ---- markers
    t_scan = traj[:, 0]
    corr_tf = [compose(tuple(corrected[k]), inverse(tuple(traj[k, 4:7]))) for k in range(n)]
    est = {}
    for o in run_obs:
        k = int(np.clip(np.searchsorted(t_scan, o['t']), 0, n - 1))
        pose_o = compose(corr_tf[k], (o['odom_x'], o['odom_y'], math.radians(o['odom_yaw_deg'])))
        b = math.radians(o['bearing_deg'])
        r = o['range_2d_m']
        x = pose_o[0] + r * math.cos(pose_o[2] + b)
        y = pose_o[1] + r * math.sin(pose_o[2] + b)
        fy = pose_o[2] + math.radians(o['marker_facing_deg'])
        wgt = 1.0 / max(r, 1.0) ** 2
        e = est.setdefault(int(o['marker_id']), [0, 0, 0, 0, 0, 0, o['name']])
        e[0] += wgt * x
        e[1] += wgt * y
        e[2] += wgt * math.cos(fy)
        e[3] += wgt * math.sin(fy)
        e[4] += wgt
        e[5] += 1
    base_markers = {int(mk['id']): mk for mk in base_doc.get('markers', [])}
    run_markers = {int(mk['id']): mk for mk in run_doc.get('markers', [])}
    markers = [dict(mk) for mk in base_doc.get('markers', [])]
    points = dict(base_doc.get('delivery_points') or {})
    standoff = float(base_doc.get('delivery_standoff', 2.3))
    marker_lines = []
    for mid, e in sorted(est.items()):
        x, y = float(e[0] / e[4]), float(e[1] / e[4])
        yaw = float(math.atan2(e[3], e[2]))
        if mid in base_markers:
            bm = base_markers[mid]
            marker_lines.append(f'  id {mid:>3}: run vs base {math.hypot(x - bm["x"], y - bm["y"]):.2f} m '
                                f'(kept base position)')
            continue
        info = run_markers.get(mid, {})
        entry = {'id': mid, 'name': info.get('name', e[6] or f'marker_{mid}'),
                 'kind': info.get('kind', 'unknown'), 'room': info.get('room'),
                 'size': info.get('size'), 'x': round(x, 3), 'y': round(y, 3),
                 'yaw': round(yaw, 4), 'sigma_xy': None, 'observations': int(e[5]),
                 'source': 'corrected run'}
        if info.get('standoff') is not None:
            entry['standoff'] = float(info['standoff'])
        markers.append(entry)
        marker_lines.append(f'  id {mid:>3}: NEW, added at ({x:.2f}, {y:.2f})')
        if entry['kind'] == 'delivery':
            so = entry.get('standoff', standoff)
            points[entry['name']] = {'x': round(x + so * math.cos(yaw), 3),
                                     'y': round(y + so * math.sin(yaw), 3),
                                     'yaw': round(wrap(yaw + math.pi), 4), 'marker_id': mid}
    doc = dict(base_doc)
    doc.update({'created': datetime.now().isoformat(timespec='seconds'),
                'occupancy_map': 'map.yaml', 'markers': markers, 'delivery_points': points,
                'corrected_from': {'base': os.path.expanduser(a.base),
                                   'run': os.path.expanduser(a.run)}})
    with open(os.path.join(out, 'aruco_landmarks.yaml'), 'w') as f:
        f.write('# Corrected map: base map has priority, later run added where new.\n')
        yaml.safe_dump(doc, f, sort_keys=False)

    # ---- tables
    with open(os.path.join(out, 'corrected_trajectory.csv'), 'w', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(['t', 'x', 'y', 'yaw', 'odom_x', 'odom_y', 'odom_yaw',
                     'run_slam_x', 'run_slam_y', 'run_slam_yaw', 'matched_on'])
        for k in range(n):
            wr.writerow([f'{traj[k, 0]:.3f}'] + [f'{v:.4f}' for v in corrected[k]] +
                        [f'{v:.4f}' for v in traj[k, 4:7]] +
                        [f'{v:.4f}' for v in traj[k, 1:4]] + [source[k]])
    with open(os.path.join(out, 'slip_events.csv'), 'w', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(['t_start', 't_end', 'x', 'y', 'heading_error_deg',
                     'position_error_m', 'max_window_heading_deg', 'max_window_dist_m'])
        for e in events:
            x, y = corrected[e['k1'], :2]
            wr.writerow([f'{traj[e["k0"], 0]:.2f}', f'{traj[e["k1"], 0]:.2f}', f'{x:.2f}',
                         f'{y:.2f}', f'{e["total_yaw"]:.2f}', f'{e["total_dist"]:.3f}',
                         f'{e["yaw"]:.2f}', f'{e["dist"]:.3f}'])

    counts = {s: source.count(s) for s in ('base', 'run', 'odom')}
    drift = [math.hypot(*(corrected[k, :2] - traj[k, 1:3])) for k in range(n)]
    report = [
        f'Corrected map written to {out}',
        f'Scans: {n} (aligned on base map {counts["base"]}, on new area {counts["run"]}, '
        f'odometry only {counts["odom"]})',
        f'Slip events: {len(events)} (heading > {a.slip_yaw_deg} deg or position > '
        f'{a.slip_dist} m over {W} scans), total heading slip '
        f'{sum(abs(e["total_yaw"]) for e in events):.1f} deg',
        f'Run\'s own SLAM pose vs corrected: mean {np.mean(drift):.2f} m, max {np.max(drift):.2f} m',
        f'Cells: base {int(base_known.sum())}, added from run {int(added.sum())}, '
        f'disagreeing {int(disagree.sum())} '
        f'({"applied" if a.accept_changes else "kept base; use --accept-changes to apply"})',
        'Markers:'] + marker_lines
    if events:
        report.append('Largest slips:')
    for e in sorted(events, key=lambda e: -abs(e['total_yaw']) - 10 * e['total_dist'])[:15]:
        report.append(f'  slip t={traj[e["k0"], 0]:.1f}-{traj[e["k1"], 0]:.1f} s at '
                      f'({corrected[e["k1"], 0]:.1f}, {corrected[e["k1"], 1]:.1f}): '
                      f'heading {e["total_yaw"]:+.1f} deg, position {e["total_dist"]:.2f} m')
    if len(events) > 15:
        report.append(f'  ... {len(events) - 15} more in slip_events.csv')
    text = '\n'.join(report)
    with open(os.path.join(out, 'correction_report.txt'), 'w') as f:
        f.write(text + '\n')
    print(text)
    preview(out, final, base_known, added, disagree, traj, corrected, events, markers, points)


def preview(out, grid, base_known, added, disagree, traj, corrected, events, markers, points):
    r0, r1, c0, c1 = grid.known_bbox()
    t = grid.ternary()[r0:r1, c0:c1]
    img = np.full(t.shape + (3,), 160, np.uint8)
    img[t == 0] = (255, 255, 255)
    img[t == 100] = (0, 0, 0)
    a = added[r0:r1, c0:c1]
    img[a & (t == 0)] = (255, 225, 190)             # new free area: light blue
    img[a & (t == 100)] = (200, 90, 0)              # new walls: blue
    img[disagree[r0:r1, c0:c1]] = (0, 0, 230)       # disagreements: red
    scale = max(1, int(round(1200 / max(t.shape))))
    img = cv2.resize(img, (t.shape[1] * scale, t.shape[0] * scale),
                     interpolation=cv2.INTER_NEAREST)

    def px(x, y):
        return (int(((x - grid.origin[0]) / grid.res - c0) * scale),
                int(((y - grid.origin[1]) / grid.res - r0) * scale))

    for i in range(1, len(traj)):
        cv2.line(img, px(*traj[i - 1, 1:3]), px(*traj[i, 1:3]), (60, 60, 255), 1)
        cv2.line(img, px(*corrected[i - 1, :2]), px(*corrected[i, :2]), (0, 170, 0), 1)
    for e in events:
        cv2.circle(img, px(*corrected[e['k1'], :2]), 7, (0, 140, 255), 2)
    for mk in markers:
        cv2.circle(img, px(mk['x'], mk['y']), 5, (0, 0, 255), -1)
    for dp in points.values():
        cv2.drawMarker(img, px(dp['x'], dp['y']), (0, 160, 255), cv2.MARKER_STAR, 12, 2)
    img = np.ascontiguousarray(np.flipud(img))
    img = cv2.copyMakeBorder(img, 84, 0, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    for i, (txt, col) in enumerate([('green: corrected path', (0, 170, 0)),
                                    ("red line: run's own SLAM path", (60, 60, 255)),
                                    ('orange circles: slips', (0, 140, 255)),
                                    ('blue: added from run, red cells: disagree', (200, 90, 0))]):
        cv2.putText(img, txt, (10, 20 + 18 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1)
    cv2.imwrite(os.path.join(out, 'correction_preview.png'), img)


if __name__ == '__main__':
    main()
