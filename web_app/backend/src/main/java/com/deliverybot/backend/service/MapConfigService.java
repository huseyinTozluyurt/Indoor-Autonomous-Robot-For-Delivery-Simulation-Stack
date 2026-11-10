package com.deliverybot.backend.service;

import java.util.List;

import org.springframework.stereotype.Service;

import com.deliverybot.backend.dto.MapConfigRequest;
import com.deliverybot.backend.dto.TableRequest;
import com.deliverybot.backend.model.MapConfig;
import com.deliverybot.backend.model.TableRecord;
import com.deliverybot.backend.repository.MapConfigRepository;

@Service
public class MapConfigService {

    private final MapConfigRepository mapConfigRepository;

    public MapConfigService(MapConfigRepository mapConfigRepository) {
        this.mapConfigRepository = mapConfigRepository;
    }

    public List<MapConfig> getAllMaps() {
        return mapConfigRepository.findAll();
    }

    public MapConfig getMapById(Long id) {
        return mapConfigRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Map not found with id: " + id));
    }

    public MapConfig getActiveMap() {
        return mapConfigRepository.findByActiveTrue()
                .orElse(null);
    }

    public MapConfig createMap(MapConfigRequest request) {
        MapConfig mapConfig = new MapConfig();

        mapConfig.setMapName(request.getMapName());
        mapConfig.setDescription(request.getDescription());
        mapConfig.setRowsCount(request.getRowsCount());
        mapConfig.setColumnsCount(request.getColumnsCount());

        if (Boolean.TRUE.equals(request.getActive())) {
            deactivateAllMaps();
            mapConfig.setActive(true);
        } else {
            mapConfig.setActive(false);
        }

        mapConfig.getTables().clear();

        if (request.getTables() != null) {
            for (TableRequest tableRequest : request.getTables()) {
                TableRecord table = convertToTableRecord(tableRequest);
                table.setMapConfig(mapConfig);
                mapConfig.getTables().add(table);
            }
        }

        return mapConfigRepository.save(mapConfig);
    }

    public MapConfig updateMap(Long id, MapConfigRequest request) {
        MapConfig mapConfig = getMapById(id);

        mapConfig.setMapName(request.getMapName());
        mapConfig.setDescription(request.getDescription());
        mapConfig.setRowsCount(request.getRowsCount());
        mapConfig.setColumnsCount(request.getColumnsCount());

        if (Boolean.TRUE.equals(request.getActive())) {
            deactivateAllMaps();
            mapConfig.setActive(true);
        } else {
            mapConfig.setActive(false);
        }

        mapConfig.getTables().clear();

        if (request.getTables() != null) {
            for (TableRequest tableRequest : request.getTables()) {
                TableRecord table = convertToTableRecord(tableRequest);
                table.setMapConfig(mapConfig);
                mapConfig.getTables().add(table);
            }
        }

        return mapConfigRepository.save(mapConfig);
    }

    public MapConfig activateMap(Long id) {
        deactivateAllMaps();

        MapConfig mapConfig = getMapById(id);
        mapConfig.setActive(true);

        return mapConfigRepository.save(mapConfig);
    }

    public void deleteMap(Long id) {
        mapConfigRepository.deleteById(id);
    }

    private void deactivateAllMaps() {
        List<MapConfig> maps = mapConfigRepository.findAll();

        for (MapConfig map : maps) {
            map.setActive(false);
        }

        mapConfigRepository.saveAll(maps);
    }

    private TableRecord convertToTableRecord(TableRequest request) {
        TableRecord table = new TableRecord();

        table.setTableNumber(request.getTableNumber());
        table.setRowNumber(request.getRowNumber());
        table.setColumnNumber(request.getColumnNumber());
        table.setArucoId(request.getArucoId());
        table.setRoute(request.getRoute());

        if (request.getStatus() == null || request.getStatus().isBlank()) {
            table.setStatus("Available");
        } else {
            table.setStatus(request.getStatus());
        }

        table.setNotes(request.getNotes());

        return table;
    }
}