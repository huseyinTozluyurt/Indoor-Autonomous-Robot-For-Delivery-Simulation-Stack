from common import fig, fig2, table, page, reset

ARCH = """<figure><svg viewBox="0 0 760 250" width="100%" xmlns="http://www.w3.org/2000/svg">
<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#334e68"/></marker></defs>
<g font-size="12">
<rect x="10" y="20" width="200" height="200" rx="8" fill="#e3f0fa" stroke="#1f5f8b"/><text x="110" y="42" text-anchor="middle" font-weight="bold">Browser (React 19 + Vite)</text>
<text x="22" y="68">/main – Shop (USER)</text><text x="22" y="88">/operator – Operator</text><text x="22" y="108">/admin/* – Admin pages</text>
<text x="22" y="128">CampusMap.jsx (SLAM map)</text><text x="22" y="148">api.js (fetch wrapper)</text><text x="22" y="168">polls every 2 s</text><text x="22" y="200" fill="#52606d">:5173</text>
<rect x="280" y="20" width="210" height="200" rx="8" fill="#e8f5e9" stroke="#2f855a"/><text x="385" y="42" text-anchor="middle" font-weight="bold">Spring Boot 3.5 (Java 17)</text>
<text x="292" y="68">Controllers: Auth, Product,</text><text x="292" y="86">Order, RobotApi, RobotConfig,</text><text x="292" y="104">AdminUser, Table, Sensor, Map</text>
<text x="292" y="128">Services + JPA repositories</text><text x="292" y="148">RaspberryPiService</text><text x="292" y="166">(RestTemplate, 2 s / 5 s)</text><text x="292" y="200" fill="#52606d">:8080  /api/*</text>
<rect x="560" y="20" width="190" height="90" rx="8" fill="#fff4e5" stroke="#c05621"/><text x="655" y="45" text-anchor="middle" font-weight="bold">MySQL 8</text><text x="655" y="66" text-anchor="middle">deliverybot_db</text><text x="655" y="86" text-anchor="middle" fill="#52606d">ddl-auto=update</text>
<rect x="560" y="130" width="190" height="90" rx="8" fill="#f3e8ff" stroke="#6b46c1"/><text x="655" y="155" text-anchor="middle" font-weight="bold">Robot REST API :5000</text><text x="655" y="176" text-anchor="middle">web_bridge (Gazebo)</text><text x="655" y="196" text-anchor="middle">or Raspberry Pi 4</text>
<line x1="210" y1="110" x2="278" y2="110" stroke="#334e68" stroke-width="2" marker-end="url(#a)"/><text x="244" y="102" text-anchor="middle" font-size="10">REST/JSON</text>
<line x1="490" y1="65" x2="558" y2="65" stroke="#334e68" stroke-width="2" marker-end="url(#a)"/><text x="524" y="58" text-anchor="middle" font-size="10">JPA</text>
<line x1="490" y1="165" x2="558" y2="165" stroke="#334e68" stroke-width="2" marker-end="url(#a)"/><text x="524" y="158" text-anchor="middle" font-size="10">HTTP</text>
<line x1="558" y1="195" x2="492" y2="195" stroke="#6b46c1" stroke-width="2" stroke-dasharray="5,3" marker-end="url(#a)"/><text x="524" y="212" text-anchor="middle" font-size="10">status</text>
</g></svg><figcaption><b>Figure 1.</b> Three-tier architecture of the DeliveryBot web application. The backend is the only part that talks to the robot.</figcaption></figure>"""


def build():
    reset()
    from common import FIGNUM
    FIGNUM['n'] = 1
    b = []
    b.append("""
<h2>1. Purpose and scope</h2>
<p>The DeliveryBot web application is the customer- and staff-facing part of the indoor delivery robot. Customers order
food and drinks from a shop page and pick the delivery point on a campus map; an operator loads the orders into the robot
and starts a delivery tour; an administrator manages users, orders and robot settings and can watch the robot's camera and
drive it by hand. The same application drives either the robot in the Gazebo simulation or the physical robot (Raspberry
Pi&nbsp;4), because both expose the same REST API on port 5000.</p>
<p>This report describes the architecture, data model, roles and pages, the REST API and the order life cycle, and records
how the application grew from the first login/table prototype to the shop/operator version that is connected to the
simulation. Sources: <code>web_app/</code> in the GitHub-ready repository (<code>indoor-delivery-robot</code>) and the
original project in <code>~/Downloads/WebApplication/Back-Front</code>.</p>
<h2>2. Technology stack</h2>""")
    b.append(table(['Layer', 'Technology', 'Notes'], [
        ['Frontend', 'React 19, React Router 7, Vite 6', '24 page components in <code>frontend/src</code>; no UI framework, plain CSS'],
        ['Backend', 'Spring Boot 3.5.15, Java 17, Maven wrapper', 'spring-boot-starter-web, data-jpa, validation; Lombok'],
        ['Security', 'spring-security-crypto (BCrypt)', 'Passwords stored as BCrypt hashes; role decides the landing page'],
        ['Database', 'MySQL 8 (<code>deliverybot_db</code>)', 'Schema created by Hibernate (<code>ddl-auto=update</code>); seed SQL for test users'],
        ['Robot link', 'RestTemplate → HTTP :5000', 'Base URL from <i>Admin → Robot Settings</i> or <code>ROBOT_BASE_URL</code>'],
    ]))
    b.append("<h2>3. Architecture</h2>" + ARCH)
    b.append("""
<p>The browser never talks to the robot directly. Every robot call goes through the backend
(<code>RobotApiController</code> → <code>RaspberryPiService</code>), which reads the robot's base URL from the
<code>RobotConfig</code> table. This keeps one place for timeouts (2 s connect, 5 s read), turns an unreachable robot into
an <i>offline</i> status instead of an error page, and lets the operator switch between the Gazebo simulation
(<code>127.0.0.1:5000</code>) and the real robot by changing one setting. The robot side reports progress back with
<code>POST /api/orders/robot-status</code>, so the database always holds the latest state of every order.</p>
<h2>4. Data model</h2>""")
    b.append(table(['Entity / table', 'Key fields', 'Purpose'], [
        ['<code>AppUser</code>', 'name, e-mail, phone, BCrypt password, <code>UserRole</code> (USER / OPERATOR / ADMIN), active', 'Accounts and roles'],
        ['<code>Product</code>', 'name, description, category, price, icon, available', 'Shop catalogue (10 sample products added by <code>DataInitializer</code>)'],
        ['<code>OrderRecord</code> (<code>delivery_orders</code>)', 'order code, user, customer, total, note, status, ArUco id, <b>delivery_point</b>, <b>robot_message</b>, timestamps', 'One delivery order'],
        ['<code>OrderItem</code> (<code>order_items</code>)', 'product, quantity, price', 'Lines of an order (one-to-many, cascade)'],
        ['<code>RobotConfig</code>', 'raspberryPiIp, raspberryPiPort, baseUrl', 'Where the robot API lives'],
        ['<code>TableRecord</code>, <code>MapConfig</code>', 'table → ArUco id / route', 'Legacy table-ordering map'],
        ['<code>RobotCommand</code>, <code>SensorLog</code>', 'command history, distance logs', 'Audit and monitoring'],
    ]))
    b.append("<h2>5. Roles and pages</h2>")
    b.append(table(['Role', 'Landing page', 'What the user can do'], [
        ['USER', '<code>/main</code> Shop', 'Browse products by category, fill a cart, click a delivery point on the campus map, place an order, follow <i>My orders</i> (Preparing → Delivering → Delivered).'],
        ['OPERATOR', '<code>/operator</code>', 'See all <i>Preparing</i> orders grouped by delivery point, tick the ones put into the robot, preview the Dijkstra shortest tour, press <i>Robot is loaded: deliver</i>.'],
        ['ADMIN', '<code>/admin</code>', 'View Orders, Manage Users (roles, activate, delete), Robot Settings, Camera Streaming &amp; Take Control, Control Robot, Distance Monitoring, Adjust Table Map; can also open the operator page.'],
    ]))
    b.append(fig2('web_shop_page.png', 'Shop page (USER): product grid, cart and delivery point picked on the robot\'s own SLAM map.',
                  'web_operator_route.png', 'Operator page: Preparing orders, the Dijkstra shortest tour on the map and the "Robot is loaded" button.'))
    b.append(fig2('web_view_orders.png', 'Admin → View Orders: every order with status, robot message and Send-to-Robot buttons.',
                  'web_manage_users.png', 'Admin → Manage Users: search, add, change roles; the last admin cannot be demoted.'))
    b.append(fig2('web_robot_settings.png', 'Robot Settings: real robot IP/port or one-click <i>Use Gazebo Simulation</i>, with a connection test and the map\'s delivery points.',
                  'web_camera_take_control.png', 'Camera Streaming &amp; Take Control: MJPEG camera, robot on the campus map and manual driving.'))
    b.append("""
<h2>6. REST API of the backend</h2>""")
    b.append(table(['Group', 'Endpoints (prefix <code>/api</code>)'], [
        ['Auth', '<code>POST /auth/register</code>, <code>POST /auth/login</code>'],
        ['Products', '<code>GET/POST/PUT/DELETE /products</code>'],
        ['Orders', '<code>GET /orders</code>, <code>POST /orders/place</code>, <code>GET /orders/user/{id}</code>, <code>POST /orders/dispatch-batch</code>, <code>POST /orders/{id}/dispatch</code>, <code>PUT /orders/{id}/status</code>, <code>POST /orders/robot-status</code> (called by the robot)'],
        ['Robot proxy', '<code>GET /robot/status</code>, <code>/robot/points</code>, <code>/robot/map-info</code>, <code>/robot/map.png</code>, <code>/robot/sensors/latest</code>, <code>/robot/camera-url</code>; <code>POST /robot/plan</code>, <code>/robot/delivery</code>, <code>/robot/commands</code>, <code>/robot/drive</code>'],
        ['Admin', '<code>/admin/users</code> (CRUD, <code>PUT /{id}/role</code>, <code>PUT /{id}/activate</code>), <code>/robot/config</code>, <code>/robot/command-history</code>, <code>/tables</code>, <code>/maps</code>, <code>/sensors/logs</code>'],
    ]))
    b.append("""
<h2>7. Order life cycle</h2>
<p>An order placed from the shop is stored as <b>Preparing</b>. The operator selects several orders and starts one mission;
the backend sends them in one call to the robot and marks them <b>Delivering</b>. The robot drives the shortest tour and
reports each stop: <b>Delivered</b> when it reached the point and confirmed the right ArUco marker, <b>Failed</b> when it
could not, and <b>Cancelled</b> after an emergency stop. Cancelled and failed orders go back to the operator's list
(<code>OrderService.WAITING = Preparing, Pending, Failed, Cancelled</code>). The legacy admin flow (<i>View Orders → Send to
Robot</i>) uses <b>Pending → Dispatched → Delivering → Delivered</b>. Shop, operator and order pages poll the backend every
2 s, so all users see the change without reloading.</p>
<pre>Place order → Preparing → (operator loads robot) → Delivering → Delivered
                                                          → Failed    → back to the operator list
Emergency stop during a mission → Cancelled → back to the operator list</pre>
<h2>8. Evolution of the application</h2>
<p>The first version (screenshots below, from <code>~/Downloads/WebApplication</code>) was a login/register application with
a "Welcome to the Main Page" screen where the user picked a delivery area and a table number from a floor plan; the
admin sent the order to the Raspberry Pi at a hard-coded IP. The current version keeps those pages (the table page is
still at <code>/table-order</code>) and adds:</p>
<ul>
<li>orders stored in MySQL instead of browser <code>localStorage</code>, with items, totals and robot messages;</li>
<li>the OPERATOR role, the product shop, multi-order missions and the Dijkstra tour preview;</li>
<li>the robot's own SLAM map as the campus map, with delivery points, the robot pose and the planned route;</li>
<li>robot settings stored in the database, a connection test and the one-click Gazebo option;</li>
<li>camera streaming, take control / release and emergency stop.</li>
</ul>""")
    b.append('<div class="row">' + ''.join([
        f'<figure><img src="../figures/{f}"><figcaption>{c}</figcaption></figure>' for f, c in [
            ('early_web_2.jpeg', 'First version: login'), ('early_web_3.jpeg', 'First version: register'),
            ('early_web_7.jpeg', 'First version: table picker')]]) + '</div>')
    b.append("""
<h2>9. Running it</h2>
<pre>sudo systemctl start mysql
sudo mysql &lt; web_app/database/create_database.sql
cd web_app/backend  &amp;&amp; ./mvnw spring-boot:run          # http://localhost:8080
cd web_app/frontend &amp;&amp; npm install &amp;&amp; npm run dev    # http://localhost:5173
# or everything incl. Gazebo:  ros2_ws/run_web_sim.sh</pre>
<p>Test accounts (development only) come from <code>database/seed_users.sql</code>: one admin, one operator and one user.
Database credentials are read from <code>DB_URL</code>, <code>DB_USERNAME</code>, <code>DB_PASSWORD</code>.</p>
<h2>10. Assessment and next steps</h2>
<div class="box"><b>Works today:</b> three roles, shop with campus-map ordering, multi-order missions with a shortest-tour
preview, live status in every page, robot settings with one-click simulation, camera and manual control.</div>
<div class="box warn"><b>Limits:</b> login returns the user and role but there is no session token, so the backend does
not enforce roles on each request; status updates use 2 s polling instead of push (WebSocket/SSE); the robot callback
endpoint is unauthenticated. Before a real deployment add Spring Security with JWT or sessions, role checks per
endpoint, HTTPS, and a shared secret for <code>/orders/robot-status</code>.</div>
""")
    return page('Web Application', 1, 'DeliveryBot: React + Spring Boot + MySQL ordering, operator and admin application', ''.join(b))
