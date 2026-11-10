package com.deliverybot.backend.controller;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.deliverybot.backend.model.RobotCommand;
import com.deliverybot.backend.service.RobotCommandService;

@RestController
@RequestMapping("/api/robot/command-history")
public class RobotCommandController {

    private final RobotCommandService robotCommandService;

    public RobotCommandController(RobotCommandService robotCommandService) {
        this.robotCommandService = robotCommandService;
    }

    @GetMapping
    public List<RobotCommand> getAllCommands() {
        return robotCommandService.getAllCommands();
    }
}