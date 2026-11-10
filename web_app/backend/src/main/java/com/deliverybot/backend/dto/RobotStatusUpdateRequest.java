package com.deliverybot.backend.dto;

/**
 * Sent by the robot (or the Gazebo simulation bridge) when a delivery changes state.
 * Example: {"orderID": "1001", "status": "Delivered", "message": "Delivered at r_delivery_point_1",
 *           "deliveryPoint": "r_delivery_point_1"}
 */
public class RobotStatusUpdateRequest {

    private Long id;
    private String orderID;
    private String status;
    private String message;
    private String deliveryPoint;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getOrderID() {
        return orderID;
    }

    public void setOrderID(String orderID) {
        this.orderID = orderID;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public String getDeliveryPoint() {
        return deliveryPoint;
    }

    public void setDeliveryPoint(String deliveryPoint) {
        this.deliveryPoint = deliveryPoint;
    }
}
