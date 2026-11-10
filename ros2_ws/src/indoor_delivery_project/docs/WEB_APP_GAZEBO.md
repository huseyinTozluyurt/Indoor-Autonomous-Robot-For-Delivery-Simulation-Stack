# DeliveryBot web app ↔ Gazebo delivery simulation

The Spring Boot backend talks to "the robot" through a small REST API on port 5000
(`/robot/delivery`, `/robot/command`, `/robot/status`, `/robot/sensors/latest`,
`/robot/camera-stream`). The real robot serves it from the Raspberry Pi. In the
simulation, the ROS2 node **`web_bridge`** serves the same API. To switch between
the two, you only change the IP and port in **Robot Settings**.

```
React (5173) ──> Spring Boot (8080) + MySQL ──HTTP──> web_bridge (5000) ──ROS2──> Gazebo robot
      ^                    ^                                │
      └── polls orders ────┴──── POST /api/orders/robot-status (Delivering / Delivered / Failed / Cancelled)
```

`web_bridge` is `delivery_navigator` behind an HTTP server. It uses the same map,
the same ArUco EKF localization, the same Dijkstra planning, and the same check that
the marker is in view at the point.

## Run everything with one command

```bash
~/ros2_jazzy_ws/run_web_sim.sh --build     # the first time (builds the package)
~/ros2_jazzy_ws/run_web_sim.sh             # every other time
```

This starts Gazebo (world `two_buildings`), `web_bridge` with the map
`campus_full_map7`, the Spring Boot backend (`./mvnw spring-boot:run`) and the React
frontend (`npm run dev`), all in one terminal. Open http://localhost:5173.
**Ctrl+C stops all of them.** MySQL has to be running already
(`sudo systemctl start mysql`); the script warns you if it isn't.

Options are passed on as `name:=value`:

```bash
~/ros2_jazzy_ws/run_web_sim.sh gui:=false rtf:=3.0           # no Gazebo window, 3x speed
~/ros2_jazzy_ws/run_web_sim.sh map_dir:=~/ros2_jazzy_ws/maps/campus6 world:=campus_area
~/ros2_jazzy_ws/run_web_sim.sh webapp:=false                 # only simulation + web_bridge
~/ros2_jazzy_ws/run_web_sim.sh webapp_dir:=~/somewhere/Back-Front
```

The backend and the frontend start 20 s after Gazebo (`webapp_delay:=20.0`).
Maven, Java and Vite starting at the same moment can starve Gazebo, and then the
robot controllers time out (`Switch controller timed out`,
`Failed to activate controller : joint_state_broadcaster`). If that still happens,
use `gui:=false` or a longer `webapp_delay`, or make Gazebo render on the NVIDIA GPU
(see "libEGL warning: egl: failed to create dri2 screen" in COMMANDS.md).

The world must be the one the map was made in. `campus_full_map7` starts at
(-17, -17), which is the `two_buildings` world. The `campus`/`campus2`..`campus6` maps
start at (-25, 0), which is `campus_area`.

The script only wraps this launch file, so you can also run it directly:

```bash
cd ~/ros2_jazzy_ws && source install/setup.bash
ros2 launch indoor_delivery_project web_sim.launch.py
```

## Or run the parts in separate terminals

```bash
# 1. Simulation (robot at home)
cd ~/ros2_jazzy_ws && source install/setup.bash
ros2 launch indoor_delivery_project sim.launch.py world:=two_buildings

# 2. Web bridge
cd ~/ros2_jazzy_ws && source install/setup.bash
ros2 run indoor_delivery_project web_bridge --ros-args \
    -p map_dir:=~/ros2_jazzy_ws/maps/campus_full_map7 \
    -p backend_url:=http://localhost:8080/api

# 3. Backend (MySQL running)
cd ~/Downloads/WebApplication/Back-Front/backend && ./mvnw spring-boot:run

# 4. Frontend
cd ~/Downloads/WebApplication/Back-Front/robotProjectApp/robotProjectApp && npm run dev
```

## Shop, operator and campus map

There are three kinds of users. The role decides the page you land on after login.

| Role | Account (from `database/seed_users.sql`) | Page |
|---|---|---|
| USER | `user1@deliverybot.com` / `user123` (or register) | **Order** (`/main`) |
| OPERATOR | `operator@deliverybot.com` / `operator123` | **Operator** (`/operator`) |
| ADMIN | `admin@deliverybot.com` / `admin123` | **Admin** (`/admin`), can also open the operator page |

When the backend starts it makes room for the OPERATOR role in the `users` table, gives
`operator@deliverybot.com` the OPERATOR role if it was still an admin, and adds 10 sample
products. Admins can change roles in **Manage Users**.

The **campus map** on these pages is the robot's own SLAM map (`map_dir`, by default
`campus_full_map7`), served by `web_bridge` as `/robot/map.png` and `/robot/map-info`. It shows
the delivery points with their ArUco IDs, the robot (red arrow), its current route (red) and
the planned route (blue, dashed).

1. **User** (`/main`): adds products to the cart, clicks the delivery point on the map
   (or picks it in the list), and presses **Place order**. The order is saved as
   **Preparing**. *My orders* shows every order with live progress
   *Preparing → Delivering → Delivered* and the robot's message. Many users can order
   at the same time.
2. **Operator** (`/operator`): sees all *Preparing* orders, with the number of orders per
   point on the map. Tick the orders you put into the robot (or click a point on the map
   to tick all its orders). The page asks the robot for the **Dijkstra shortest tour**
   (`/robot/plan`): the order of the stops, every leg in metres and the total, compared with
   driving them in order of arrival. **Robot is loaded: deliver …** sends them as one
   mission (`/robot/mission`). They become **Delivering**, the robot drives the tour in
   Gazebo, each order becomes **Delivered** (or *Failed*) when the robot reaches its point,
   and the robot returns to base. The database, the user's page and the operator's page all
   update by themselves.
3. **Admin → Camera Streaming & Take Control**: the robot camera (MJPEG from the
   simulation), the robot on the campus map, and manual control. **Take control** pauses a
   running delivery (the orders stay *Delivering*, message "Paused"), then hold the arrow
   buttons or the arrow keys / W A S D to drive (space = stop). **Release robot** gives it
   back: it plans again from where it is and finishes the deliveries. **Emergency stop**
   cancels everything; cancelled orders go back to the operator's list.

The old table page is still at `/table-order`, and **View Orders** still lists every order
with customer, products and delivery point.

## Use it

1. **Robot Settings** → **Use Gazebo Simulation**. This saves `127.0.0.1:5000` and
   tests the connection. The page then lists the delivery points of the map with their
   ArUco IDs.
2. **Adjust Table Map**: give every table the **ArUco ID** of the delivery point it
   should go to (for example 12 = `r_delivery_point_1`, 41 = `a_delivery_point_2`).
   If you want a fixed name instead, you can put the point name in the table's
   **route** field (for example `b_delivery_point_3`). The route is checked first.
3. A user creates an order on the main page. It is saved as *Pending*.
4. **View Orders** → **Send to Robot** (or **Send All Pending to Robot**). The status
   then changes on its own: *Dispatched → Delivering → Delivered* (or *Failed* /
   *Cancelled*). The **Robot** column shows the delivery point and the navigator's
   message. If several orders are waiting together, they are driven as one
   shortest-order tour, and then the robot returns home.
5. **Control Robot** shows the live state and pose. It has buttons for every delivery
   point, manual driving (Forward/Left/...; only when the robot is not on a delivery),
   Stop, Emergency Stop (also cancels waiting orders), Return to Base, Pose = Home and
   Find Pose.
6. **Distance Monitoring** shows the closest lidar distance in 4 directions (cm from
   the robot body). **Camera Streaming** shows the robot camera as MJPEG, with the
   ArUco IDs it sees.

To dispatch every new order automatically, set `robot.auto-dispatch=true` in
`backend/src/main/resources/application.properties`.

## web_bridge parameters

| Parameter | Default | Meaning |
|---|---|---|
| `map_dir` | `~/ros2_jazzy_ws/maps/aruco_slam_map` | Map folder made by the mapper |
| `http_port` / `http_host` | `5000` / `0.0.0.0` | Where the API listens |
| `backend_url` | `http://localhost:8080/api` | Where status reports go (`''` = off) |
| `return_home` | `true` | Go home after the orders |
| `optimize_order` | `true` | Shortest order for orders that wait together |
| `stream_topic` / `stream_fps` | `/robot/aruco_camera/image_raw` / `5` | Camera stream |
| `manual_speed` / `manual_turn` / `manual_duration` | `0.3` / `0.6` / `0.6` | Manual buttons |
| `body_radius` | `0.3` | Subtracted from the lidar distances |
| `jpeg_quality` | `70` | Camera stream quality |
| `initial_pose`, `dwell_time`, ... | | Same as `delivery_navigator` |

You can test the API without the web app:

```bash
curl localhost:5000/robot/status
curl localhost:5000/robot/points
curl -X POST localhost:5000/robot/delivery -H 'Content-Type: application/json' \
     -d '{"orderID": "test1", "targetArucoId": 12}'
curl -X POST localhost:5000/robot/command -H 'Content-Type: application/json' -d '{"command": "STOP"}'
curl -X POST localhost:5000/robot/plan -H 'Content-Type: application/json' \
     -d '{"stops": ["a_delivery_point_2", "b_delivery_point_3"]}'
curl -X POST localhost:5000/robot/mission -H 'Content-Type: application/json' \
     -d '{"orders": [{"orderID": "t1", "deliveryPoint": "a_delivery_point_2"},
                     {"orderID": "t2", "deliveryPoint": "b_delivery_point_3"}]}'
curl -o map.png localhost:5000/robot/map.png
```

## Changed files in the web app

Backend: `OrderRecord` (new columns `delivery_point`, `robot_message`, which Hibernate
adds by itself with `ddl-auto=update`), `OrderRecordRepository`, `OrderService`,
`OrderController` (`POST /api/orders/{id}/dispatch`, `POST /api/orders/robot-status`),
`RobotApiController` (`GET /api/robot/points`, `GET /api/robot/camera-url`, status
returns `offline` instead of an error, no more `Map.of` crash on null values),
`RaspberryPiService`, `RestTemplateConfig` (2 s / 5 s timeouts), `DeliveryCommandRequest`
(`orderDbId`), new `RobotStatusUpdateRequest`, `application.properties`.

Frontend: `api.js`, `ViewOrders.jsx` (orders come from the backend instead of
localStorage), `ControlRobot.jsx` (goes through the backend instead of a hard-coded
Pi IP), `RobotSettings.jsx`, new `RobotLiveStatus.jsx`, `index.css`.

Shop / operator / camera control: new `Product`, `OrderItem`, `ProductRepository`,
`ProductController` (`/api/products`), `PlaceOrderRequest`, `BatchDispatchRequest`;
`UserRole` (OPERATOR), `OrderRecord` (customer, total, note, items; new table `order_items`),
`OrderService`/`OrderController` (`POST /api/orders/place`, `GET /api/orders/user/{id}`,
`POST /api/orders/dispatch-batch`), `RobotApiController` (`/api/robot/map-info`,
`/api/robot/map.png`, `/api/robot/plan`, `/api/robot/drive`), `DataInitializer`.
Frontend: new `ShopPage.jsx`, `OperatorPage.jsx`, `CampusMap.jsx`, `campusPoints.js`,
`orderStatus.jsx`; changed `CameraStreaming.jsx`, `Navbar.jsx`, `LoginPage.jsx`, `App.jsx`,
`AdminPage.jsx`, `ManageUsers.jsx`, `ViewOrders.jsx`, `api.js`, `index.css`.
ROS: `web_bridge.py` (map, plan, mission, take control). Rebuild once with
`~/ros2_jazzy_ws/run_web_sim.sh --build`.

The original files are in `Back-Front/_backup_before_gazebo_link.tgz`,
`_backup_before_manage_users.tgz` and `_backup_before_shop_operator.tgz`.
