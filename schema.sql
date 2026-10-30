CREATE DATABASE IF NOT EXISTS inventory_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE inventory_db;

CREATE TABLE IF NOT EXISTS products (
    product_id    INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    product_code  VARCHAR(50)   NOT NULL,
    product_name  VARCHAR(150)  NOT NULL,
    description   TEXT          NULL,
    category      VARCHAR(100)  NOT NULL,
    price         DECIMAL(12,2) NOT NULL,
    quantity      INT           NOT NULL DEFAULT 0,
    supplier_name VARCHAR(150)  NOT NULL,
    is_active     TINYINT(1)    NOT NULL DEFAULT 1,
    created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id),
    UNIQUE KEY uq_products_code (product_code),
    KEY ix_products_category (category),
    KEY ix_products_name (product_name),
    CONSTRAINT ck_products_price_positive CHECK (price > 0),
    CONSTRAINT ck_products_quantity_non_negative CHECK (quantity >= 0)
) ENGINE=InnoDB;
