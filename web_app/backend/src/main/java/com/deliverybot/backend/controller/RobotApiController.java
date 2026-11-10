package com.deliverybot.backend.controller;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.server.ResponseStatusException;

import com.deliverybot.backend.dto.DeliveryCommandRequest;
import com.deliverybot.backend.dto.RobotCommandRequest;
import com.deliverybot.backend.dto.RobotSensorResponse;
import com.deliverybot.backend.model.RobotCommand;
import com.deliverybot.backend.service.RaspberryPiService;
import com.deliverybot.backend.service.RobotCommandService;

@RestController
@RequestMapping("/api/robot")
public class RobotApiController {

    private final RaspberryPiService raspberryPiService;
    private final RobotCommandService robotCommandService;

    public RobotApiController(
            RaspberryPiService raspberryPiService,
            RobotCommandService robotCommandService
    ) {
        this.raspberryPiService = raspberryPiService;
        this.robotCommandService = robotCommandService;
    }

    private ResponseStatusException robotUnreachable(RestClientException e) {
        if (e instanceof RestClientResponseException r) {
            // the robot answered with an error (e.g. 409 busy): keep its status code
            return new ResponseStatusException(r.getStatusCode(), r.getResponseBodyAsString(), e);
        }
        return new ResponseStatusException(HttpStatus.BAD_GATEWAY,
                "Robot server not reachable: " + e.getMessage(), e);
    }

    @PostMapping("/commands")
    public Map<String, Object> sendCommand(@RequestBody RobotCommandRequest request) {
        RobotCommand savedCommand = robotCommandService.createCommand(request);

        Map<String, Object> piResponse;
        try {
            piResponse = raspberryPiService.sendRobotCommand(request);
        } catch (RestClientException e) {
            throw robotUnreachable(e);
        }

        // HashMap, not Map.of: Map.of throws on null values (e.g. an empty robot answer)
        Map<String, Object> result = new HashMap<>();
        result.put("message", "Command saved and sent to the robot");
        result.put("commandId", savedCommand.getId());
        result.put("command", savedCommand.getCommand());
        result.put("piResponse", piResponse);
        return result;
    }

    /**
     * Manual driving from the camera page (sent several times per second while a
     * button is held): forwarded to the robot but not stored in robot_commands.
     */
    @PostMapping("/drive")
    public Map<String, Object> drive(@RequestBody RobotCommandRequest request) {
        try {
            Map<String, Object> piResponse = raspberryPiService.sendRobotCommand(request);
            return piResponse != null ? piResponse : Map.of("ok", true);
        } catch (RestClientException e) {
            throw robotUnreachable(e);
        }
    }

    @PostMapping("/delivery")
    public Map<String, Object> sendDeliveryCommand(@RequestBody DeliveryCommandRequest request) {
        Map<String, Object> piResponse;
        try {
            piResponse = raspberryPiService.sendDeliveryCommand(request);
        } catch (RestClientException e) {
            throw robotUnreachable(e);
        }

        Map<String, Object> result = new HashMap<>();
        result.put("message", "Delivery command sent to the robot");
        result.put("orderID", request.getOrderID());
        result.put("tableNumber", request.getTableNumber());
        result.put("targetArucoId", request.getTargetArucoId());
        result.put("route", request.getRoute());
        result.put("piResponse", piResponse);
        return result;
    }

    @GetMapping("/sensors/latest")
    public RobotSensorResponse getLatestSensorData() {
        try {
            return raspberryPiService.getLatestSensorData();
        } catch (RestClientException e) {
            throw robotUnreachable(e);
        }
    }

    /** Never fails: reports status "offline" when the robot server is not reachable. */
    @GetMapping("/status")
    public Map<String, Object> getRobotStatus() {
        try {
            Map<String, Object> status = raspberryPiService.getRobotStatus();
            return status != null ? status : Map.of("status", "unknown");
        } catch (RestClientException e) {
            Map<String, Object> offline = new HashMap<>();
            offline.put("status", "offline");
            offline.put("error", e.getMessage());
            return offline;
        }
    }

    /** Delivery points known to the robot (for the simulation: from the SLAM map). */
    @GetMapping("/points")
    public List<Map<String, Object>> getDeliveryPoints() {
        try {
            return raspberryPiService.getDeliveryPoints();
        } catch (RestClientException e) {
            throw robotUnreachable(e);
        }
    }

    @GetMapping("/camera-url")
    public Map<String, Object> getCameraUrl() {
        return Map.of("url", raspberryPiService.getCameraStreamUrl());
    }

    /** Campus map: image size, metres per pixel, origin, home and delivery points. */
    @GetMapping("/map-info")
    public Map<String, Object> getMapInfo() {
        try {
            return raspberryPiService.getMapInfo();
        } catch (RestClientException e) {
            throw robotUnreachable(e);
        }
    }

    @GetMapping("/map.png")
    public ResponseEntity<byte[]> getMapPng(@RequestParam(defaultValue = "false") boolean refresh) {
        try {
            return ResponseEntity.ok().contentType(MediaType.IMAGE_PNG)
                    .header("Cache-Control", "no-cache")
                    .body(raspberryPiService.getMapPng(refresh));
        } catch (RestClientException e) {
            throw robotUnreachable(e);
        }
    }

    /** Route preview: {"stops": ["a_delivery_point_2", ...], "end": "home"} */
    @PostMapping("/plan")
    public Map<String, Object> planRoute(@RequestBody Map<String, Object> request) {
        try {
            return raspberryPiService.planRoute(request);
        } catch (RestClientException e) {
            throw robotUnreachable(e);
        }
    }
}
