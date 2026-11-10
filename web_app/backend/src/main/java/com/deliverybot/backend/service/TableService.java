package com.deliverybot.backend.service;

import java.util.ArrayList;
import java.util.List;

import org.springframework.stereotype.Service;

import com.deliverybot.backend.dto.TableRequest;
import com.deliverybot.backend.model.TableRecord;
import com.deliverybot.backend.repository.TableRecordRepository;

@Service
public class TableService {

    private final TableRecordRepository tableRecordRepository;

    public TableService(TableRecordRepository tableRecordRepository) {
        this.tableRecordRepository = tableRecordRepository;
    }

    public List<TableRecord> getAllTables() {
        return tableRecordRepository.findAll();
    }

    public TableRecord createTable(TableRequest request) {
        TableRecord table = new TableRecord();

        table.setTableNumber(request.getTableNumber());
        table.setRowNumber(request.getRowNumber());
        table.setColumnNumber(request.getColumnNumber());
        table.setArucoId(request.getArucoId());
        table.setRoute(request.getRoute());
        table.setStatus(request.getStatus() != null ? request.getStatus() : "Available");
        table.setNotes(request.getNotes());

        return tableRecordRepository.save(table);
    }

    public List<TableRecord> saveAllTables(List<TableRequest> requests) {
        tableRecordRepository.deleteAll();

        List<TableRecord> tables = new ArrayList<>();

        for (TableRequest request : requests) {
            TableRecord table = new TableRecord();

            table.setTableNumber(request.getTableNumber());
            table.setRowNumber(request.getRowNumber());
            table.setColumnNumber(request.getColumnNumber());
            table.setArucoId(request.getArucoId());
            table.setRoute(request.getRoute());
            table.setStatus(request.getStatus() != null ? request.getStatus() : "Available");
            table.setNotes(request.getNotes());

            tables.add(table);
        }

        return tableRecordRepository.saveAll(tables);
    }

    public TableRecord updateTable(Long id, TableRequest request) {
        TableRecord table = tableRecordRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Table not found with id: " + id));

        table.setTableNumber(request.getTableNumber());
        table.setRowNumber(request.getRowNumber());
        table.setColumnNumber(request.getColumnNumber());
        table.setArucoId(request.getArucoId());
        table.setRoute(request.getRoute());
        table.setStatus(request.getStatus());
        table.setNotes(request.getNotes());

        return tableRecordRepository.save(table);
    }

    public void deleteTable(Long id) {
        tableRecordRepository.deleteById(id);
    }

    public void deleteAllTables() {
        tableRecordRepository.deleteAll();
    }
}