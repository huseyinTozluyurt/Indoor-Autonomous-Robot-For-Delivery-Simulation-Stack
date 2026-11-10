package com.deliverybot.backend.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.deliverybot.backend.dto.RobotConfigRequest;
import com.deliverybot.backend.dto.RobotConfigResponse;
import com.deliverybot.backend.service.RobotConfigService;

@RestController
@RequestMapping("/api/robot/config")
public class RobotConfigController {

    private final RobotConfigService robotConfigService;

    public RobotConfigController(RobotConfigService robotConfigService) {
        this.robotConfigService = robotConfigService;
    }

    @GetMapping
    public RobotConfigResponse getConfig() {
        return robotConfigService.getConfig();
    }

    @PutMapping
    public RobotConfigResponse updateConfig(@RequestBody RobotConfigRequest request) {
        return robotConfigService.updateConfig(request);
    }
}