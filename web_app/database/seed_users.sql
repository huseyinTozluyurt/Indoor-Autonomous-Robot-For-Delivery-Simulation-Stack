-- Users with known passwords for DeliveryBot (deliverybot_db.users).
-- Passwords are stored as BCrypt hashes, as the backend expects.
--
--   email                      password      role
--   admin@deliverybot.com      admin123      ADMIN
--   operator@deliverybot.com   operator123   OPERATOR (loads the robot, starts deliveries)
--   user1@deliverybot.com      user123       USER
--   user2@deliverybot.com      user123       USER
--   user3@deliverybot.com      user123       USER
--
-- More users with your own passwords: Admin page -> Manage Users -> Add User.

-- Older databases have role as ENUM('ADMIN','USER'): make room for OPERATOR.
ALTER TABLE users MODIFY role VARCHAR(20);

INSERT INTO users (name, surname, age, email, phone, password, role, created_at) VALUES
('Default',  'Admin',    NULL, 'admin@deliverybot.com',    '+900000000000', '$2a$10$kckcs2O.dl6/xQqRodgWg.DHgOsQAVSLf/DhnhuGGQHYlFvLxdnJy', 'ADMIN', NOW()),
('Robot',    'Operator', NULL, 'operator@deliverybot.com', NULL,            '$2a$10$GvE9EgDuMcYjMTLldVOCde3Ih9lFyF2ysUOP6lDecZndaglBxBkku', 'OPERATOR', NOW()),
('Test',     'User1',    21,   'user1@deliverybot.com',    NULL,            '$2a$10$XlIbk9HhgMJczKg/6zE/Q.Izer1NckUkmBwFiRMCLxKyaDHUfE9Z6', 'USER',  NOW()),
('Test',     'User2',    22,   'user2@deliverybot.com',    NULL,            '$2a$10$v0uOlNGe7u5k20iErK8CbOkTToFq6PVK.lqAiMl9iALZOal8lKtKi', 'USER',  NOW()),
('Test',     'User3',    23,   'user3@deliverybot.com',    NULL,            '$2a$10$mrTIuWGmNAXoRiJfeGttSerprk6ileaFxaADkXWxlYL/YPFqFVTJu', 'USER',  NOW());
