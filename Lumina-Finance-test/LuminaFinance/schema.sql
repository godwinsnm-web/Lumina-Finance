-- LuminaFinance — MySQL 8 schema (3NF)
-- Run: mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS lumina
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;
USE lumina;

-- ── Identity ──────────────────────────────────────────────
CREATE TABLE User_Auth (
    user_id        BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    email          VARCHAR(255) NOT NULL UNIQUE,
    password_hash  VARCHAR(128) NOT NULL,
    display_name   VARCHAR(80)  NOT NULL,
    base_currency  CHAR(3)      NOT NULL DEFAULT 'USD',
    created_at     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_user_email (email)
) ENGINE=InnoDB;

-- ── Reference tables (factored for 3NF) ───────────────────
CREATE TABLE Categories (
    category_id  SMALLINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    name         VARCHAR(60) NOT NULL UNIQUE,
    kind         ENUM('EXPENSE','INCOME') NOT NULL
) ENGINE=InnoDB;

CREATE TABLE Asset_Classes (
    asset_class_id TINYINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    name           VARCHAR(40) NOT NULL UNIQUE
) ENGINE=InnoDB;

-- ── Cash flow ─────────────────────────────────────────────
CREATE TABLE Transactions (
    transaction_id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    user_id        BIGINT UNSIGNED   NOT NULL,
    category_id    SMALLINT UNSIGNED NOT NULL,
    amount         DECIMAL(19,4)     NOT NULL,
    txn_date       DATE              NOT NULL,
    description    VARCHAR(180),
    is_recurring   BOOLEAN           NOT NULL DEFAULT FALSE,
    created_at     DATETIME(3)       NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    CONSTRAINT fk_txn_user     FOREIGN KEY (user_id)     REFERENCES User_Auth(user_id)   ON DELETE CASCADE,
    CONSTRAINT fk_txn_category FOREIGN KEY (category_id) REFERENCES Categories(category_id),
    INDEX idx_txn_user_date (user_id, txn_date DESC),
    INDEX idx_txn_user_cat  (user_id, category_id)
) ENGINE=InnoDB;

-- ── Portfolio ─────────────────────────────────────────────
CREATE TABLE Asset_Portfolio (
    asset_id       BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    user_id        BIGINT UNSIGNED   NOT NULL,
    asset_class_id TINYINT UNSIGNED  NOT NULL,
    ticker         VARCHAR(20)       NOT NULL,
    quantity       DECIMAL(19,4)     NOT NULL,
    cost_basis     DECIMAL(19,4)     NOT NULL,
    acquired_at    DATE              NOT NULL,
    CONSTRAINT fk_asset_user  FOREIGN KEY (user_id)        REFERENCES User_Auth(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_asset_class FOREIGN KEY (asset_class_id) REFERENCES Asset_Classes(asset_class_id),
    INDEX idx_asset_user_class (user_id, asset_class_id)
) ENGINE=InnoDB;

CREATE TABLE Asset_Price_History (
    price_id    BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    asset_id    BIGINT UNSIGNED NOT NULL,
    price       DECIMAL(19,4)   NOT NULL,
    recorded_at DATETIME(3)     NOT NULL,
    CONSTRAINT fk_price_asset FOREIGN KEY (asset_id) REFERENCES Asset_Portfolio(asset_id) ON DELETE CASCADE,
    INDEX idx_price_asset_time (asset_id, recorded_at DESC)
) ENGINE=InnoDB;

-- ── Forecast cache ────────────────────────────────────────
CREATE TABLE Forecast_Snapshots (
    snapshot_id      BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    user_id          BIGINT UNSIGNED NOT NULL,
    generated_at     DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    horizon_months   TINYINT UNSIGNED NOT NULL DEFAULT 6,
    projected_spend  DECIMAL(19,4)   NOT NULL,
    projected_income DECIMAL(19,4)   NOT NULL,
    runway_months    DECIMAL(10,2),
    method           VARCHAR(40)     NOT NULL,
    params           JSON,
    CONSTRAINT fk_fc_user FOREIGN KEY (user_id) REFERENCES User_Auth(user_id) ON DELETE CASCADE,
    INDEX idx_fc_user_time (user_id, generated_at DESC)
) ENGINE=InnoDB;

-- ── Seed reference data ───────────────────────────────────
INSERT INTO Categories (name, kind) VALUES
    ('Salary',        'INCOME'),
    ('Dividends',     'INCOME'),
    ('Rent',          'EXPENSE'),
    ('Groceries',     'EXPENSE'),
    ('Dining',        'EXPENSE'),
    ('Transport',     'EXPENSE'),
    ('Subscriptions', 'EXPENSE'),
    ('Travel',        'EXPENSE'),
    ('Healthcare',    'EXPENSE'),
    ('Other',         'EXPENSE');

INSERT INTO Asset_Classes (name) VALUES
    ('Cash'), ('Stocks'), ('Crypto'), ('Gold'), ('Bonds');
