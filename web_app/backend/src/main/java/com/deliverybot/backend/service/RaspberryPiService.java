package com.deliverybot.backend.service;

import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import com.deliverybot.backend.dto.DeliveryCommandRequest;
import com.deliverybot.backend.dto.RobotCommandRequest;
import com.deliverybot.backend.dto.RobotSensorResponse;

/**
 * Talks to the robot server. This is either the Flask server on the Raspberry Pi
 * or the ROS2 "web_bridge" node of the Gazebo simulation: both serve the same
 * REST API, so switching only means changing the IP/port in Robot Settings
 * (simulation on the same PC: 127.0.0.1, port 5000).
 */
@Service
public class RaspberryPiService {

    private final RestTemplate restTemplate;
    private final RobotConfigService robotConfigService;

    public RaspberryPiService(
            RestTemplate restTemplate,
            RobotConfigService robotConfigService
    ) {
        this.restTemplate = restTemplate;
        this.robotConfigService = robotConfigService;
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> sendRobotCommand(RobotCommandRequest request) {
        String url = robotConfigService.getRaspberryPiBaseUrl() + "/robot/command";
        return restTemplate.postForObject(url, request, Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> sendDeliveryCommand(DeliveryCommandRequest request) {
        String url = robotConfigService.getRaspberryPiBaseUrl() + "/robot/delivery";
        return restTemplate.postForObject(url, request, Map.class);
    }

    public RobotSensorResponse getLatestSensorData() {
        String url = robotConfigService.getRaspberryPiBaseUrl() + "/robot/sensors/latest";
        return restTemplate.getForObject(url, RobotSensorResponse.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> getRobotStatus() {
        String url = robotConfigService.getRaspberryPiBaseUrl() + "/robot/status";
        return restTemplate.getForObject(url, Map.class);
    }

    /** Delivery points the robot knows (name, ArUco marker id, position). */
    @SuppressWarnings("unchecked")
    public List<Map<String, Object>> getDeliveryPoints() {
        String url = robotConfigService.getRaspberryPiBaseUrl() + "/robot/points";
        return restTemplate.getForObject(url, List.class);
    }

    /** Several orders as one delivery tour: {"orders": [{orderID, orderDbId, deliveryPoint, ...}]} */
    @SuppressWarnings("unchecked")
    public Map<String, Object> sendMission(Map<String, Object> mission) {
        String url = robotConfigService.getRaspberryPiBaseUrl() + "/robot/mission";
        return restTemplate.postForObject(url, mission, Map.class);
    }

    /** Shortest tour through the stops, without driving (route preview for the operator). */
    @SuppressWarnings("unchecked")
    public Map<String, Object> planRoute(Map<String, Object> request) {
        String url = robotConfigService.getRaspberryPiBaseUrl() + "/robot/plan";
        return restTemplate.postForObject(url, request, Map.class);
    }

    /** Size, resolution, origin and points of the campus map image. */
    @SuppressWarnings("unchecked")
    public Map<String, Object> getMapInfo() {
        String url = robotConfigService.getRaspberryPiBaseUrl() + "/robot/map-info";
        return restTemplate.getForObject(url, Map.class);
    }

    private volatile byte[] mapPng;
    private volatile String mapPngFrom;

    /** The campus map PNG (kept in memory: it only changes with another map). */
    public byte[] getMapPng(boolean refresh) {
        String url = robotConfigService.getRaspberryPiBaseUrl() + "/robot/map.png";
        byte[] cached = mapPng;
        if (!refresh && cached != null && url.equals(mapPngFrom)) {
            return cached;
        }
        byte[] png = restTemplate.getForObject(url, byte[].class);
        mapPng = png;
        mapPngFrom = url;
        return png;
    }

    public String getCameraStreamUrl() {
        return robotConfigService.getRaspberryPiBaseUrl() + "/robot/camera-stream";
    }
}
