package com.deliverybot.backend.config;

import java.util.List;

import org.springframework.boot.CommandLineRunner;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Component;

import com.deliverybot.backend.model.AppUser;
import com.deliverybot.backend.model.Product;
import com.deliverybot.backend.model.UserRole;
import com.deliverybot.backend.repository.AppUserRepository;
import com.deliverybot.backend.repository.ProductRepository;

@Component
public class DataInitializer implements CommandLineRunner {

    private final AppUserRepository appUserRepository;
    private final ProductRepository productRepository;
    private final BCryptPasswordEncoder passwordEncoder;
    private final JdbcTemplate jdbcTemplate;

    public DataInitializer(
            AppUserRepository appUserRepository,
            ProductRepository productRepository,
            BCryptPasswordEncoder passwordEncoder,
            JdbcTemplate jdbcTemplate
    ) {
        this.appUserRepository = appUserRepository;
        this.productRepository = productRepository;
        this.passwordEncoder = passwordEncoder;
        this.jdbcTemplate = jdbcTemplate;
    }

    @Override
    public void run(String... args) {
        widenRoleColumn();
        useUtf8mb4("products", "order_items", "delivery_orders", "users");
        createUserIfMissing("Default", "Admin", "admin@deliverybot.com", "admin123", UserRole.ADMIN);
        createUserIfMissing("Robot", "Operator", "operator@deliverybot.com", "operator123", UserRole.OPERATOR);
        makeSeedOperatorAnOperator();
        seedProducts();
    }

    /**
     * reset_database.sh used to create operator@deliverybot.com as an ADMIN, before
     * the OPERATOR role existed. Give that account the operator role, as long as
     * there is no operator yet and another admin remains.
     */
    private void makeSeedOperatorAnOperator() {
        if (appUserRepository.countByRole(UserRole.OPERATOR) > 0
                || appUserRepository.countByRole(UserRole.ADMIN) < 2) {
            return;
        }
        appUserRepository.findByEmail("operator@deliverybot.com").ifPresent(user -> {
            if (user.getRole() == UserRole.ADMIN) {
                user.setRole(UserRole.OPERATOR);
                appUserRepository.save(user);
                System.out.println("operator@deliverybot.com now has the OPERATOR role.");
            }
        });
    }

    /**
     * Hibernate created users.role as MySQL ENUM('USER','ADMIN'), and ddl-auto=update
     * never changes an existing column, so the new OPERATOR role would not fit.
     */
    private void widenRoleColumn() {
        try {
            jdbcTemplate.execute("ALTER TABLE users MODIFY role VARCHAR(20)");
        } catch (Exception e) {
            // not MySQL, or already done: nothing to do
        }
    }

    /**
     * Product icons are emoji and names/notes may be Turkish: the tables need
     * utf8mb4. A database created with an older default (latin1/utf8mb3) gets
     * its tables converted once.
     */
    private void useUtf8mb4(String... tables) {
        for (String table : tables) {
            try {
                String collation = jdbcTemplate.queryForObject(
                        "SELECT TABLE_COLLATION FROM information_schema.TABLES "
                                + "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ?",
                        String.class, table);
                if (collation != null && !collation.startsWith("utf8mb4")) {
                    jdbcTemplate.execute("ALTER TABLE " + table
                            + " CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");
                    System.out.println("Table " + table + " converted to utf8mb4.");
                }
            } catch (Exception e) {
                // not MySQL / table missing: nothing to do
            }
        }
    }

    private void createUserIfMissing(String name, String surname, String email, String password, UserRole role) {
        if (appUserRepository.existsByEmail(email)) {
            return;
        }
        AppUser user = new AppUser();
        user.setName(name);
        user.setSurname(surname);
        user.setEmail(email);
        user.setPassword(passwordEncoder.encode(password));
        user.setRole(role);
        appUserRepository.save(user);
        System.out.println("Created " + role + " user: " + email + " / " + password);
    }

    private void seedProducts() {
        if (productRepository.count() > 0) {
            return;
        }
        productRepository.saveAll(List.of(
                new Product("Caffe Latte", "Espresso with steamed milk", "Hot Drinks", 85.0, "☕"),
                new Product("Americano", "Espresso with hot water", "Hot Drinks", 70.0, "☕"),
                new Product("Turkish Tea", "Freshly brewed black tea", "Hot Drinks", 25.0, "🍵"),
                new Product("Iced Mocha", "Chocolate, espresso, milk and ice", "Cold Drinks", 95.0, "🧋"),
                new Product("Lemonade", "Homemade lemonade", "Cold Drinks", 55.0, "🍋"),
                new Product("Water", "500 ml bottled water", "Cold Drinks", 15.0, "💧"),
                new Product("Chicken Sandwich", "Grilled chicken, lettuce, tomato", "Food", 140.0, "🥪"),
                new Product("Simit", "Sesame bagel", "Food", 30.0, "🥯"),
                new Product("Chocolate Cookie", "Fresh baked cookie", "Snacks", 40.0, "🍪"),
                new Product("Fruit Cup", "Seasonal fruit", "Snacks", 60.0, "🍓")
        ));
        System.out.println("Sample products created.");
    }
}
