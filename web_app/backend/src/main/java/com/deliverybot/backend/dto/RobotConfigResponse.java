package com.deliverybot.backend.dto;

public class RobotConfigResponse {

    private Long id;
    private String raspberryPiIp;
    private Integer raspberryPiPort;
    private String baseUrl;

    public RobotConfigResponse(
            Long id,
            String raspberryPiIp,
            Integer raspberryPiPort,
            String baseUrl
    ) {
        this.id = id;
        this.raspberryPiIp = raspberryPiIp;
        this.raspberryPiPort = raspberryPiPort;
        this.baseUrl = baseUrl;
    }

    public Long getId() {
        return id;
    }

    public String getRaspberryPiIp() {
        return raspberryPiIp;
    }

    public Integer getRaspberryPiPort() {
        return raspberryPiPort;
    }

    public String getBaseUrl() {
        return baseUrl;
    }
}