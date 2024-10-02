from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import *
from db import get_db

comments_bp = Blueprint('comments', __name__)

@comments_bp.route('/novel/<int:novel_id>', methods=['GET'])
@jwt_required(locations=['headers', 'cookies'])
def get_comment(novel_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM novel_comment WHERE novel_id = %s', 
                   (novel_id,))
    comments = cursor.fetchall()
    return jsonify({"comments": comments}), 201

@comments_bp.route('/novel/<int:novel_id>', methods=['POST'])
@jwt_required()
def write_comment(novel_id):
    db = get_db()
    data = request.get_json()
    current_user = get_jwt_identity()
    cursor = db.cursor()
    if data['is_reply']:
        cursor.execute('INSERT INTO comments_novel (novel_id, user_id, content, parent_comment_id) VALUES (%s, %s, %s, %s)', 
                       (novel_id, current_user, data['content'], data['parent_comment_id']))
        db.commit()
        return jsonify({"message": "Comment successfully posted"}), 201
    
    cursor.execute('INSERT INTO comments_novel (novel_id, user_id, content) VALUES (%s, %s, %s)', (novel_id, current_user, data['content']))
    db.commit()
    return jsonify({"message": "Comment successfully posted"}), 201

@comments_bp.route('/novel-comment/<int:comment_id>', methods=['PUT'])
@jwt_required()
def edit_comment(comment_id):
    db = get_db()
    data = request.get_json()
    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)

    cursor.execute('SELECT user_id FROM comments_novel WHERE comment_id = %s', 
                   (comment_id,))
    
    if cursor.fetchone()['user_id'] != current_user:
        return jsonify({"message": "Invalid user_id"}), 401

    cursor.execute('UPDATE comments_novel SET content = %s WHERE comment_id = %s', 
                   (data['content'], comment_id))
    db.commit()
    return jsonify({"message": "Comment Successfully edited"}), 201

@comments_bp.route('/novel-comment/<int:comment_id>', methods=['DELETE'])
@jwt_required()
def delete_comment(comment_id):
    db = get_db()
    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)

    cursor.execute('SELECT user_id FROM comments_novel WHERE comment_id = %s', 
                   (comment_id),)
    
    if cursor.fetchone()['user_id'] != current_user:
        return jsonify({"message": "Invalid user_id"}), 401
    
    cursor.execute('DELETE FROM commets_novel WHERE comment_id = %s', (comment_id))
    db.commit()
    return jsonify({"message": "Comment Successfully deleted"}), 201

@comments_bp.route('/episodes-comment/<int:novel_id>/<int:episode>/count', methods=['GET'])
@jwt_required()
def get_episode_comment_count(novel_id, episode):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT count(comment_id) FROM comments_episode WHERE novel_id = %s AND episode = %s', 
                   (novel_id, episode))
    
    count = cursor.fetchone()['count(comment_id)']

    return jsonify({'count': count})


@comments_bp.route('/episodes-comment/<int:novel_id>/<int:episode>', methods=['GET'])
@jwt_required()
def get_episode_comment(novel_id, episode):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM novel_comment WHERE novel_id = %s AND episode = %s', 
                   (novel_id, episode))
    comments = cursor.fetchall()
    return jsonify({"comments": comments}), 201

@comments_bp.route('/episodes-comment/<int:novel_id>/<int:episode>', methods=['POST'])
@jwt_required()
def upload_episode_comment(novel_id, episode):
    db = get_db()
    data = request.get_json()
    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)
    cursor.execute('INSERT INTO comments_episode (novel_id, episode, user_id, content) VALUES (%s, %s, %s, %s)', 
                   (novel_id, episode, current_user, data['content']))
    return jsonify({"message": "Successfully comment posted"}), 201

@comments_bp.route('/episodes-comment/<int:comment_id>', methods=['PUT'])
@jwt_required()
def edit_episode_comment(comment_id):
    db = get_db()
    data = request.get_json()
    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT user_id FROM comments_episode WHERE comment_id = %s', 
                   (comment_id,))
    if cursor.fetchone()['user_id'] != current_user:
        return jsonify({"message": "Invalid user_id"}), 401
    
    cursor.execute('UPDATE comments_episode SET content = %s WHERE comment_id = %s', 
                   (data['content'], comment_id))
    db.commit()
    return jsonify({"message": "Successfully edited"}), 201

@comments_bp.route('/episodes-comment/<int:comment_id>', methods=['DELETE'])
@jwt_required()
def delete_episode_comment(comment_id):
    db = get_db()
    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT user_id FROM comments_episode WHERE comment_id = %s', 
                   (comment_id,))
    if cursor.fetchone()['user_id'] != current_user:
        return jsonify({"message": "Invalid user_id"}), 401
    
    cursor.execute('DELETE FROM comments_episode WHERE comment_id = %s',
                   (comment_id,))
    db.commit()
    return jsonify({"message":"Successfully deleted"}), 201

@comments_bp.route('/notice-comment/<int:novel_id>/<int:number>', methods=['GET'])
@jwt_required()
def get_notice_comment(novel_id, number):
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute('SELECT * FROM comments_notice WHERE novel_id = %s AND num = %s', 
                   (novel_id, number))
    notice = cursor.fetchone()
    return jsonify({"notice": notice}), 201

@comments_bp.route('/notice-comment/<int:novel_id>/<int:number>', methods=['POST'])
@jwt_required()
def upload_notice_comment(novel_id, number):
    db = get_db()
    current_user = get_jwt_identity()
    data = request.get_json()
    cursor = db.cursor(dictionary=True)
    
    cursor.execute('INSERT INTO comments_notice (novel_id, num, user_id, content) VALUES (%s, %s, %s, %s)', 
                   (novel_id, number, current_user, data['content']))
    
    db.commit()
    return jsonify({"message": "Successfully uploaded."}), 201

@comments_bp.route('/notice-comment/<int:comment_id>', methods=['PUT'])
@jwt_required()
def edit_notice_comment(comment_id):
    db = get_db()
    current_user = get_jwt_identity()
    data = request.get_json()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT user_id FROM comments_notice WHERE comment_id = %s', 
                   (comment_id,))
    if cursor.fetchone()['user_id'] != current_user:
        return jsonify({"message": "Invalid user_id"}), 401

    cursor.execute('UPDATE comments_notice SET content = %s WHERE comment_id = %s', (data['content'], comment_id))
    db.commit()

    return jsonify({"message": "Successfully edited."}), 201

@comments_bp.route('/notice-comment/<int:comment_id>', methods=['DELETE'])
@jwt_required()
def delete_notice_comment(comment_id):
    db = get_db()
    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)

    cursor.execute('SELECT user_id FROM comments_notice WHERE comment_id = %s', 
                   (comment_id,))
    if cursor.fetchone()['user_id'] != current_user:
        return jsonify({"message": "Invalid user_id"}), 401
    
    cursor.execute('DELETE FROM comment_notice WHERE comment_id = %s', 
                   (comment_id,))
    db.commit()

    return jsonify({"message": "Successfully deleted."}), 201