SET FOREIGN_KEY_CHECKS=0;

SET GLOBAL time_zone='+09:00';
SET time_zone='+09:00';

CREATE TABLE users (
    user_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    profile_image VARCHAR(255) DEFAULT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nickname VARCHAR(50) NOT NULL UNIQUE,
    introduction TEXT,
    role ENUM('user', 'admin') DEFAULT 'user',
    is_check BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);  

CREATE TABLE novels (
    novel_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    thumbnail VARCHAR(255) DEFAULT NULL,
    introduction TEXT,
    author_id BIGINT UNSIGNED,
    episode INT UNSIGNED DEFAULT 0,
    notice INT UNSIGNED DEFAULT 0,
    views BIGINT UNSIGNED DEFAULT 0,
    recommendations BIGINT UNSIGNED DEFAULT 0,
    dislikes BIGINT UNSIGNED DEFAULT 0,
    favorites BIGINT UNSIGNED DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (author_id) REFERENCES users(user_id)
);

CREATE TABLE episodes (
    episode INT UNSIGNED,
    novel_id BIGINT UNSIGNED,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    author_note TEXT,
    views BIGINT UNSIGNED DEFAULT 0,
    recommendations BIGINT UNSIGNED DEFAULT 0,
    dislikes BIGINT UNSIGNED DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (novel_id) REFERENCES novels(novel_id)
);

CREATE TABLE notice (
    notice_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    novel_id BIGINT UNSIGNED NOT NULL,
    title VARCHAR(255) NOT NULL,
    num INT NOT NULL,
    content TEXT NOT NULL,
    author_note TEXT,
    author_id BIGINT UNSIGNED NOT NULL,
    views BIGINT UNSIGNED DEFAULT 0,
    recommendations BIGINT UNSIGNED DEFAULT 0,
    dislikes BIGINT UNSIGNED DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (novel_id) REFERENCES novels(novel_id),
    FOREIGN KEY (author_id) REFERENCES users(user_id)
);

CREATE TABLE like_novel_table (
    is_like BOOLEAN,
    user_id BIGINT UNSIGNED,
    novel_id BIGINT UNSIGNED,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (novel_id) REFERENCES novels(novel_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE like_episode_table (
    is_like BOOLEAN,
    user_id BIGINT UNSIGNED,
    novel_id BIGINT UNSIGNED,
    episode INT UNSIGNED,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (novel_id) REFERENCES novels(novel_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE like_notice_table (
    is_like BOOLEAN,
    user_id BIGINT UNSIGNED,
    novel_id BIGINT UNSIGNED,
    num INT UNSIGNED,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (novel_id) REFERENCES novels(novel_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE favorites (
    favorite_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED,
    novel_id BIGINT UNSIGNED,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (novel_id) REFERENCES novels(novel_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE recent_views (
    view_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED,
    novel_id BIGINT UNSIGNED,
    episode INT UNSIGNED,
    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (novel_id) REFERENCES novels(novel_id)
);

CREATE TABLE comments_novel (
    comment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    novel_id BIGINT UNSIGNED,
    user_id BIGINT UNSIGNED, 
    content TEXT,
    recommendations BIGINT UNSIGNED DEFAULT 0,
    dislikes BIGINT UNSIGNED DEFAULT 0,
    report_status BOOLEAN DEFAULT FALSE,
    parent_comment_id BIGINT UNSIGNED,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (novel_id) REFERENCES novels(novel_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (parent_comment_id) REFERENCES comments_novel(comment_id)
);

CREATE TABLE comments_episode (
    comment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    novel_id BIGINT UNSIGNED,
    episode INT UNSIGNED,
    user_id BIGINT UNSIGNED,
    content TEXT,
    recommendations BIGINT UNSIGNED DEFAULT 0,
    dislikes BIGINT UNSIGNED DEFAULT 0,
    report_status BOOLEAN DEFAULT FALSE,
    parent_comment_id BIGINT UNSIGNED,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (novel_id) REFERENCES novels(novel_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (parent_comment_id) REFERENCES comments_episode(comment_id)
);

CREATE TABLE comments_notice (
    comment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    novel_id BIGINT UNSIGNED,
    num INT UNSIGNED,
    user_id BIGINT UNSIGNED,
    content TEXT,
    recommendations BIGINT UNSIGNED DEFAULT 0,
    dislikes BIGINT UNSIGNED DEFAULT 0,
    report_status BOOLEAN DEFAULT FALSE,
    parent_comment_id BIGINT UNSIGNED,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (novel_id) REFERENCES novels(novel_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (parent_comment_id) REFERENCES comments_notice(comment_id)
);

CREATE TABLE reports (
    report_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    report_type VARCHAR(32),
    comment_id BIGINT UNSIGNED,
    report_reason TEXT,
    report_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (comment_id) REFERENCES comments_novel(comment_id)
);

CREATE TABLE admin_logs (
    log_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    action VARCHAR(255),
    user_id BIGINT UNSIGNED,
    target_id BIGINT UNSIGNED,
    target_type ENUM('user', 'novel', 'episode', 'comment'),
    action_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

SET FOREIGN_KEY_CHECKS=1;