package com.deliverybot.backend.repository;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import com.deliverybot.backend.model.MapConfig;

public interface MapConfigRepository extends JpaRepository<MapConfig, Long> {

    Optional<MapConfig> findByActiveTrue();
}