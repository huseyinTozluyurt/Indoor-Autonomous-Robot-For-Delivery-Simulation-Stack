package com.deliverybot.backend.model;

import java.time.LocalDateTime;

import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;

@Entity
@Table(name = "robot_config")
public class RobotConfig {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String raspberryPiIp;

    private Integer raspberryPiPort;

    private String baseUrl;

    private LocalDateTime updatedAt;

    public RobotConfig() {
        this.updatedAt = LocalDateTime.now();
    }

    @PreUpdate
    public void preUpdate() {
        this.updatedAt = LocalDateTime.now();
    }

    public Long getId() {
        return id;
    }

    public String getRaspberryPiIp() {
        return raspberryPiIp;
    }

    public void setRaspberryPiIp(String raspberryPiIp) {
        this.raspberryPiIp = raspberryPiIp;
    }

    public Integer getRaspberryPiPort() {
        return raspberryPiPort;
    }

    public void setRaspberryPiPort(Integer raspberryPiPort) {
        this.raspberryPiPort = raspberryPiPort;
    }

    public String getBaseUrl() {
        return baseUrl;
    }

    public void setBaseUrl(String baseUrl) {
        this.baseUrl = baseUrl;
    }

    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }
}