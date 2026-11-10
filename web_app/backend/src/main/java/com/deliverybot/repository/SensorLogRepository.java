package com.deliverybot.backend.repository;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import com.deliverybot.backend.model.SensorLog;

public interface SensorLogRepository extends JpaRepository<SensorLog, Long> {

    Optional<SensorLog> findTopByOrderByCreatedAtDesc();
}