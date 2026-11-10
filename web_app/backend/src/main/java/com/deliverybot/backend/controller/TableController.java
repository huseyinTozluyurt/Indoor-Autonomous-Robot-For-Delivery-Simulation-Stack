package com.deliverybot.backend.controller;

import java.util.List;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.deliverybot.backend.dto.TableRequest;
import com.deliverybot.backend.model.TableRecord;
import com.deliverybot.backend.service.TableService;

@RestController
@RequestMapping("/api/tables")
public class TableController {

    private final TableService tableService;

    public TableController(TableService tableService) {
        this.tableService = tableService;
    }

    @GetMapping
    public List<TableRecord> getAllTables() {
        return tableService.getAllTables();
    }

    @PostMapping
    public TableRecord createTable(@RequestBody TableRequest request) {
        return tableService.createTable(request);
    }

    @PostMapping("/bulk")
    public List<TableRecord> saveAllTables(@RequestBody List<TableRequest> requests) {
        return tableService.saveAllTables(requests);
    }

    @PutMapping("/{id}")
    public TableRecord updateTable(
            @PathVariable Long id,
            @RequestBody TableRequest request
    ) {
        return tableService.updateTable(id, request);
    }

    @DeleteMapping("/{id}")
    public void deleteTable(@PathVariable Long id) {
        tableService.deleteTable(id);
    }

    @DeleteMapping
    public void deleteAllTables() {
        tableService.deleteAllTables();
    }
}