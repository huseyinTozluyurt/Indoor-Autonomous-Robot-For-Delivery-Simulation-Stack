package com.deliverybot.backend.repository;

import org.springframework.data.jpa.repository.JpaRepository;

import com.deliverybot.backend.model.TableRecord;

public interface TableRecordRepository extends JpaRepository<TableRecord, Long> {
}