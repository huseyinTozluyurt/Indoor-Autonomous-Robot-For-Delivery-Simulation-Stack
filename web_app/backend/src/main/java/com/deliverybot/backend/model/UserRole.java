package com.deliverybot.backend.model;

public enum UserRole {
    USER,
    OPERATOR,   // robot operator: loads orders into the robot and starts deliveries
    ADMIN
}
