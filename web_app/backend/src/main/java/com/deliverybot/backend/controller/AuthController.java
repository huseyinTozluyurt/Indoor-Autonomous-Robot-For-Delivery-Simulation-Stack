package com.deliverybot.backend.controller;

import com.deliverybot.backend.dto.LoginRequest;
import com.deliverybot.backend.dto.LoginResponse;
import com.deliverybot.backend.dto.RegisterRequest;
import com.deliverybot.backend.dto.RegisterResponse;
import com.deliverybot.backend.model.AppUser;
import com.deliverybot.backend.model.UserRole;
import com.deliverybot.backend.repository.AppUserRepository;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AppUserRepository appUserRepository;
    private final BCryptPasswordEncoder passwordEncoder;

    public AuthController(
            AppUserRepository appUserRepository,
            BCryptPasswordEncoder passwordEncoder
    ) {
        this.appUserRepository = appUserRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @PostMapping("/login")
    public LoginResponse login(@RequestBody LoginRequest request) {
        AppUser user = appUserRepository.findByEmail(request.getEmail())
                .orElseThrow(() -> new ResponseStatusException(
                        HttpStatus.UNAUTHORIZED,
                        "Invalid email or password"
                ));

        boolean passwordMatches = passwordEncoder.matches(
                request.getPassword(),
                user.getPassword()
        );

        if (!passwordMatches) {
            throw new ResponseStatusException(
                    HttpStatus.UNAUTHORIZED,
                    "Invalid email or password"
            );
        }

        return new LoginResponse(
                user.getId(),
                user.getName(),
                user.getSurname(),
                user.getEmail(),
                user.getRole().name()
        );
    }

    @PostMapping("/register")
    public RegisterResponse register(@RequestBody RegisterRequest request) {
        if (request.getName() == null || request.getName().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Name is required");
        }

        if (request.getSurname() == null || request.getSurname().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Surname is required");
        }

        if (request.getAge() == null || request.getAge() < 18) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "User must be at least 18");
        }

        if (request.getEmail() == null || request.getEmail().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Email is required");
        }

        if (request.getPassword() == null || request.getPassword().length() < 3) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Password is too short");
        }

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

        // Important: registered users are always normal USER accounts.
        user.setRole(UserRole.USER);

        AppUser savedUser = appUserRepository.save(user);

        return new RegisterResponse(
                savedUser.getId(),
                savedUser.getName(),
                savedUser.getSurname(),
                savedUser.getEmail(),
                savedUser.getRole().name()
        );
    }
}