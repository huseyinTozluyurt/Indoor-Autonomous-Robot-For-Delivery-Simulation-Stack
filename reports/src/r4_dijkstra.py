import json, os
from common import fig, fig2, table, page, reset
D = os.path.join(os.path.dirname(__file__), 'data')


def build():
    reset()
    r = json.load(open(f'{D}/dij.json'))
    sc = r['scaling']
    save = (1 - r['hk'] / r['given']) * 100
    b = []
    b.append(f"""
<h2>1. Two shortest-path problems</h2>
<p>A delivery mission has two layers. <b>Where to drive between two points</b> is a shortest-path problem on the map
grid, solved with <b>Dijkstra's algorithm</b>. <b>In which order to visit several delivery points</b> is a travelling-salesman
problem on top of it, solved exactly with <b>Held-Karp dynamic programming</b> on the Dijkstra distance matrix. Both run in
<code>delivery_navigator.py</code> and behind the web app's <code>/robot/plan</code> and <code>/robot/mission</code>.</p>
<div class="kpi"><div><b>{r['given']:.0f} → {r['hk']:.0f}</b><span>tour cost: arrival order → optimal (6 stops)</span></div><div><b>−{save:.0f} %</b><span>driving saved</span></div>
<div><b>{r['tree_s']*1000:.0f} ms</b><span>one full Dijkstra tree, {r['grid'][0]}×{r['grid'][1]} grid</span></div><div><b>{r['thk']*1000:.0f} ms</b><span>exact order for 6 stops</span></div></div>
<h2>2. From SLAM map to planning graph</h2>
<ol>
<li>The saved 0.1 m occupancy grid is down-sampled to <b>0.2 m cells</b> (here {r['grid'][0]}×{r['grid'][1]} cells for
campus_full_map7).</li>
<li>A distance transform on the <i>full-resolution</i> map gives every cell its <b>clearance</b> – distance to the nearest
wall – taking the worst point inside the cell, so thin or doubled walls do not eat corridor cells.</li>
<li>Cells with clearance below the <b>robot radius (0.45 m)</b>, and unknown cells, are blocked.</li>
<li>Free cells get a cost 1 + w·t² with w = 4 and t rising from 0 at 1.0 m clearance to 1 at the robot radius. The cheapest
path therefore keeps to the middle of corridors and doors instead of grazing walls.</li>
<li>Each cell is connected to its 8 neighbours; an edge costs step length × mean cost of the two cells (1 or √2 times
0.2 m).</li>
</ol>""")
    b.append(fig('dij_costmap.png', 'campus_full_map7. Left: per-cell planning cost (bright = close to a wall, dark grey = blocked). Right: one full Dijkstra run from home gives the cost-to-reach of every cell – this single tree answers "how far to any delivery point" at once.'))
    b.append("""
<h2>3. Dijkstra's algorithm as implemented</h2>
<pre>g[start] = 0, all other g = ∞; push (0, start) on a binary heap
while heap not empty:
    pop cell i with the smallest g; skip if already closed; close it
    for each of the 8 neighbours j (not blocked, not closed):
        ng = g[i] + step(i,j) · ½(cost[i] + cost[j])
        if ng &lt; g[j]: g[j] = ng; parent[j] = i; push (ng, j)
path = follow parent[] back from the goal</pre>
<p><code>PlanningGrid._search</code> uses Python's <code>heapq</code> with lazy deletion, so the run time is
O(E log V) on the grid. With a goal and the octile heuristic the same function becomes A*; the navigator uses the pure
Dijkstra form because one run from a point returns the whole tree (<code>dijkstra_tree</code>), from which the cost and path to
<i>every</i> stop are read without searching again.</p>""")
    b.append(table(['Same query: home → b_delivery_point_3', 'Time', 'Path length'], [
        ['Dijkstra (no heuristic, stops at goal)', f'{r["single"]["dij_s"]*1000:.0f} ms', f'{r["single"]["dij_len"]:.1f} m'],
        ['A* (octile heuristic)', f'{r["single"]["astar_s"]*1000:.0f} ms', f'{r["single"]["astar_len"]:.1f} m'],
    ]))
    b.append("""<p>Both return the identical path; A* explores fewer cells for one goal, but for tours the full Dijkstra tree is
cheaper than one A* per pair of points.</p>
<h3>Robustness rules around the planner</h3>
<ul>
<li>Replan from the current pose every 15 s and after every pose correction.</li>
<li>A goal too close to a wall or table is moved to the nearest reachable cell with room (logged as "stopped x m before").</li>
<li>Lidar obstacles are added with their own clearance for 30 s; if no path is found the planner relaxes step by step
(drop remembered obstacles → 0.1 m less margin → allow unknown cells).</li>
<li>The path is followed with pure pursuit; an obstacle closer than the stop distance halts the robot and, if it stays
more than 2 s, is put into the map and planned around.</li>
</ul>
<h2>4. Visiting order: Held-Karp</h2>
<p>For a mission with start A, stops x₁…x<sub>k</sub> and end B, one Dijkstra tree from A and from every stop fills the
(k+2)×(k+2) matrix of real driving costs. Held-Karp then finds the cheapest open path A → all stops → B exactly:</p>
<pre>best[{x_i}, i] = D[A, x_i]
best[S ∪ {j}, j] = min over i in S of best[S, i] + D[x_i, x_j]
answer = min over i of best[all, i] + D[x_i, B]   (back-pointers give the order)</pre>
<p>This is O(k²·2<sup>k</sup>) instead of O(k!) for trying every order. The navigator uses it up to 12 stops and switches
to nearest-neighbour + 2-opt above that.</p>""")
    stops = r['stops']
    b.append(f"""
<h2>5. Experiment on the final map</h2>
<p>Six delivery points of campus_full_map7, start and end at home, listed in "order of arrival":
{', '.join('<code>'+s+'</code>' for s in stops)}. The planner and ordering code were imported unchanged from the
package and run offline on the saved map (script <code>reports/src/scripts/dij.py</code>).</p>""")
    b.append(table(['Method', 'Tour cost', 'vs. optimum'], [
        ['Order of arrival (no optimisation)', f'{r["given"]:.1f}', f'+{(r["given"]/r["hk"]-1)*100:.0f} %'],
        ['Nearest neighbour', f'{r["nn"]:.1f}', f'+{(r["nn"]/r["hk"]-1)*100:.1f} %'],
        ['Nearest neighbour + 2-opt', f'{r["twoopt"]:.1f}', f'+{(r["twoopt"]/r["hk"]-1)*100:.1f} %'],
        ['Held-Karp (used)', f'<b>{r["hk"]:.1f}</b>', 'optimal'],
        ['Brute force over all 720 orders (check)', f'{r["brute"]:.1f}', 'same as Held-Karp'],
    ]))
    b.append(f"<p>Optimal order: home → {' → '.join(r['hk_order'])} → home. Costs are in cost-weighted metres, i.e. path length "
             "inflated slightly near walls, so they are a little above the geometric length.</p>")
    b.append(fig('dij_tour_compare.png', 'The same six stops driven in arrival order (left) and in the Held-Karp order (right), each leg drawn from the Dijkstra trees on the SLAM map.'))
    legs = ''.join(f'<tr><td><code>{s}</code></td><td>{d:.1f}</td><td>{e:.1f}</td><td>{d/e:.2f}</td></tr>' for s, d, e in r['legs_home'])
    b.append(f"""<h3>Why a map-based distance is needed</h3>
<table><tr><th>From home to</th><th>Dijkstra cost</th><th>Straight line (m)</th><th>Ratio</th></tr>{legs}</table>
<p>Walls make the real distance 5–25 % longer than the straight line, and not by the same factor for every point, so
ordering by straight-line distance can choose the wrong tour.</p>""")
    b.append(fig('dij_scaling.png', f'Run time of the exact ordering. Held-Karp needs {sc[-1][1]*1000:.0f} ms for 12 stops; brute force already takes {sc[7][2]:.1f} s for 9 stops and would take hours for 12.', 'half'))
    b.append(fig2('delivery_gui_mission.png', 'Delivery GUI: a multi-stop mission typed as "3 4 6 7 5"; the GUI shows the shortest order, each leg and the total compared with the typed order.',
                  'web_operator_route.png', 'Web operator page: the same planner behind <code>/robot/plan</code> shows the shortest tour and its saving before the robot starts.'))
    b.append("""
<h2>6. Results in the simulation</h2>
<ul>
<li>campus_area offline test: stops right 1, left 4, right 3, left 1, end right 4 – optimal tour 173.8 m against 377.5 m in
the given order; the robot drove 173 m and stopped 0.11–0.15 m from every pad.</li>
<li>The navigator went around a box placed in the corridor (stop → obstacle added → replan).</li>
<li>From the web app the operator's preview and the driven tour use the same code, so the distance shown before loading the
robot is what the robot drives.</li>
</ul>
<div class="box"><b>Summary.</b> Dijkstra on a clearance-weighted grid gives safe, centred paths and – run once per stop – all
pairwise driving distances. Held-Karp turns those into the provably shortest delivery order in milliseconds for realistic
loads (≤ 12 stops), saving about 40 % of the driving in the six-stop example.</div>""")
    return page('Dijkstra Shortest Path and Tour Planning', 4, 'Clearance-weighted grid Dijkstra, Held-Karp ordering of multi-stop deliveries, and measured results on the SLAM map', ''.join(b))
