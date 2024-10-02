from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import *
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db, get_redis
import os
import hashlib

users_bp = Blueprint('users', __name__)

@users_bp.route('/', methods=['GET'])
@jwt_required()
def get_user():
    current_user = get_jwt_identity()
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM users WHERE user_id = %s', 
                   (current_user,))
    users = cursor.fetchone()
    return jsonify({"users": users}), 201

@users_bp.route('/<int:user_id>/username', methods=['GET'])
@jwt_required()
def get_username(user_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT nickname FROM users WHERE user_id = %s',
                   (user_id,))
    username = cursor.fetchone()["nickname"]
    return jsonify({"nickname": username}), 201

@users_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    hashed_password = generate_password_hash(data['password'], method='pbkdf2:sha256')
    db = get_db()
    cursor = db.cursor()
    cursor.execute('INSERT INTO users (email, password_hash, nickname) VALUES (%s, %s, %s)', 
                   (data['email'], hashed_password, data['nickname']))
    db.commit()
    return jsonify({'message': 'User registered successfully!'}), 201

@users_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    db = get_db()
    redis = get_redis()
    cursor = db.cursor()

    cursor.execute('SELECT is_check FROM users WHERE email = %s', (data['email'],))
    try:
        is_checked = cursor.fetchone()[0]
    except TypeError: 
        return jsonify({"message": "User not found."}), 409
    
    if not is_checked: return jsonify({"message": "User not checked."}), 401

    cursor.execute('SELECT * FROM users WHERE email = %s', (data['email'],))
    user = cursor.fetchone()
    if not user or not check_password_hash(user[3], data['password']):
        return jsonify({'message': 'Login failed!'}), 409
    user_id = user[0]
    access_token = create_access_token(identity=user_id)
    refresh_token = create_refresh_token(identity=user_id)

    redis.set('user_id:' + str(user_id), refresh_token, current_app.config['JWT_REFRESH_TOKEN_EXPIRES'])

    return jsonify(access_token=access_token, refresh_token=refresh_token), 201

@users_bp.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify(logged_in_user_id=current_user), 200

@users_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True, locations=['headers', 'cookies'])
def refresh():
    data = request.get_json()
    current_user = get_jwt_identity()
    redis = get_redis()
    refresh = redis.get('user_id:' + str(current_user))
    if not refresh:
        return jsonify({"message": "Refresh token outdated."}), 409
    else:
        refresh = refresh.decode('utf-8')

    if data['refresh'] != refresh:
        return jsonify({"message": "Invalid refresh token"}), 400
        
    new_access_token = create_access_token(identity=current_user)
    return jsonify(access_token=new_access_token), 201
    
@users_bp.route('/init-token', methods=['GET'])
@jwt_required()
def logout():
    current_user = get_jwt_identity()
    redis = get_redis()
    is_delete = redis.delete('user_id:' + str(current_user))
    if not is_delete:
        return jsonify({"message": "Token already initialized."}), 401
    return jsonify({"message": "Successfully initialized."}), 201

@users_bp.route('/change-info', methods=['PUT'])
@jwt_required(locations=["cookies", "headers"])
def info_change():
    data = request.get_json()
    current_user = get_jwt_identity()
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = %s', 
                   (current_user,))
    user = cursor.fetchone()
    if not user: return jsonify({'message': 'Not a valid user'}), 401
    cursor.execute('UPDATE users SET email = %s, nickname = %s, introduction = %s WHERE user_id = %s',
                   (data['email'], data['nickname'], data['introduction'], current_user))
    db.commit()
    return jsonify({'message': 'User data successfully chagned'}), 201

@users_bp.route('/change-pw', methods=['PUT'])
@jwt_required(locations=["cookies", "headers"])
def password_change():
    data = request.get_json()
    current_user = get_jwt_identity()
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = %s', 
                   (current_user,))
    user = cursor.fetchone()
    if not user or not check_password_hash(user[3], data['old-password']):
        return jsonify({'message': 'Password incorrect'}), 401
    hashed_new_password = generate_password_hash(data['password'], method='pbkdf2:sha256')
    cursor.execute('UPDATE users SET password_hash = %s WHERE user_id = %s', 
                   (hashed_new_password, current_user))
    db.commit()
    return jsonify({'message': 'User password successfully changed'}), 201

@users_bp.route('/role', methods=['GET'])
@jwt_required()
def get_user_role():
    current_user = get_jwt_identity()    
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = %s', 
                   (current_user,))
    user = cursor.fetchone()
    role = user[5]
    return jsonify({'role': role}), 201

