package com.deliverybot.backend.dto;

public class DeliveryCommandRequest {

    private String orderID;
    private Integer tableNumber;
    private Integer targetArucoId;
    private String route;
    // Database id of the order, so the robot can report status back for exactly this order
    private Long orderDbId;

    public Long getOrderDbId() {
        return orderDbId;
    }

    public void setOrderDbId(Long orderDbId) {
        this.orderDbId = orderDbId;
    }

    public String getOrderID() {
        return orderID;
    }

    public void setOrderID(String orderID) {
        this.orderID = orderID;
    }

    public Integer getTableNumber() {
        return tableNumber;
    }

    public void setTableNumber(Integer tableNumber) {
        this.tableNumber = tableNumber;
    }

    public Integer getTargetArucoId() {
        return targetArucoId;
    }

    public void setTargetArucoId(Integer targetArucoId) {
        this.targetArucoId = targetArucoId;
    }

    public String getRoute() {
        return route;
    }

    public void setRoute(String route) {
        this.route = route;
    }
}