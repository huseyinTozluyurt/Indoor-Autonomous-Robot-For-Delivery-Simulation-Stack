package com.deliverybot.backend.repository;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import com.deliverybot.backend.model.AppUser;
import com.deliverybot.backend.model.UserRole;

public interface AppUserRepository extends JpaRepository<AppUser, Long> {

    Optional<AppUser> findByEmail(String email);

    boolean existsByEmail(String email);

    long countByRole(UserRole role);
}