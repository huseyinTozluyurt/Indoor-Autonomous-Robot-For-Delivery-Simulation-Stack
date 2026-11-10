package com.deliverybot.backend.service;

import java.util.List;

import org.springframework.stereotype.Service;

import com.deliverybot.backend.dto.RobotConfigRequest;
import com.deliverybot.backend.dto.RobotConfigResponse;
import com.deliverybot.backend.model.RobotConfig;
import com.deliverybot.backend.repository.RobotConfigRepository;

@Service
public class RobotConfigService {

    private final RobotConfigRepository robotConfigRepository;

    public RobotConfigService(RobotConfigRepository robotConfigRepository) {
        this.robotConfigRepository = robotConfigRepository;
    }

    public RobotConfigResponse getConfig() {
        RobotConfig config = getOrCreateDefaultConfig();

        return new RobotConfigResponse(
                config.getId(),
                config.getRaspberryPiIp(),
                config.getRaspberryPiPort(),
                config.getBaseUrl()
        );
    }

    public RobotConfigResponse updateConfig(RobotConfigRequest request) {
        RobotConfig config = getOrCreateDefaultConfig();

        String ip = request.getRaspberryPiIp();
        Integer port = request.getRaspberryPiPort();

        if (ip == null || ip.isBlank()) {
            throw new RuntimeException("Raspberry Pi IP address is required");
        }

        if (port == null || port <= 0) {
            port = 5000;
        }

        String baseUrl = "http://" + ip + ":" + port;

        config.setRaspberryPiIp(ip);
        config.setRaspberryPiPort(port);
        config.setBaseUrl(baseUrl);

        RobotConfig saved = robotConfigRepository.save(config);

        return new RobotConfigResponse(
                saved.getId(),
                saved.getRaspberryPiIp(),
                saved.getRaspberryPiPort(),
                saved.getBaseUrl()
        );
    }

    public String getRaspberryPiBaseUrl() {
        RobotConfig config = getOrCreateDefaultConfig();
        return config.getBaseUrl();
    }

    private RobotConfig getOrCreateDefaultConfig() {
        List<RobotConfig> configs = robotConfigRepository.findAll();

        if (!configs.isEmpty()) {
            return configs.get(0);
        }

        RobotConfig defaultConfig = new RobotConfig();
        defaultConfig.setRaspberryPiIp("192.168.1.113");
        defaultConfig.setRaspberryPiPort(5000);
        defaultConfig.setBaseUrl("http://192.168.1.113:5000");

        return robotConfigRepository.save(defaultConfig);
    }
}