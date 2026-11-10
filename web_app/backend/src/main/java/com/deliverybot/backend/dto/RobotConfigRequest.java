package com.deliverybot.backend.dto;

public class RobotConfigRequest {

    private String raspberryPiIp;
    private Integer raspberryPiPort;

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
}