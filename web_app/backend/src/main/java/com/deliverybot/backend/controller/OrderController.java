package com.deliverybot.backend.controller;

import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.server.ResponseStatusException;

import com.deliverybot.backend.dto.BatchDispatchRequest;
import com.deliverybot.backend.dto.OrderRequest;
import com.deliverybot.backend.dto.PlaceOrderRequest;
import com.deliverybot.backend.dto.RobotStatusUpdateRequest;
import com.deliverybot.backend.dto.StatusUpdateRequest;
import com.deliverybot.backend.model.OrderRecord;
import com.deliverybot.backend.service.OrderService;

@RestController
@RequestMapping("/api/orders")
public class OrderController {

    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    @GetMapping
    public List<OrderRecord> getAllOrders() {
        return orderService.getAllOrders();
    }

    @PostMapping
    public OrderRecord createOrder(@RequestBody OrderRequest request) {
        return orderService.createOrder(request);
    }

    /** A user orders products from the shop page; the order starts as "Preparing". */
    @PostMapping("/place")
    public OrderRecord placeOrder(@RequestBody PlaceOrderRequest request) {
        try {
            return orderService.placeOrder(request);
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, e.getMessage(), e);
        }
    }

    /** The orders of one user, newest first ("My Orders"). */
    @GetMapping("/user/{userId}")
    public List<OrderRecord> ordersOfUser(@PathVariable Long userId) {
        return orderService.getOrdersOfUser(userId);
    }

    /** The operator loaded these orders into the robot: deliver them as one shortest tour. */
    @PostMapping("/dispatch-batch")
    public ResponseEntity<Map<String, Object>> dispatchBatch(@RequestBody BatchDispatchRequest request) {
        try {
            return ResponseEntity.ok(orderService.dispatchBatch(request.getOrderIds()));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage(), "message", e.getMessage()));
        } catch (RestClientResponseException e) {
            String reason = e.getResponseBodyAsString();
            try {
                reason = new ObjectMapper().readTree(reason).path("error").asText(reason);
            } catch (Exception ignored) {
                // not JSON: keep the raw text
            }
            String msg = "Robot rejected the delivery: " + reason;
            return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Map.of("error", msg, "message", msg));
        } catch (RestClientException e) {
            String msg = "Robot server not reachable: " + e.getMessage();
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(Map.of("error", msg, "message", msg));
        }
    }

    @PutMapping("/{id}/status")
    public OrderRecord updateOrderStatus(
            @PathVariable Long id,
            @RequestBody StatusUpdateRequest request
    ) {
        return orderService.updateStatus(id, request.getStatus());
    }

    /** Send this order to the robot / Gazebo simulation. */
    @PostMapping("/{id}/dispatch")
    public ResponseEntity<Map<String, Object>> dispatchOrder(@PathVariable Long id) {
        try {
            return ResponseEntity.ok(orderService.dispatchOrder(id));
        } catch (RestClientResponseException e) {
            // The robot answered with an error, e.g. no delivery point for this ArUco ID
            String reason = e.getResponseBodyAsString();
            try {
                reason = new ObjectMapper().readTree(reason).path("error").asText(reason);
            } catch (Exception ignored) {
                // not JSON: keep the raw text
            }
            orderService.setRobotMessage(id, "Robot rejected the order: " + reason);
            return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                    .body(Map.of("error", "Robot rejected the order", "robotResponse", reason));
        } catch (RestClientException e) {
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                    .body(Map.of("error", "Robot server not reachable: " + e.getMessage()));
        } catch (RuntimeException e) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", e.getMessage()));
        }
    }

    /** Called by the robot / simulation bridge when a delivery changes state. */
    @PostMapping("/robot-status")
    public OrderRecord robotStatus(@RequestBody RobotStatusUpdateRequest request) {
        try {
            return orderService.updateFromRobot(request);
        } catch (RuntimeException e) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, e.getMessage(), e);
        }
    }

    @DeleteMapping("/{id}")
    public void deleteOrder(@PathVariable Long id) {
        orderService.deleteOrder(id);
    }

    @DeleteMapping
    public void deleteAllOrders() {
        orderService.deleteAllOrders();
    }
}
