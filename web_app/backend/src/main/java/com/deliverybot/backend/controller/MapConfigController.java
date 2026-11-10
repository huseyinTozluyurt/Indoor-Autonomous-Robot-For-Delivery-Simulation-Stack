package com.deliverybot.backend.controller;

import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.deliverybot.backend.dto.MapConfigRequest;
import com.deliverybot.backend.model.MapConfig;
import com.deliverybot.backend.service.MapConfigService;

@RestController
@RequestMapping("/api/maps")
public class MapConfigController {

    private final MapConfigService mapConfigService;

    public MapConfigController(MapConfigService mapConfigService) {
        this.mapConfigService = mapConfigService;
    }

    @GetMapping
    public List<MapConfig> getAllMaps() {
        return mapConfigService.getAllMaps();
    }

    @GetMapping("/active")
    public ResponseEntity<MapConfig> getActiveMap() {
        MapConfig activeMap = mapConfigService.getActiveMap();

        if (activeMap == null) {
            return ResponseEntity.notFound().build();
        }

        return ResponseEntity.ok(activeMap);
    }

    @GetMapping("/{id}")
    public MapConfig getMapById(@PathVariable Long id) {
        return mapConfigService.getMapById(id);
    }

    @PostMapping
    public MapConfig createMap(@RequestBody MapConfigRequest request) {
        return mapConfigService.createMap(request);
    }

    @PutMapping("/{id}")
    public MapConfig updateMap(
            @PathVariable Long id,
            @RequestBody MapConfigRequest request
    ) {
        return mapConfigService.updateMap(id, request);
    }

    @PutMapping("/{id}/activate")
    public MapConfig activateMap(@PathVariable Long id) {
        return mapConfigService.activateMap(id);
    }

    @DeleteMapping("/{id}")
    public void deleteMap(@PathVariable Long id) {
        mapConfigService.deleteMap(id);
    }
}