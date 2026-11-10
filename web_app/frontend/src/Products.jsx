function Products() {
  return (
    <div className="public-page">
      <section className="public-hero">
        <h1>DeliveryBot Products</h1>
        <p>
          DeliveryBot is an indoor autonomous delivery robot system that combines
          robotics, computer vision, embedded systems, ROS2, and full-stack web
          development.
        </p>
      </section>

      <section className="product-grid">
        <div className="product-card">
          <img
            src="/deliverybot-robot.jpg"
            alt="DeliveryBot Robot"
            className="product-image"
          />

          <div className="product-content">
            <h2>DeliveryBot Robot</h2>
            <p>
              DeliveryBot is designed as a low-cost indoor service and delivery
              robot. It can be used in cafes, offices, libraries, laboratories,
              and campus environments.
            </p>

            <ul>
              <li>Camera-based indoor navigation</li>
              <li>ArUco marker-based table targeting</li>
              <li>Distance sensor obstacle awareness</li>
              <li>Raspberry Pi and microcontroller integration</li>
              <li>ROS2-ready architecture</li>
            </ul>
          </div>
        </div>

        <div className="product-card">
          <img
            src="/deliverybot-webapp.jpg"
            alt="DeliveryBot Web Application"
            className="product-image"
          />

          <div className="product-content">
            <h2>DeliveryBot Web Application</h2>
            <p>
              The DeliveryBot web application allows users and admins to interact
              with the robot system through a modern web interface.
            </p>

            <ul>
              <li>User order creation</li>
              <li>Admin table map management</li>
              <li>Robot control panel</li>
              <li>Camera streaming page</li>
              <li>Distance sensor monitoring</li>
              <li>User and admin management</li>
            </ul>
          </div>
        </div>

        <div className="product-card wide-product-card">
          <img
            src="/deliverybot-system.jpg"
            alt="DeliveryBot System Architecture"
            className="product-image"
          />

          <div className="product-content">
            <h2>Integrated Robotics System</h2>
            <p>
              DeliveryBot is not only a robot or a website. It is a complete
              integrated system where the web application, backend server,
              database, Raspberry Pi, computer vision, sensors, and robot control
              software communicate with each other.
            </p>

            <div className="architecture-flow">
              React Web App → Spring Boot Backend → MySQL Database → Raspberry Pi → ROS2 / Sensors / Camera
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

export default Products;