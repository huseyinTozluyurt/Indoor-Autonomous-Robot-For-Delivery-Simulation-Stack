package com.deliverybot.backend.dto;

import java.time.LocalDateTime;

import com.deliverybot.backend.model.AppUser;

public class UserResponse {

    private Long id;
    private String name;
    private String surname;
    private Integer age;
    private String email;
    private String phone;
    private String role;
    private LocalDateTime createdAt;

    public UserResponse(AppUser user) {
        this.id = user.getId();
        this.name = user.getName();
        this.surname = user.getSurname();
        this.age = user.getAge();
        this.email = user.getEmail();
        this.phone = user.getPhone();
        this.role = user.getRole().name();
        this.createdAt = user.getCreatedAt();
    }

    public Long getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public String getSurname() {
        return surname;
    }

    public Integer getAge() {
        return age;
    }

    public String getEmail() {
        return email;
    }

    public String getPhone() {
        return phone;
    }

    public String getRole() {
        return role;
    }

    public LocalDateTime getCreatedAt() {
        return createdAt;
    }
}