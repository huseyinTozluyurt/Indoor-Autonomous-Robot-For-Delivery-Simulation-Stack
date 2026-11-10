-- Creates the DeliveryBot database and its user (run once as MySQL root):
--   sudo mysql < web_app/database/create_database.sql
-- The tables are created by the Spring Boot backend on first start
-- (spring.jpa.hibernate.ddl-auto=update). Then load the test users:
--   mysql -u deliverybot_user -p deliverybot_db < web_app/database/seed_users.sql
--
-- 'deliverybot123' is the local development default used by application.properties.
-- Pick your own password here and pass it to the backend as DB_PASSWORD.
CREATE DATABASE IF NOT EXISTS deliverybot_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'deliverybot_user'@'localhost' IDENTIFIED BY 'deliverybot123';
GRANT ALL PRIVILEGES ON deliverybot_db.* TO 'deliverybot_user'@'localhost';
FLUSH PRIVILEGES;
