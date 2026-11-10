package com.deliverybot.backend.service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import com.deliverybot.backend.dto.DeliveryCommandRequest;
import com.deliverybot.backend.dto.OrderRequest;
import com.deliverybot.backend.dto.PlaceOrderRequest;
import com.deliverybot.backend.dto.RobotStatusUpdateRequest;
import com.deliverybot.backend.model.AppUser;
import com.deliverybot.backend.model.OrderItem;
import com.deliverybot.backend.model.OrderRecord;
import com.deliverybot.backend.model.Product;
import com.deliverybot.backend.repository.AppUserRepository;
import com.deliverybot.backend.repository.OrderRecordRepository;
import com.deliverybot.backend.repository.ProductRepository;

@Service
public class OrderService {

    private final OrderRecordRepository orderRecordRepository;
    private final RaspberryPiService raspberryPiService;
    private final ProductRepository productRepository;
    private final AppUserRepository appUserRepository;
    private final boolean autoDispatch;

    /** Orders the operator can still put into the robot. */
    public static final List<String> WAITING = List.of("Preparing", "Pending", "Failed", "Cancelled");

    public OrderService(
            OrderRecordRepository orderRecordRepository,
            RaspberryPiService raspberryPiService,
            ProductRepository productRepository,
            AppUserRepository appUserRepository,
            @Value("${robot.auto-dispatch:false}") boolean autoDispatch
    ) {
        this.orderRecordRepository = orderRecordRepository;
        this.raspberryPiService = raspberryPiService;
        this.productRepository = productRepository;
        this.appUserRepository = appUserRepository;
        this.autoDispatch = autoDispatch;
    }

    public List<OrderRecord> getOrdersOfUser(Long userId) {
        return orderRecordRepository.findByUserIdOrderByIdDesc(userId);
    }

    /**
     * A user orders products to a delivery point of the campus map. The order
     * stays "Preparing" until the operator loads it into the robot and starts
     * the delivery ({@link #dispatchBatch(List)}).
     */
    public OrderRecord placeOrder(PlaceOrderRequest request) {
        if (request.getUserId() == null) {
            throw new IllegalArgumentException("Please log in before ordering");
        }
        AppUser user = appUserRepository.findById(request.getUserId())
                .orElseThrow(() -> new IllegalArgumentException("User not found: " + request.getUserId()));
        String point = request.getDeliveryPoint() == null ? "" : request.getDeliveryPoint().trim();
        if (point.isEmpty() && request.getArucoId() == null) {
            throw new IllegalArgumentException("Choose a delivery point on the map");
        }
        if (request.getItems() == null || request.getItems().isEmpty()) {
            throw new IllegalArgumentException("The cart is empty");
        }

        OrderRecord order = new OrderRecord();
        order.setUserId(user.getId());
        String name = ((user.getName() == null ? "" : user.getName()) + " "
                + (user.getSurname() == null ? "" : user.getSurname())).trim();
        order.setCustomerName(name.isEmpty() ? user.getEmail() : name);
        order.setCustomerEmail(user.getEmail());
        order.setDeliveryPoint(point.isEmpty() ? null : point);
        order.setRoute(point.isEmpty() ? null : point);
        order.setArucoId(request.getArucoId());
        order.setNote(request.getNote());
        order.setStatus("Preparing");

        double total = 0;
        Map<Long, Integer> merged = new LinkedHashMap<>();
        for (PlaceOrderRequest.Item it : request.getItems()) {
            if (it.getProductId() == null) {
                continue;
            }
            int q = it.getQuantity() == null ? 1 : it.getQuantity();
            if (q <= 0) {
                continue;
            }
            merged.merge(it.getProductId(), q, Integer::sum);
        }
        if (merged.isEmpty()) {
            throw new IllegalArgumentException("The cart is empty");
        }
        for (Map.Entry<Long, Integer> e : merged.entrySet()) {
            Product product = productRepository.findById(e.getKey())
                    .orElseThrow(() -> new IllegalArgumentException("Product not found: " + e.getKey()));
            if (Boolean.FALSE.equals(product.getAvailable())) {
                throw new IllegalArgumentException(product.getName() + " is not available now");
            }
            int q = Math.min(e.getValue(), 20);
            OrderItem item = new OrderItem();
            item.setProductId(product.getId());
            item.setProductName(product.getName());
            item.setUnitPrice(product.getPrice());
            item.setQuantity(q);
            order.addItem(item);
            total += (product.getPrice() == null ? 0 : product.getPrice()) * q;
        }
        order.setTotalPrice(Math.round(total * 100) / 100.0);
        order.setRobotMessage("Waiting for the operator to load the robot");

        OrderRecord saved = orderRecordRepository.save(order);
        saved.setOrderID("ORD-" + saved.getId());
        return orderRecordRepository.save(saved);
    }

    /**
     * The operator put these orders into the robot and pressed "Start delivery":
     * they are sent as ONE mission, the robot plans the shortest tour (Dijkstra
     * between the points, best order of the points) and reports every order back.
     */
    public Map<String, Object> dispatchBatch(List<Long> orderIds) {
        if (orderIds == null || orderIds.isEmpty()) {
            throw new IllegalArgumentException("Select at least one order");
        }
        List<OrderRecord> orders = new ArrayList<>();
        for (Long id : orderIds) {
            OrderRecord o = orderRecordRepository.findById(id)
                    .orElseThrow(() -> new IllegalArgumentException("Order not found: " + id));
            if (!WAITING.contains(o.getStatus())) {
                throw new IllegalArgumentException("Order " + o.getOrderID() + " is already " + o.getStatus());
            }
            orders.add(o);
        }

        List<Map<String, Object>> missionOrders = new ArrayList<>();
        Map<Long, String> previous = new HashMap<>();
        for (OrderRecord o : orders) {
            Map<String, Object> m = new HashMap<>();
            m.put("orderID", o.getOrderID() != null ? o.getOrderID() : "ORD-" + o.getId());
            m.put("orderDbId", o.getId());
            if (o.getDeliveryPoint() != null && !o.getDeliveryPoint().isBlank()) {
                m.put("deliveryPoint", o.getDeliveryPoint());
            }
            m.put("route", o.getRoute());
            m.put("targetArucoId", o.getArucoId());
            m.put("tableNumber", o.getTableNumber());
            missionOrders.add(m);
            previous.put(o.getId(), o.getStatus());
            // before sending: the robot reports quickly and must not be overwritten
            o.setStatus("Delivering");
            o.setRobotMessage("Loaded on the robot; planning the route");
            orderRecordRepository.save(o);
        }

        Map<String, Object> robotResponse;
        try {
            robotResponse = raspberryPiService.sendMission(Map.of("orders", missionOrders));
        } catch (RuntimeException e) {
            for (OrderRecord o : orders) {
                orderRecordRepository.findById(o.getId()).ifPresent(cur -> {
                    cur.setStatus(previous.get(o.getId()));
                    cur.setRobotMessage("Could not start the delivery: " + e.getMessage());
                    orderRecordRepository.save(cur);
                });
            }
            throw e;
        }

        Map<String, Object> result = new HashMap<>();
        result.put("orders", orderRecordRepository.findAllById(orderIds));
        result.put("robotResponse", robotResponse);
        return result;
    }

    public List<OrderRecord> getAllOrders() {
        return orderRecordRepository.findAll();
    }

    public OrderRecord createOrder(OrderRequest request) {
        OrderRecord order = new OrderRecord();

        order.setOrderID(request.getOrderID());
        order.setTableNumber(request.getTableNumber());
        order.setRowNumber(request.getRowNumber());
        order.setColumnNumber(request.getColumnNumber());
        order.setArucoId(request.getArucoId());
        order.setRoute(request.getRoute());
        order.setStatus(request.getStatus() != null ? request.getStatus() : "Pending");

        OrderRecord saved = orderRecordRepository.save(order);

        if (autoDispatch) {
            try {
                dispatchOrder(saved.getId());
                return orderRecordRepository.findById(saved.getId()).orElse(saved);
            } catch (RuntimeException e) {
                // The order stays Pending; the admin can send it again from View Orders.
                saved.setRobotMessage("Auto dispatch failed: " + e.getMessage());
                return orderRecordRepository.save(saved);
            }
        }
        return saved;
    }

    public OrderRecord updateStatus(Long id, String status) {
        OrderRecord order = orderRecordRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Order not found with id: " + id));

        order.setStatus(status);

        return orderRecordRepository.save(order);
    }

    /**
     * Sends the order to the robot (Raspberry Pi or the Gazebo simulation bridge).
     * The robot then reports Delivering / Delivered / Failed back through
     * {@link #updateFromRobot(RobotStatusUpdateRequest)}.
     */
    public Map<String, Object> dispatchOrder(Long id) {
        OrderRecord order = orderRecordRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Order not found with id: " + id));

        DeliveryCommandRequest command = new DeliveryCommandRequest();
        command.setOrderID(order.getOrderID());
        command.setOrderDbId(order.getId());
        command.setTableNumber(order.getTableNumber());
        command.setTargetArucoId(order.getArucoId());
        command.setRoute(order.getDeliveryPoint() != null && !order.getDeliveryPoint().isBlank()
                ? order.getDeliveryPoint() : order.getRoute());

        // Mark it before sending: the robot may report "Delivering" within a second,
        // and that report must not be overwritten afterwards.
        String previousStatus = order.getStatus();
        order.setStatus("Dispatched");
        orderRecordRepository.save(order);

        Map<String, Object> robotResponse;
        try {
            robotResponse = raspberryPiService.sendDeliveryCommand(command);
        } catch (RuntimeException e) {
            order.setStatus(previousStatus);
            orderRecordRepository.save(order);
            throw e;
        }

        if (robotResponse != null) {
            Object point = robotResponse.get("deliveryPoint");
            Object message = robotResponse.get("message");
            orderRecordRepository.saveDispatchAnswer(id,
                    point != null ? point.toString() : null,
                    message != null ? message.toString() : null);
        }
        OrderRecord saved = orderRecordRepository.findById(id).orElse(order);

        Map<String, Object> result = new HashMap<>();
        result.put("order", saved);
        result.put("robotResponse", robotResponse);
        return result;
    }

    public void setRobotMessage(Long id, String message) {
        orderRecordRepository.findById(id).ifPresent(order -> {
            order.setRobotMessage(message.length() > 1000 ? message.substring(0, 1000) : message);
            orderRecordRepository.save(order);
        });
    }

    /** Status report from the robot: matches the order by database id, else by order code. */
    public OrderRecord updateFromRobot(RobotStatusUpdateRequest request) {
        OrderRecord order = null;

        if (request.getId() != null) {
            order = orderRecordRepository.findById(request.getId()).orElse(null);
        }
        if (order == null && request.getOrderID() != null) {
            List<OrderRecord> matches = orderRecordRepository.findByOrderCode(request.getOrderID());
            order = matches.isEmpty() ? null : matches.get(0);
        }
        if (order == null) {
            throw new RuntimeException("Order not found: id=" + request.getId()
                    + ", orderID=" + request.getOrderID());
        }

        if (request.getStatus() != null && !request.getStatus().isBlank()) {
            order.setStatus(request.getStatus());
        }
        if (request.getMessage() != null) {
            String message = request.getMessage();
            order.setRobotMessage(message.length() > 1000 ? message.substring(0, 1000) : message);
        }
        if (request.getDeliveryPoint() != null) {
            order.setDeliveryPoint(request.getDeliveryPoint());
        }
        return orderRecordRepository.save(order);
    }

    public void deleteOrder(Long id) {
        orderRecordRepository.deleteById(id);
    }

    public void deleteAllOrders() {
        orderRecordRepository.deleteAll();
    }
}
