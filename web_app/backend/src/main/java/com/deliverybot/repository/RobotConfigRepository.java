package com.deliverybot.backend.repository;

import org.springframework.data.jpa.repository.JpaRepository;

import com.deliverybot.backend.model.RobotConfig;

public interface RobotConfigRepository extends JpaRepository<RobotConfig, Long> {
}