package com.deliverybot.backend.service;

import java.util.List;

import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import com.deliverybot.backend.dto.AdminUserRequest;
import com.deliverybot.backend.dto.UserResponse;
import com.deliverybot.backend.dto.UserRoleUpdateRequest;
import com.deliverybot.backend.model.AppUser;
import com.deliverybot.backend.model.UserRole;
import com.deliverybot.backend.repository.AppUserRepository;

@Service
public class AdminUserService {

    private final AppUserRepository appUserRepository;
    private final BCryptPasswordEncoder passwordEncoder;

    public AdminUserService(
            AppUserRepository appUserRepository,
            BCryptPasswordEncoder passwordEncoder
    ) {
        this.appUserRepository = appUserRepository;
        this.passwordEncoder = passwordEncoder;
    }

    public List<UserResponse> getAllUsers() {
        return appUserRepository.findAll()
                .stream()
                .map(UserResponse::new)
                .toList();
    }

    public UserResponse createUser(AdminUserRequest request) {
        validateCreateRequest(request);

        if (appUserRepository.existsByEmail(request.getEmail())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "Email already exists");
        }

        AppUser user = new AppUser();

        user.setName(request.getName());
        user.setSurname(request.getSurname());
        user.setAge(request.getAge());
        user.setEmail(request.getEmail());
        user.setPhone(request.getPhone());
        user.setPassword(passwordEncoder.encode(request.getPassword()));
        user.setRole(parseRole(request.getRole()));

        AppUser savedUser = appUserRepository.save(user);

        return new UserResponse(savedUser);
    }

    public UserResponse updateUserRole(Long id, UserRoleUpdateRequest request) {
        AppUser user = appUserRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.NOT_FOUND,
                        "User not found"
                ));

        UserRole newRole = parseRole(request.getRole());
        if (user.getRole() == UserRole.ADMIN && newRole != UserRole.ADMIN) {
            ensureAnotherAdminExists();
        }
        user.setRole(newRole);

        AppUser savedUser = appUserRepository.save(user);

        return new UserResponse(savedUser);
    }

    // Never leave the application without an admin account
    private void ensureAnotherAdminExists() {
        if (appUserRepository.countByRole(UserRole.ADMIN) <= 1) {
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                    "This is the last admin account; make another user admin first");
        }
    }

    public void deleteUser(Long id) {
        AppUser user = appUserRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.NOT_FOUND,
                        "User not found"
                ));

        if (user.getRole() == UserRole.ADMIN) {
            ensureAnotherAdminExists();
        }

        appUserRepository.delete(user);
    }

    private void validateCreateRequest(AdminUserRequest request) {
        if (request.getName() == null || request.getName().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Name is required");
        }

        if (request.getSurname() == null || request.getSurname().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Surname is required");
        }

        if (request.getEmail() == null || request.getEmail().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Email is required");
        }

        if (request.getPassword() == null || request.getPassword().length() < 3) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Password is too short");
        }
    }

    private UserRole parseRole(String role) {
        if (role == null || role.isBlank()) {
            return UserRole.USER;
        }

        try {
            return UserRole.valueOf(role.toUpperCase());
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid role");
        }
    }
}