/* This database setup was approved before submission - Tuesday 10th December 2024 */

CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL, 
    password TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS entries(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL, 
    game_id INTEGER NOT NULL, 
    title TEXT NOT NULL,
    description TEXT,
    rating INTEGER NOT NULL,
    image_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (game_id) REFERENCES games(id));

CREATE TABLE IF NOT EXISTS games(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    year INTEGER NOT NULL, 
    description TEXT,
    rating INTEGER NOT NULL,
    image_path TEXT NOT NULL);

/* INSERT INTO users(username, password) VALUES
                 ('admin_test', '12345');
This is the admin_test user - a dummy user used for website testing */ 