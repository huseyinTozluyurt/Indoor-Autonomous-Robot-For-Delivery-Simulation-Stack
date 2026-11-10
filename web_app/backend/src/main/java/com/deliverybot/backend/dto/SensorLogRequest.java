package com.deliverybot.backend.dto;

public class SensorLogRequest {

    private Integer frontDistance;
    private Integer leftDistance;
    private Integer rightDistance;
    private Integer backDistance;
    private Integer errorCode;

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
}