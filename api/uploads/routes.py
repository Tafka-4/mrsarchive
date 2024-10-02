from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import *
from db import get_db, get_aws_s3_client
from botocore.exceptions import ClientError
import hashlib
import re

uploads_bp = Blueprint('uploads', __name__)

BUCKET_NAME = 'webnovelarchive1'
USER_PROFILE_FOLDER = 'user_profile/'
NOVEL_THUMBNAIL_FOLDER = 'novel_thumbnail/'
EPISODE_IMAGE_FOLDER = 'episode_image/'
NOTICE_IMAGE_FOLDER = 'notice_image/'

def is_allowed_file(filename, ALLOWED_EXTENSIONS):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_extension(filename):
    return filename.rsplit('.', 1)[1].lower()

def sanitize(input_string):
    # Wait, Is it right?
    sanitized = re.sub(r'[^a-zA-Z0-9/\.]', '', input_string)
    sanitized = re.sub(r'\.+/', '/', sanitized) 
    while '../' in sanitized:
        sanitized = sanitized.replace('../', '')
    return sanitized

def extract_key(url):
    match = re.search(r'https://[^/]+/(.+)', url)
    if match: return sanitize(match.group(1))
    return 

def extract_episode_key(novel_id, episode, content):
    base = f"https://webnovelarchive1\.s3\.amazonaws\.com/episode_image/{novel_id}/{episode}/(?P<i>[^/.]+)\.(?P<ext>[^']+)"
    matches = re.finditer(base, content)
    return [f"/episode_image/{novel_id}/{episode}/{match.group('i')}.{match.group('ext')}" for match in matches]

def extract_notice_key(novel_id, number, content):
    base = f"https://webnovelarchive1\.s3\.amazonaws\.com/notice_image/{novel_id}/{number}/(?P<i>[^/.]+)\.(?P<ext>[^']+)"
    matches = re.finditer(base, content)
    return [f"/notice_image/{novel_id}/{number}/{match.group('i')}.{match.group('ext')}" for match in matches]

@uploads_bp.route('/user/', methods=['POST'])
@jwt_required(locations=["cookies", "headers"])
def user_upload():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    current_user = get_jwt_identity()

    cursor.execute('SELECT * FROM users WHERE user_id = %s', (current_user,))
    if not cursor.fetchone():
        return jsonify({"message": "User not found"}), 400

    if "profile_image" not in request.files or request.files["profile_image"].filename == '':
        return jsonify({"message": "No file provided"}), 400

    profile_image = request.files["profile_image"]
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

    if not is_allowed_file(profile_image.filename, ALLOWED_EXTENSIONS):
        return jsonify({"message": "Invalid file extension"}), 400
    
    extension = get_file_extension(profile_image.filename)
    profile_image.filename = hashlib.sha256(str(current_user).encode() + current_app.config['SECRET_KEY']).hexdigest() + '.' + extension

    s3 = get_aws_s3_client()
    image_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{USER_PROFILE_FOLDER + profile_image.filename}"

    s3.upload_fileobj(profile_image, BUCKET_NAME, USER_PROFILE_FOLDER + profile_image.filename)
    cursor.execute('UPDATE users SET profile_image = %s WHERE user_id = %s', 
                   (image_url, current_user))
    db.commit()
    
    return jsonify({"message": "Successfully uploaded"}), 201

@uploads_bp.route('/user/', methods=['DELETE'])
@jwt_required()
def user_delete():
    current_user = get_jwt_identity()
    db = get_db()
    s3 = get_aws_s3_client()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM users WHERE user_id = %s', 
                   (current_user,))
    if not cursor.fetchone():
        return jsonify({"message": "User not found"}), 400
    
    cursor.execute('SELECT profile_image FROM users WHERE user_id = %s', 
                   (current_user,))

    profile_image = cursor.fetchone()['profile_image']

    if not profile_image:
        return jsonify({"message": "No profile image"}), 400

    file_key = extract_key(cursor.fetchone()['profile_image'])
    s3.delete_object(Bucket=BUCKET_NAME, Key=file_key)

    cursor.execute('UPDATE users SET profile_image = NULL WHERE user_id = %s', 
                   (current_user))
    db.commit()
    return jsonify({"Successfully deleted"}), 201

@uploads_bp.route('/novel/', methods=['POST'])
@jwt_required(locations=["cookies", "headers"])
def novel_upload():
    thumbnail_image = request.files.get('thumbnail')

    if not thumbnail_image:
        return jsonify({"message": "No file uploaded"}), 400

    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

    if not is_allowed_file(thumbnail_image.filename, ALLOWED_EXTENSIONS):
        return jsonify({"message": "Invalid file extension"}), 400
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT MAX(novel_id) FROM novels')
    result = cursor.fetchone()
    if not result: max_novel_id = 0
    else: max_novel_id = result['MAX(novel_id)']

    extension = get_file_extension(thumbnail_image.filename)
    thumbnail_image.filename = hashlib.sha256(str(max_novel_id + 1).encode() + current_app.config['SECRET_KEY']).hexdigest() + '.' + extension
    
    s3 = get_aws_s3_client()
    s3.upload_fileobj(thumbnail_image, BUCKET_NAME, NOVEL_THUMBNAIL_FOLDER + thumbnail_image.filename)

    return jsonify({"message": "Successfully uploaded"}), 201

@uploads_bp.route('/novel/<int:novel_id>/', methods=['PUT'])
@jwt_required()
def novel_edit(novel_id):
    current_user = get_jwt_identity()
    thumbnail_image = request.files['file']
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

    if not is_allowed_file(thumbnail_image.filename, ALLOWED_EXTENSIONS):
        return jsonify({"message": "Invalid file extension"}), 400
    
    extension = get_file_extension(thumbnail_image.filename)
    thumbnail_image.filename = hashlib.sha256(str(novel_id).encode() + current_app.config['SECRET_KEY']).hexdigest() + '.' + extension

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT author_id FROM novels WHERE novel_id = %s', 
                   (novel_id,))
    author = cursor.fetchone()['author_id']

    if author != current_user:
        return jsonify({"message": "Not a author"}), 401
    
    s3 = get_aws_s3_client()
    image_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{NOVEL_THUMBNAIL_FOLDER + thumbnail_image.filename}"
    s3.upload_fileobj(thumbnail_image, BUCKET_NAME, NOVEL_THUMBNAIL_FOLDER + thumbnail_image.filename)
    s3.put_object(Bucket=BUCKET_NAME, Key=EPISODE_IMAGE_FOLDER + str(novel_id))

    cursor.execute('UPDATE novels SET thumbnail = %s WHERE novel_id = %s', 
                   (image_url, novel_id))
    db.commit()
    return jsonify({"Successfully uploaded"}), 201

@uploads_bp.route('/novel/<int:novel_id>/', methods=['DELETE'])
@jwt_required()
def novel_delete(novel_id):
    db = get_db()
    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT author_id FROM novels WHERE novel_id = %s', 
                   (novel_id,))
    author = cursor.fetchone()['author_id']

    if author != current_user:
        return jsonify({"message": "Not a author"}), 401

    cursor.execute('SELECT thumbnail FROM novels WHERE novel_id = %s',
                   (novel_id,))
    thumbnail = cursor.fetchone()['thumbnail']

    if not thumbnail:
        return jsonify({"message": "No thumbnail"}), 401
    
    s3 = get_aws_s3_client()
    file_key = extract_key(thumbnail)
    s3.delete_object(Bucket=BUCKET_NAME, Key=file_key)

    cursor.execute('UPDATE novels SET thumbnail = NULL WHERE novel_id = %s', 
                   (novel_id,))
    db.commit()
    return jsonify({"message": "Successfully deleted"}), 201

@uploads_bp.route('/novel/<int:novel_id>/episode/<int:episode>/', methods=['POST'])
@jwt_required()
def episode_upload(novel_id, episode):
    current_user = get_jwt_identity()
    s3 = get_aws_s3_client()

    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    cursor.execute('SELECT author_id FROM novels WHERE novel_id = %s', (novel_id,))
    author = cursor.fetchone()['author_id']
    if author != current_user:
        return jsonify({"message": "Not a author"}), 401

    images = request.files.getlist('images')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
    BASE_LOCATION = EPISODE_IMAGE_FOLDER + str(novel_id) +'/' + str(episode) + '/'

    for count, image in enumerate(images):
        if not is_allowed_file(image.filename, ALLOWED_EXTENSIONS):
            return jsonify({"message": "Invalid file extension"}), 409
        
        extension = get_file_extension(image.filename)
        image.filename = str(count+1) + '.' + extension

        image.seek(0)
        s3.upload_fileobj(image, BUCKET_NAME, BASE_LOCATION + image.filename, {'ACL':'public-read'})

    return jsonify({"message": "Successfully uploaded"}), 201

@uploads_bp.route('/novel/<int:novel_id>/episode/<int:episode>/', methods=['DELETE'])
@jwt_required()
def episode_delete(novel_id, episode):
    current_user = get_jwt_identity()
    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)
    
    cursor.execute('SELECT author_id FROM novels WHERE novel_id = %s', 
                   (novel_id,))
    author = cursor.fetchone()['author_id']
    if author != current_user:
        return jsonify({"message": "Not a author"}), 401
    
    s3 = get_aws_s3_client()
    
    cursor.execute('SELECT content FROM episodes WHERE novel_id = %s AND episode = %s', 
                   (novel_id, episode))
    content = cursor.fetchone()['content']

    keys = extract_episode_key(novel_id, episode, content)
    
    for key in keys:
        s3.delete_object(Bucket=BUCKET_NAME, Key=key)

    return jsonify({"message": "Successfully deleted."}), 201

@uploads_bp.route('/novel/<int:novel_id>/notice/<int:number>', methods=['POST'])
@jwt_required()
def notice_upload(novel_id, number):
    current_user = get_jwt_identity()
    db = get_db()
    cursor = db.cursor(dictionary=True)
    s3 = get_aws_s3_client()

    cursor.execute('SELECT author_id FROM novels WHERE novel_id = %s', 
                   (novel_id, ))
    author = cursor.fetchone()['author_id']
    if author != current_user:
        return jsonify({"message": "Not a author"}), 401

    images = request.files.getlist('images')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
    
    BASE_LOCATION = NOTICE_IMAGE_FOLDER + str(novel_id) +'/' + str(number) + '/'

    s3.put_object(Bucket=BUCKET_NAME, Key=BASE_LOCATION)

    for count, image in enumerate(images):
        if not is_allowed_file(image.filename, ALLOWED_EXTENSIONS):
            return jsonify({"message": "Invalid file extension"}), 401

        extension = get_file_extension(image.filename)
        image.filename = str(count+1) + '.' + extension
        s3.upload_fileobj(image, BUCKET_NAME, BASE_LOCATION + image.filename)

    return jsonify({"message": "Successfully uploaded"}), 201
    
@uploads_bp.route('/novel/<int:novel_id>/notice/<int:number>', methods=['DELETE'])
@jwt_required()
def notice_delete(novel_id, number):
    current_user = get_jwt_identity()
    db = get_db()
    cursor = db.cursor(dictionary=True)
    s3 = get_aws_s3_client()

    cursor.execute('SELECT author_id FROM novels WHERE novel_id = %s')
    author = cursor.fetchone()['author_id']
    if author != current_user:
        return jsonify({"message": "Not a author"}), 401
    
    cursor.execute('SELECT content FROM notice WHERE novel_id = %s AND number = %s',
                   (novel_id, number))
    content = cursor.fetchone()['content']

    keys = extract_notice_key(novel_id, number, content)

    for key in keys:
        s3.delete(Bucket=BUCKET_NAME, Key=key)

    return jsonify({"message": "Successfully deleted."}), 201