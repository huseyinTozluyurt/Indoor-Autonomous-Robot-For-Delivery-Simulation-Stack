package com.deliverybot.backend.dto;

import java.util.List;

public class MapConfigRequest {

    private String mapName;
    private String description;
    private Integer rowsCount;
    private Integer columnsCount;
    private Boolean active;
    private List<TableRequest> tables;

    public String getMapName() {
        return mapName;
    }

    public void setMapName(String mapName) {
        this.mapName = mapName;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public Integer getRowsCount() {
        return rowsCount;
    }

    public void setRowsCount(Integer rowsCount) {
        this.rowsCount = rowsCount;
    }

    public Integer getColumnsCount() {
        return columnsCount;
    }

    public void setColumnsCount(Integer columnsCount) {
        this.columnsCount = columnsCount;
    }

    public Boolean getActive() {
        return active;
    }

    public void setActive(Boolean active) {
        this.active = active;
    }

    public List<TableRequest> getTables() {
        return tables;
    }

    public void setTables(List<TableRequest> tables) {
        this.tables = tables;
    }
}