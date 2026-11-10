package com.deliverybot.backend.controller;

import java.util.List;

import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.deliverybot.backend.dto.AdminUserRequest;
import com.deliverybot.backend.dto.UserResponse;
import com.deliverybot.backend.dto.UserRoleUpdateRequest;
import com.deliverybot.backend.service.AdminUserService;

@RestController
@RequestMapping("/api/admin/users")
public class AdminUserController {

    private final AdminUserService adminUserService;

    public AdminUserController(AdminUserService adminUserService) {
        this.adminUserService = adminUserService;
    }

    @GetMapping
    public List<UserResponse> getAllUsers() {
        return adminUserService.getAllUsers();
    }

    @PostMapping
    public UserResponse createUser(@RequestBody AdminUserRequest request) {
        return adminUserService.createUser(request);
    }

    @PutMapping("/{id}/role")
    public UserResponse updateUserRole(
            @PathVariable Long id,
            @RequestBody UserRoleUpdateRequest request
    ) {
        return adminUserService.updateUserRole(id, request);
    }

    @DeleteMapping("/{id}")
    public void deleteUser(@PathVariable Long id) {
        adminUserService.deleteUser(id);
    }
}