package com.deliverybot.backend.service;

import java.util.List;

import org.springframework.stereotype.Service;

import com.deliverybot.backend.dto.SensorLogRequest;
import com.deliverybot.backend.model.SensorLog;
import com.deliverybot.backend.repository.SensorLogRepository;

@Service
public class SensorService {

    private final SensorLogRepository sensorLogRepository;

    public SensorService(SensorLogRepository sensorLogRepository) {
        this.sensorLogRepository = sensorLogRepository;
    }

    public List<SensorLog> getAllLogs() {
        return sensorLogRepository.findAll();
    }

    public SensorLog getLatestLog() {
        return sensorLogRepository.findTopByOrderByCreatedAtDesc().orElse(null);
    }

    public SensorLog createLog(SensorLogRequest request) {
        SensorLog log = new SensorLog();

        log.setFrontDistance(request.getFrontDistance());
        log.setLeftDistance(request.getLeftDistance());
        log.setRightDistance(request.getRightDistance());
        log.setBackDistance(request.getBackDistance());
        log.setErrorCode(request.getErrorCode());

        return sensorLogRepository.save(log);
    }
}