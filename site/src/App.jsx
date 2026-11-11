import { useEffect, useState } from 'react'
import { LightboxProvider, Figure } from './components/Lightbox.jsx'
import Architecture from './components/Architecture.jsx'
import AccuracyChart from './components/AccuracyChart.jsx'
import MapEvolution from './components/MapEvolution.jsx'
import TourCompare from './components/TourCompare.jsx'
import SimVideo from './components/SimVideo.jsx'
import { fig, pdf, heroStats, reports, markerKinds, tour, robotApi, webPages, gazebo, gazeboShots } from './data.js'

const sections = [
  ['overview', 'Overview'],
  ['simulation', 'Simulation'],
  ['video', 'Video'],
  ['aruco', 'ArUco'],
  ['slam', 'SLAM'],
  ['maps', 'Map evolution'],
  ['planning', 'Planning'],
  ['webapp', 'Web app'],
  ['bridge', 'Sim ↔ web'],
  ['real', 'Real robot'],
  ['reports', 'Reports'],
]

function Nav() {
  const [active, setActive] = useState('')
  const [open, setOpen] = useState(false)
  useEffect(() => {
    const obs = new IntersectionObserver(
      (es) => es.forEach((e) => e.isIntersecting && setActive(e.target.id)),
      { rootMargin: '-45% 0px -50% 0px' },
    )
    sections.forEach(([id]) => { const el = document.getElementById(id); if (el) obs.observe(el) })
    return () => obs.disconnect()
  }, [])
  return (
    <header className="nav">
      <div className="nav-in">
        <a href="#top" className="brand" onClick={() => setOpen(false)}>
          <span className="brand-mark" aria-hidden="true" />
          Indoor Delivery Robot
        </a>
        <button className="nav-toggle" aria-expanded={open} aria-controls="nav-links" onClick={() => setOpen(!open)}>Menu</button>
        <nav id="nav-links" className={open ? 'open' : ''} aria-label="Sections">
          {sections.map(([id, label]) => (
            <a key={id} href={`#${id}`} className={active === id ? 'on' : ''} onClick={() => setOpen(false)}>{label}</a>
          ))}
        </nav>
      </div>
    </header>
  )
}

function Section({ id, kicker, title, lead, children }) {
  return (
    <section id={id} className="section">
      <div className="wrap">
        <p className="kicker">{kicker}</p>
        <h2>{title}</h2>
        {lead && <p className="lead">{lead}</p>}
        {children}
      </div>
    </section>
  )
}

const Stat = ({ v, l }) => (
  <div className="stat"><span className="stat-v">{v}</span><span className="stat-l">{l}</span></div>
)

export default function App() {
  return (
    <LightboxProvider>
      <Nav />
      <main id="top">
        <section className="hero">
          <div className="wrap hero-grid">
            <div>
              <p className="kicker">ROS 2 Jazzy · Gazebo Harmonic · React · Spring Boot</p>
              <h1>An indoor robot that maps the building, plans the shortest tour, and delivers your order.</h1>
              <p className="lead">
                Customers order from a web shop and click where they are on the campus map. An operator loads the robot.
                The robot localises on ArUco markers, drives the provably shortest multi-stop tour, and checks it sees the
                right marker before it reports <em>Delivered</em>. Everything runs first in simulation, then moves to the real
                robot without changing the web app.
              </p>
              <div className="cta">
                <a className="btn primary" href="#overview">How it works</a>
                <a className="btn" href="#video">Watch the demo</a>
                <a className="btn" href="#reports">Read the six reports</a>
              </div>
            </div>
            <Figure src={fig('web_operator_route.png')} caption="Operator page: the Dijkstra shortest tour on the robot’s own SLAM map." className="hero-fig" />
          </div>
          <div className="wrap stats">
            {heroStats.map((s) => <Stat key={s.label} v={s.value} l={s.label} />)}
          </div>
        </section>

        <Section id="overview" kicker="01 · Overview" title="One system, five parts"
          lead="The backend never talks to ROS directly. It talks to “the robot” over HTTP on port 5000. In simulation that is web_bridge; on the real robot it is the Raspberry Pi. Both serve the same API.">
          <Architecture />
          <ol className="flow">
            <li><b>Order</b><span>A user fills a cart and clicks a delivery point on the SLAM map.</span></li>
            <li><b>Load</b><span>The operator ticks the orders put in the robot and previews the shortest tour.</span></li>
            <li><b>Plan</b><span>Dijkstra gives all leg lengths; Held-Karp picks the best visiting order.</span></li>
            <li><b>Drive</b><span>EKF localisation on ArUco markers and lidar, pure-pursuit driving, obstacle replanning.</span></li>
            <li><b>Confirm</b><span>At each stop the robot turns to the marker, checks its ID, and reports back.</span></li>
          </ol>
        </Section>

        <Section id="simulation" kicker="02 · Simulation" title="A two-building campus in Gazebo"
          lead="The robot is a Robotnik RB1 base with a 2D lidar, an IMU, an RGB-D camera and a mast camera for markers. Two worlds were built: campus_area (two rooms and a corridor) and two_buildings, a 70 × 45 m campus with a ring corridor, tables and 32 ArUco markers.">
          <Figure src={gazebo(gazeboShots[0].img)} caption={`${gazeboShots[0].title}. ${gazeboShots[0].text}`} className="wide first" />
          <div className="gallery g3">
            {gazeboShots.slice(1).map((p) => (
              <div key={p.img} className="shot">
                <Figure src={gazebo(p.img)} caption={p.title} />
                <p>{p.text}</p>
              </div>
            ))}
          </div>
          <div className="grid2 top">
            <Figure src={fig('two_buildings_top_view.png')} caption="The two_buildings Gazebo world from above." />
            <Figure src={fig('robot_vision_overlay.png')} caption="Mast camera in Gazebo: marker ID, name, range and bearing drawn live." />
          </div>
          <div className="cards3">
            <div className="card"><h3>Sim time everywhere</h3><p>All waits and time-outs run on <code>/clock</code>, so mapping at 3–10× real time behaves the same as at 1×. A 10× run reached 9.9× with the same map quality.</p></div>
            <div className="card"><h3>Map = world coordinates</h3><p>The mapper starts at the Gazebo spawn pose, so every saved marker can be scored against the world file. That is what makes the map comparison in Report 6 objective.</p></div>
            <div className="card"><h3>One command</h3><p><code>run_web_sim.sh</code> starts Gazebo, web_bridge, the Spring Boot backend and the Vite frontend together.</p></div>
          </div>
        </Section>

        <Section id="video" kicker="Video" title="See it run"
          lead="A 68-second walk through the two_buildings world in Gazebo Sim: both buildings, the corridors, the delivery tables and the ArUco markers the robot maps and navigates by.">
          <SimVideo />
        </Section>

        <Section id="aruco" kicker="03 · Object detection" title="ArUco markers tell the robot where it is, and where it is not"
          lead="Each DICT_4X4_50 marker has a known ID, size and purpose. One detection gives which landmark is in view, its range and bearing, and which way it faces. Because the ID is decoded from the image, there are no wrong matches.">
          <Figure src={fig('aruco_markers.png')} caption="Examples of the DICT_4X4_50 markers used in the world." className="wide" />
          <div className="grid2 top">
            <div>
              <h3>Detection pipeline</h3>
              <ol className="steps">
                <li><b>Detect</b> with <code>cv2.aruco</code> on the grey image: four corners and an ID.</li>
                <li><b>Filter</b> markers smaller than 12 px and IDs not in the marker config.</li>
                <li><b>Pose</b> with <code>solvePnP</code> (IPPE_SQUARE) and the real marker size.</li>
                <li><b>Robot frame</b>: range, bearing and facing in <code>base_link</code>; flipped or too-far poses are rejected.</li>
                <li><b>Noise model</b>: σ grows with range/pixels and with the turn rate, so far, small markers count less.</li>
              </ol>
              <table className="tbl">
                <thead><tr><th>Kind</th><th>Size</th><th>Count</th><th>Where</th></tr></thead>
                <tbody>{markerKinds.map((m) => <tr key={m.kind}><td>{m.kind}</td><td>{m.size}</td><td>{m.count}</td><td>{m.where}</td></tr>)}</tbody>
              </table>
            </div>
            <AccuracyChart />
          </div>
          <div className="stats inline">
            <Stat v="1523" l="detections logged while mapping campus_full_map7" />
            <Stat v="25.0 m" l="longest detection (1.0 m room marker)" />
            <Stat v="≈ 5–8 cm" l="range error at 3 m, 0.30 m marker" />
          </div>
        </Section>

        <Section id="slam" kicker="04 · SLAM and localisation" title="EKF-SLAM on markers, lidar for the walls"
          lead="Wheel odometry gives distance, the IMU gyro gives heading (wheels slip in turns), ArUco detections correct the pose, and the 2D lidar draws a 0.1 m occupancy grid. The robot explores on its own until every wall has been seen from close range.">
          <div className="grid2 top">
            <div className="prose">
              <h3>State and update</h3>
              <p>The state is the robot pose plus the x, y of every marker seen so far. Innovations are gated (χ² = 13.8). Bearings are down-weighted while turning and ignored above 0.5 rad/s, because camera latency turns into heading error.</p>
              <h3>Exploration</h3>
              <p>After a 360° start turn the robot drives to the cheapest goal: a frontier next to unknown space, or a viewpoint 2–3.5 m in front of a wall the camera has not yet seen. That second goal type makes sure every marker is seen from near.</p>
              <h3>Repairing bad runs</h3>
              <p>Raw scans are kept, so a run spoiled by wheel slip can be rebuilt as a pose graph (keyframes every 0.3 m / 10°, odometry, marker and lidar loop edges) and solved with robust Gauss-Newton. In a 15 % slip test marker errors went from up to 72.7 m to within 0.07 m.</p>
            </div>
            <div className="stack">
              <div className="stats inline two">
                <Stat v="17.1 → 1.7 m" l="end drift: wheels only → wheels + gyro" />
                <Stat v="0.39 m" l="mean marker error after rigid fit" />
              </div>
              <Figure src={fig('map_correction_slip15.png')} caption="Pose-graph correction of a run with 15 % wheel slip: green corrected path, red the run’s own path, orange the detected slip events." />
            </div>
          </div>
          <Figure src={fig('slam_traj_markers.png')} caption="campus_full_map7. Left: the same run from three pose sources. Right: SLAM marker estimates (red) against the true positions (green)." className="wide" />
        </Section>

        <Section id="maps" kicker="05 · Map evolution" title="Thirteen runs from a shattered map to campus_full_map7"
          lead="Between 4 and 8 November the mapper was run 13 times. Every map was scored against the world file. Heading turned out to be the dominant error, not marker detection. Pick a run to see what changed.">
          <div className="stats inline">
            <Stat v="53 → 1.4 m" l="mean absolute marker error, first → final" />
            <Stat v="100° → 2.6°" l="global map rotation" />
            <Stat v="1007 → 242 m" l="path driven to finish the map" />
          </div>
          <MapEvolution />
        </Section>

        <Section id="planning" kicker="06 · Path planning" title="Dijkstra for the path, Held-Karp for the order"
          lead="Where to drive between two points is a shortest-path problem on the map grid. In which order to visit several points is a travelling-salesman problem on top of it. Both run behind /robot/plan, so the tour the operator previews is the tour the robot drives.">
          <div className="grid2 top">
            <div className="prose">
              <h3>From SLAM map to graph</h3>
              <p>The 0.1 m grid is down-sampled to 0.2 m cells. Cells closer to a wall than the robot radius (0.45 m) are blocked, and free cells get a cost that rises near walls, so paths keep to the middle of corridors and doors. Each cell links to its 8 neighbours.</p>
              <h3>One Dijkstra tree per stop</h3>
              <p>One run from a point returns the cost to every cell, so a tour of k stops needs k + 1 runs to fill the whole distance matrix. Held-Karp then finds the exact best order in O(k²·2ᵏ): 8 ms for 6 stops, 161 ms for 12. Above 12 stops it switches to nearest neighbour + 2-opt.</p>
            </div>
            <Figure src={fig('dij_costmap.png')} caption="Left: per-cell planning cost (bright = close to a wall). Right: one Dijkstra tree from home." />
          </div>
          <h3 className="mt">Six stops, two orders</h3>
          <TourCompare />
          <Figure src={fig('dij_tour_compare.png')} caption="The same six stops in arrival order (left) and in the Held-Karp order (right), drawn from the Dijkstra trees on the SLAM map." className="wide" />
          <div className="grid2 top">
            <table className="tbl">
              <caption>Tour cost by method</caption>
              <thead><tr><th>Method</th><th>Cost</th><th>vs. optimum</th></tr></thead>
              <tbody>{tour.methods.map((m) => <tr key={m.name}><td>{m.name}</td><td className="num">{m.cost.toFixed(1)}</td><td>{m.delta}</td></tr>)}</tbody>
            </table>
            <table className="tbl">
              <caption>Why straight lines are not enough</caption>
              <thead><tr><th>home →</th><th>Dijkstra</th><th>Straight</th><th>Ratio</th></tr></thead>
              <tbody>{tour.detour.map((d) => <tr key={d.to}><td><code>{d.to}</code></td><td className="num">{d.dij}</td><td className="num">{d.line}</td><td className="num">{(d.dij / d.line).toFixed(2)}</td></tr>)}</tbody>
            </table>
          </div>
        </Section>

        <Section id="webapp" kicker="07 · Web application" title="DeliveryBot: shop, operator and admin"
          lead="React 19 + Vite on the front, Spring Boot 3.5 + MySQL behind it. Three roles land on three pages, and every page polls the backend every 2 s, so a status change shows up for everyone without reloading.">
          <div className="gallery">
            {webPages.map((p) => (
              <div key={p.img} className="shot">
                <Figure src={p.src ? import.meta.env.BASE_URL + p.src : fig(p.img)} caption={p.title} />
                <p>{p.text}</p>
              </div>
            ))}
          </div>
          <h3 className="mt">Order life cycle</h3>
          <div className="life">
            <span className="st">Preparing</span><span className="arr">operator loads robot</span>
            <span className="st">Delivering</span><span className="arr">marker confirmed</span>
            <span className="st ok">Delivered</span>
          </div>
          <p className="muted small">An unreachable point becomes <b>Failed</b>, an emergency stop makes orders <b>Cancelled</b>; both go back to the operator’s list.</p>
          <details className="evolution">
            <summary>Where it started: the first prototype</summary>
            <p>The first version was a login/register app where the user picked a delivery area and a table number from a floor plan, and the admin sent the order to a hard-coded robot IP. Orders lived in browser storage.</p>
            <div className="grid2">
              <Figure src={fig('early_web_3.jpeg')} caption="First version: register." />
              <Figure src={fig('early_web_7.jpeg')} caption="First version: table picker." />
            </div>
          </details>
        </Section>

        <Section id="bridge" kicker="08 · Web app ↔ Gazebo" title="web_bridge makes the simulated robot look real"
          lead="The backend was first written for the physical robot’s REST API. web_bridge serves that same API from ROS 2: the delivery navigator wrapped in an HTTP server, a mission worker, a status reporter and an MJPEG camera stream.">
          <div className="grid2 top">
            <table className="tbl api">
              <caption>Robot REST API on :5000</caption>
              <tbody>{robotApi.map(([m, p, d]) => <tr key={p}><td><span className={`verb ${m}`}>{m}</span></td><td><code>{p}</code><br /><span className="muted small">{d}</span></td></tr>)}</tbody>
            </table>
            <div className="stack">
              <Figure src={import.meta.env.BASE_URL + 'screens/camera_stream.jpg'} caption="Admin → Camera Streaming: the live MJPEG stream from the robot’s mast camera in Gazebo (here facing a building wall), the robot pose under it, and the manual-control pad." />
              <div className="card">
                <h3>Manual control</h3>
                <p><b>Take control</b> pauses the running leg and keeps unfinished orders queued. <b>Release</b> replans from the current pose. <b>Emergency stop</b> stops at once and cancels the mission.</p>
              </div>
            </div>
          </div>
        </Section>

        <Section id="real" kicker="09 · Toward hardware" title="From simulation to the real robot"
          lead="Because the contract is the HTTP API, moving to hardware means serving the same endpoints from the Raspberry Pi 4 and entering its IP in Robot Settings. The cleanest route is to run web_bridge itself on the robot, keeping the map, planner and status reporting tested in Gazebo.">
          <table className="tbl">
            <thead><tr><th /><th>Simulation</th><th>Real robot</th></tr></thead>
            <tbody>
              <tr><td>Robot API on :5000</td><td>web_bridge (ROS 2 node)</td><td>Raspberry Pi 4 service</td></tr>
              <tr><td>Sensors</td><td>Gazebo lidar, IMU, cameras</td><td>Physical sensors</td></tr>
              <tr><td>Selected in</td><td>Robot Settings → Use Gazebo Simulation</td><td>Robot Settings → robot IP</td></tr>
            </tbody>
          </table>
          <div className="cards3">
            <div className="card"><h3>Markers</h3><p>Print them, measure the black square and put the real size in the marker YAML. Range scales directly with it.</p></div>
            <div className="card"><h3>Calibration</h3><p>Calibrate the camera, wheel radius and track. Keep the gyro on; heading was the dominant error in every simulated run.</p></div>
            <div className="card"><h3>Before a shared network</h3><p>Add authentication on the robot API and the status callback, role checks per endpoint, and HTTPS.</p></div>
          </div>
        </Section>

        <Section id="reports" kicker="10 · Reports" title="Six technical reports"
          lead="Each report goes deeper than this page, with the measured data and the scripts that produced it.">
          <div className="reports">
            {reports.map((r) => (
              <a key={r.file} className="report" href={pdf(r.file)} target="_blank" rel="noreferrer">
                <span className="rn">{String(r.n).padStart(2, '0')}</span>
                <span className="rt">{r.title}</span>
                <span className="rb">{r.blurb}</span>
                <span className="rl">Open PDF ↗</span>
              </a>
            ))}
          </div>
          <div className="card run">
            <h3>Run it yourself</h3>
            <pre><code>{`cd ros2_ws
./setup_workspace.sh          # RB1 packages, patch, rosdep, colcon build
./run_web_sim.sh --build      # Gazebo + web_bridge + backend + frontend
# open http://localhost:5173 → Admin → Robot Settings → Use Gazebo Simulation`}</code></pre>
            <p className="muted small">Needs Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic, Java 17, Node 18+ and MySQL 8. Full steps are in the repository README.</p>
          </div>
        </Section>
      </main>
      <footer className="foot">
        <div className="wrap">
          <p>Indoor Autonomous Delivery Robot · Hüseyin Tozluyurt · 2026</p>
          <p className="muted small">The Robotnik RB1 robot, sensors and worlds come from RobotnikAutomation and keep their own licenses.</p>
        </div>
      </footer>
    </LightboxProvider>
  )
}
