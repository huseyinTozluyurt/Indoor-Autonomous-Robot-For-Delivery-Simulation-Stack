package com.deliverybot.backend.repository;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;

import com.deliverybot.backend.model.OrderRecord;

public interface OrderRecordRepository extends JpaRepository<OrderRecord, Long> {

    List<OrderRecord> findByUserIdOrderByIdDesc(Long userId);

    List<OrderRecord> findByStatusInOrderByIdAsc(List<String> statuses);

    /** All orders with this order code (the "Order ID" typed by the user), newest first. */
    @Query("select o from OrderRecord o where o.orderID = :code order by o.id desc")
    List<OrderRecord> findByOrderCode(@Param("code") String code);

    /**
     * Stores the robot's answer to a dispatch without touching the status, so a
     * "Delivering" report that arrived in the meantime is not overwritten.
     */
    @Transactional
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("update OrderRecord o set o.deliveryPoint = :point, "
            + "o.robotMessage = case when o.status = 'Dispatched' then :message else o.robotMessage end "
            + "where o.id = :id")
    int saveDispatchAnswer(@Param("id") Long id, @Param("point") String point,
                           @Param("message") String message);
}
