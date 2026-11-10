package com.deliverybot.backend.model;

import java.time.LocalDateTime;

import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "sensor_logs")
public class SensorLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Integer frontDistance;

    private Integer leftDistance;

    private Integer rightDistance;

    private Integer backDistance;

    private Integer errorCode;

    private LocalDateTime createdAt;

    public SensorLog() {
        this.createdAt = LocalDateTime.now();
    }

    public Long getId() {
        return id;
    }

    public Integer getFrontDistance() {
        return frontDistance;
    }

    public void setFrontDistance(Integer frontDistance) {
        this.frontDistance = frontDistance;
    }

    public Integer getLeftDistance() {
        return leftDistance;
    }

    public void setLeftDistance(Integer leftDistance) {
        this.leftDistance = leftDistance;
    }

    public Integer getRightDistance() {
        return rightDistance;
    }

    public void setRightDistance(Integer rightDistance) {
        this.rightDistance = rightDistance;
    }

    public Integer getBackDistance() {
        return backDistance;
    }

    public void setBackDistance(Integer backDistance) {
        this.backDistance = backDistance;
    }

    public Integer getErrorCode() {
        return errorCode;
    }

    public void setErrorCode(Integer errorCode) {
        this.errorCode = errorCode;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }
}