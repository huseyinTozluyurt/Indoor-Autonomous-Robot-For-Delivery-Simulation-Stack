package com.deliverybot.backend.repository;

import org.springframework.data.jpa.repository.JpaRepository;

import com.deliverybot.backend.model.RobotCommand;

public interface RobotCommandRepository extends JpaRepository<RobotCommand, Long> {
}