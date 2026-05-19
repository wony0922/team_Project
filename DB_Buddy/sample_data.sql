-- DB-Buddy 실습용 샘플 스키마 및 더미 데이터

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    price INTEGER NOT NULL,
    stock INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    total_amount INTEGER,
    order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER,
    product_id INTEGER,
    quantity INTEGER,
    unit_price INTEGER,
    FOREIGN KEY(order_id) REFERENCES orders(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);

-- 더미 데이터 삽입
INSERT INTO users (name, email, created_at) VALUES ('홍길동', 'hong@example.com', '2023-01-15 10:00:00');
INSERT INTO users (name, email, created_at) VALUES ('김철수', 'kim@example.com', '2023-02-20 14:30:00');
INSERT INTO users (name, email, created_at) VALUES ('이영희', 'lee@example.com', '2023-03-05 09:15:00');
INSERT INTO users (name, email, created_at) VALUES ('박민수', 'park@example.com', '2023-05-12 11:45:00');
INSERT INTO users (name, email, created_at) VALUES ('최지윤', 'choi@example.com', '2023-07-22 16:20:00');

INSERT INTO products (product_name, price, stock) VALUES ('노트북', 1200000, 10);
INSERT INTO products (product_name, price, stock) VALUES ('무선 마우스', 35000, 50);
INSERT INTO products (product_name, price, stock) VALUES ('기계식 키보드', 150000, 30);
INSERT INTO products (product_name, price, stock) VALUES ('모니터', 350000, 20);

INSERT INTO orders (user_id, total_amount, order_date) VALUES (1, 1235000, '2023-08-01 10:00:00');
INSERT INTO orders (user_id, total_amount, order_date) VALUES (2, 350000, '2023-08-05 14:00:00');

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (1, 1, 1, 1200000);
INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (1, 2, 1, 35000);
INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (2, 4, 1, 350000);
