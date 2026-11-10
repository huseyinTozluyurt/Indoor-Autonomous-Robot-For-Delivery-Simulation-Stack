package com.deliverybot.backend.repository;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

import com.deliverybot.backend.model.Product;

public interface ProductRepository extends JpaRepository<Product, Long> {

    List<Product> findByAvailableTrueOrderByCategoryAscNameAsc();
}
