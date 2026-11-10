package com.deliverybot.backend.controller;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.deliverybot.backend.dto.SensorLogRequest;
import com.deliverybot.backend.model.SensorLog;
import com.deliverybot.backend.service.SensorService;

@RestController
@RequestMapping("/api/sensors")
public class SensorController {

    private final SensorService sensorService;

    public SensorController(SensorService sensorService) {
        this.sensorService = sensorService;
    }

    @GetMapping("/logs")
    public List<SensorLog> getAllLogs() {
        return sensorService.getAllLogs();
    }

    @GetMapping("/latest")
    public SensorLog getLatestLog() {
        return sensorService.getLatestLog();
    }

    @PostMapping("/logs")
    public SensorLog createLog(@RequestBody SensorLogRequest request) {
        return sensorService.createLog(request);
    }
}