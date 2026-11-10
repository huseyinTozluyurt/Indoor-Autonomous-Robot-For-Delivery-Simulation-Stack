function AboutUs() {
  return (
    <div className="public-page">
      <section className="about-section">
        <div className="about-image-box">
          <img
            src="/developer.jpg"
            alt="Developer"
            className="developer-image"
          />
        </div>

        <div className="about-content">
          <h1>About the Developer</h1>

          <h2>Hüseyin Akar</h2>

          <p>
            Hüseyin Akar is the developer of the DeliveryBot system, an indoor
            autonomous delivery robot project that integrates robotics,
            computer vision, embedded software, backend development, frontend
            development, and database systems.
          </p>

          <p>
            This project demonstrates a full-stack robotics architecture where
            a web application communicates with a Raspberry Pi-based robot. The
            system includes user order management, admin control panels, table
            map configuration, robot commands, camera streaming, and sensor data
            monitoring.
          </p>

          <div className="developer-info-card">
            <h3>Developer Information</h3>

            <p>
              <strong>Name:</strong> Hüseyin Akar
            </p>

            <p>
              <strong>Project:</strong> DeliveryBot
            </p>

            <p>
              <strong>Role:</strong> Full-Stack Robotics Developer
            </p>

            <p>
              <strong>Fields:</strong> Computer Vision, ROS2, Embedded Systems,
              Web Development, Machine Learning
            </p>

            <p>
              <strong>System Stack:</strong> React, Spring Boot, MySQL,
              Raspberry Pi, STM32, Arduino, OpenCV, ROS2
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}

export default AboutUs;