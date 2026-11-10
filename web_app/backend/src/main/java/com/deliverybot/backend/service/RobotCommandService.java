package com.deliverybot.backend.service;

import java.util.List;

import org.springframework.stereotype.Service;

import com.deliverybot.backend.dto.RobotCommandRequest;
import com.deliverybot.backend.model.RobotCommand;
import com.deliverybot.backend.repository.RobotCommandRepository;

@Service
public class RobotCommandService {

    private final RobotCommandRepository robotCommandRepository;

    public RobotCommandService(RobotCommandRepository robotCommandRepository) {
        this.robotCommandRepository = robotCommandRepository;
    }

    public List<RobotCommand> getAllCommands() {
        return robotCommandRepository.findAll();
    }

    public RobotCommand createCommand(RobotCommandRequest request) {
        RobotCommand command = new RobotCommand();
        command.setCommand(request.getCommand());
        command.setStatus("Sent");

        return robotCommandRepository.save(command);
    }
}