package com.deliverybot.backend.dto;

import java.util.ArrayList;
import java.util.List;

/** The orders the operator put into the robot: {"orderIds": [4, 7, 9]} */
public class BatchDispatchRequest {

    private List<Long> orderIds = new ArrayList<>();

    public List<Long> getOrderIds() {
        return orderIds;
    }

    public void setOrderIds(List<Long> orderIds) {
        this.orderIds = orderIds;
    }
}
