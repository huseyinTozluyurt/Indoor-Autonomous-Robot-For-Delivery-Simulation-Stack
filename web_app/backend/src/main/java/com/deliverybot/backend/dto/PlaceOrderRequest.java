package com.deliverybot.backend.dto;

import java.util.ArrayList;
import java.util.List;

/**
 * A product order from the shop page:
 * {"userId": 3, "deliveryPoint": "a_delivery_point_2", "arucoId": 41, "note": "",
 *  "items": [{"productId": 1, "quantity": 2}]}
 */
public class PlaceOrderRequest {

    private Long userId;
    private String deliveryPoint;
    private Integer arucoId;
    private String note;
    private List<Item> items = new ArrayList<>();

    public static class Item {
        private Long productId;
        private Integer quantity;

        public Long getProductId() {
            return productId;
        }

        public void setProductId(Long productId) {
            this.productId = productId;
        }

        public Integer getQuantity() {
            return quantity;
        }

        public void setQuantity(Integer quantity) {
            this.quantity = quantity;
        }
    }

    public Long getUserId() {
        return userId;
    }

    public void setUserId(Long userId) {
        this.userId = userId;
    }

    public String getDeliveryPoint() {
        return deliveryPoint;
    }

    public void setDeliveryPoint(String deliveryPoint) {
        this.deliveryPoint = deliveryPoint;
    }

    public Integer getArucoId() {
        return arucoId;
    }

    public void setArucoId(Integer arucoId) {
        this.arucoId = arucoId;
    }

    public String getNote() {
        return note;
    }

    public void setNote(String note) {
        this.note = note;
    }

    public List<Item> getItems() {
        return items;
    }

    public void setItems(List<Item> items) {
        this.items = items;
    }
}
