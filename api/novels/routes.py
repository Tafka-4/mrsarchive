from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import *
from db import get_db
from .utils import *

import re
import hashlib

novels_bp = Blueprint('novels', __name__)

@novels_bp.route('/', methods=['GET'])
@jwt_required()
def get_novels():
    start = request.args.get("start", type=int)
    amount = request.args.get("amount", type=int)
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM novels LIMIT %s, %s', (start-1, amount))
    novels = cursor.fetchall()
    return jsonify({"novels": novels}), 201

@novels_bp.route('/search-novel-count', methods=['GET'])
@jwt_required()
def search_novel_count():
    keyword = request.args.get("keyword")
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT count(novel_id) FROM novels WHERE title LIKE %s', (keyword + '%',))
    count = cursor.fetchone()['count(novel_id)']
    return jsonify({"count": count}), 201

@novels_bp.route('/search-novel', methods=['GET'])
@jwt_required()
def search_novel():
    keyword = request.args.get("keyword")
    start = request.args.get("start", type=int)
    amount = request.args.get("amount", type=int)
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM novels WHERE title LIKE %s LIMIT %s, %s', (keyword + '%', start-1, amount))
    novels = cursor.fetchall()
    return jsonify({"novels": novels}), 201

@novels_bp.route('/count', methods=['GET'])
@jwt_required()
def get_novel_count():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT count(novel_id) FROM novels')
    count = cursor.fetchone()['count(novel_id)']
    return jsonify({"count": count}), 201

@novels_bp.route('/set', methods=['POST'])
@jwt_required()
def update_novels_username():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    novels = request.get_json()
    for item in novels:
        author_id = item["author_id"]
        cursor.execute('SELECT nickname FROM users WHERE user_id = %s',
                   (author_id,))
        username = cursor.fetchone()
        
        if not username: del item
        else: item["author_nickname"] = username["nickname"]

    return jsonify({"novels": novels}), 201

@novels_bp.route('/get-episodes/<int:novel_id>', methods=['GET'])
@jwt_required()
def get_novel_episodes(novel_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT max(episode) FROM novels WHERE novel_id = %s', 
                   (novel_id,))
    episodes = cursor.fetchone()["max(episode)"]
    return jsonify({"episode": episodes})


@novels_bp.route('/<int:novel_id>', methods=['GET'])
@jwt_required()
def get_novel_data(novel_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    start = request.args.get("start", type=int)
    amount = request.args.get("amount", type=int)
    cursor.execute('SELECT * FROM novels WHERE novel_id = %s', 
                   (novel_id,))
    novel = cursor.fetchone()

    cursor.execute('SELECT * FROM episodes WHERE novel_id = %s AND episode BETWEEN %s AND %s + %s - 1', 
                   (novel_id, start, start, amount))
    novel["episode_data"] = cursor.fetchall()
    return jsonify({"novel": novel}), 201

@novels_bp.route('/upload', methods=['POST'])
@jwt_required(locations=['headers', 'cookies'])
def upload_novel():
    db = get_db()
    data = request.form

    access_token = request.cookies.get('access_token')

    if not access_token:
        return jsonify({"message": "Missing access token"}), 401

    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)

    thumbnail = request.files.get('thumbnail')

    cursor.execute('SELECT title FROM novels WHERE author_id = %s', (current_user,))
    title_list = [title['title'] for title in cursor.fetchall()]

    cursor.execute('SELECT MAX(novel_id) FROM novels')
    result = cursor.fetchone()
    if not result: max_novel_id = 0
    else: max_novel_id = result['MAX(novel_id)']

    if data['title'] in title_list:
        return jsonify({"message": "Title already exists"}), 409
    
    if thumbnail:
        header = {'Authorization': 'Bearer ' + access_token}
        api_resp = requests.post(f'http://api:5000/api/uploads/novel/', files={'thumbnail': (thumbnail.filename, thumbnail)}, headers=header)
        
        if api_resp.status_code != 201: 
            return jsonify({"message": "Thumbnail upload failed"}), 409

        def get_file_extension(filename):
            return filename.rsplit('.', 1)[1].lower()

        extension = get_file_extension(thumbnail.filename)
        
        filename = hashlib.sha256(str(max_novel_id + 1).encode() + current_app.config['SECRET_KEY']).hexdigest() + '.' + extension

        thumbnail = "https://webnovelarchive1.s3.amazonaws.com/novel_thumbnail/" + filename
        cursor.execute('INSERT INTO novels (title, introduction, thumbnail ,author_id) VALUES (%s, %s, %s, %s)',
                    (data['title'], data['introduction'], thumbnail, current_user)) # will be edited
    else:
        cursor.execute('INSERT INTO novels (title, introduction, thumbnail ,author_id) VALUES (%s, %s, %s, %s)', 
                    (data['title'], data['introduction'], None, current_user))
        filename = None
    db.commit()

    return jsonify({"message": "successfully uploaded!", "novel_id": max_novel_id + 1,"image_url": filename if filename else None}), 201

@novels_bp.route('/<int:novel_id>/edit', methods=['PUT'])
@jwt_required(locations=['headers', 'cookies'])
def edit_novel(novel_id):
    db = get_db()
    data = request.form

    access_token = request.cookies.get('access_token')

    if not access_token:
        return jsonify({"message": "Missing access token"}), 401

    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)

    cursor.execute('SELECT author_id, title, thumbnail FROM novels WHERE novel_id = %s', (novel_id,))
    novel = cursor.fetchone()

    if not novel:
        return jsonify({"message": "Novel not found"}), 404

    if novel['author_id'] != current_user:
        return jsonify({"message": "You are not the author of this novel"}), 403

    if 'title' in data:
        cursor.execute('SELECT title FROM novels WHERE author_id = %s AND title = %s AND novel_id != %s', (current_user, data['title'], novel_id))
        title_exists = cursor.fetchone()

        if title_exists:
            return jsonify({"message": "Title already exists"}), 409

    thumbnail = request.files.get('thumbnail')
    if thumbnail:
        header = {'Authorization': 'Bearer ' + access_token}
        api_resp = requests.put(f'http://api:5000/api/uploads/novel/', files={'thumbnail': (thumbnail.filename, thumbnail)}, headers=header)

        if api_resp.status_code != 201:
            return jsonify({"message": "Thumbnail upload failed"}), 409

        def get_file_extension(filename):
            return filename.rsplit('.', 1)[1].lower()

        extension = get_file_extension(thumbnail.filename)
        filename = hashlib.sha256(str(novel_id).encode() + current_app.config['SECRET_KEY']).hexdigest() + '.' + extension
        new_thumbnail_url = "https://webnovelarchive1.s3.amazonaws.com/novel_thumbnail/" + filename

        cursor.execute('UPDATE novels SET thumbnail = %s WHERE novel_id = %s', (new_thumbnail_url, novel_id)) # will be deleted

    if 'title' in data:
        cursor.execute('UPDATE novels SET title = %s WHERE novel_id = %s', (data['title'], novel_id))

    if 'introduction' in data:
        cursor.execute('UPDATE novels SET introduction = %s WHERE novel_id = %s', (data['introduction'], novel_id))

    db.commit()

    return jsonify({"message": "Novel successfully updated!", "novel_id": novel_id}), 200

@novels_bp.route('/<int:novel_id>/delete', methods=['DELETE'])
@jwt_required(locations=["cookies"])
def delete_novel(novel_id):
    db = get_db()
    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)

    cursor.execute('SELECT * FROM novels WHERE novel_id = %s AND author_id = %s', 
                   (novel_id, current_user))
    is_user = cursor.fetchone()
    if not is_user:
        return jsonify({"message": "Invalid user id"}), 409

    cursor.execute('SELECT thumbnail FROM novels WHERE novel_id = %s', 
                   (novel_id,))
    thumbnail = cursor.fetchone()['thumbnail']

    if thumbnail:
        header = {'Authorization': 'Bearer ' + request.cookies.get('access_token')}
        api_resp = requests.delete(f'http://api:5000/api/uploads/novel/{novel_id}/', headers=header)
        if api_resp.status_code != 201:
            return jsonify({"message": "Thumbnail delete failed"}), 409
    try: 
        cursor.execute('DELETE FROM novels where novel_id = %s', 
                    (novel_id,))
    except:
        return jsonify({"message": "Novel data is remaining."}), 400
    db.commit()
    return jsonify({"message": "successfully deleted!"}), 201

@novels_bp.route('/<int:novel_id>/like', methods=['POST'])
@jwt_required(locations=["cookies", "headers"])
def like_novel(novel_id):
    db = get_db()
    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM like_novel_table WHERE user_id = %s AND novel_id = %s', 
                   (current_user, novel_id))
    
    try: 
        is_like = cursor.fetchone()["is_like"]
    except TypeError: # like
        cursor.execute('INSERT INTO like_novel_table (is_like, user_id, novel_id) VALUES (%s, %s, %s)', 
                       (True, current_user, novel_id))
        cursor.execute('UPDATE novels SET recommendations = recommendations + 1 WHERE novel_id = %s', 
                       (novel_id,))
        db.commit()
        return jsonify({"message": "Successfully liked!"}), 201

    if is_like: # cancel like
        cursor.execute('DELETE FROM like_novel_table WHERE user_id = %s AND novel_id = %s', 
                       (current_user, novel_id))
        cursor.execute('UPDATE novels SET recommendations = recommendations - 1 WHERE novel_id = %s', 
                       (novel_id,))
        db.commit()
        return jsonify({"message": "like successfully canceled!"}), 201
    else: # dislike to like
        cursor.execute('UPDATE like_novel_table SET is_like = TRUE WHERE user_id = %s AND novel_id = %s', 
                       (current_user, novel_id))
        cursor.execute('UPDATE novels SET recommendations = recommendations + 1, dislikes = dislikes - 1 WHERE novel_id = %s', 
                       (novel_id,))
        db.commit()
        return jsonify({"message": "Successfully liked!"}), 201
    
@novels_bp.route('/<int:novel_id>/dislike', methods=['POST'])
@jwt_required(locations=["cookies", "headers"])
def dislike_novel(novel_id):
    db = get_db()
    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM like_novel_table WHERE user_id = %s AND novel_id = %s', 
                   (current_user, novel_id))

    try: 
        is_like = cursor.fetchone()["is_like"]
    except TypeError: # dislike
        cursor.execute('INSERT INTO like_novel_table (is_like, user_id, novel_id) VALUES (%s, %s, %s)', 
                       (False, current_user, novel_id))
        cursor.execute('UPDATE novels SET dislikes = dislikes + 1 WHERE novel_id = %s', 
                       (novel_id,))
        db.commit()
        return jsonify({"message": "Successfully disliked!"}), 201
    
    if is_like: # like to dislike
        cursor.execute('UPDATE like_novel_table SET is_like = FALSE WHERE user_id = %s AND novel_id = %s', 
                       (current_user, novel_id))
        cursor.execute('UPDATE novels SET dislikes = dislikes + 1, recommendations = recommendations - 1 WHERE novel_id = %s',
                       (novel_id,))
        db.commit()
        return jsonify({"message": "Successfully disliked!"}), 201
    else: # cancel dislike
        cursor.execute('DELETE FROM like_novel_table WHERE user_id = %s AND novel_id = %s', 
                       (current_user, novel_id))
        cursor.execute('UPDATE novels SET dislikes = dislikes - 1 WHERE novel_id = %s', 
                       (novel_id,))
        db.commit()
        return jsonify({"message": "dislike successfully canceled!"}), 201

@novels_bp.route('/<int:novel_id>/favorite', methods=['POST'])
@jwt_required(locations=["cookies", "headers"])
def favorite_novel(novel_id):
    db = get_db()
    current_user = get_jwt_identity()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM favorites WHERE user_id = %s AND novel_id = %s', 
                   (current_user, novel_id))
    favorite_novel = cursor.fetchone()
    if favorite_novel:
        cursor.execute('DELETE FROM favorites WHERE user_id = %s AND novel_id = %s', 
                   (current_user, novel_id))
        cursor.execute('UPDATE novels SET favorites = favorites - 1 WHERE novel_id = %s',
                       (novel_id,))
        db.commit()
        return jsonify({"message": "Successfully unfavorited."}), 201
    
    cursor.execute('INSERT INTO favorites (user_id, novel_id) VALUES (%s, %s)', 
                   (current_user, novel_id))
    cursor.execute('UPDATE novels SET favorites = favorites + 1 WHERE novel_id = %s',
                   (novel_id,))
    db.commit()
    return jsonify({"message": "Successfully added to favorites"}), 201

@novels_bp.route('/<int:novel_id>/episode/<int:episode>', methods=['GET'])
@jwt_required(locations=["cookies", "headers"])
def get_novel_text(novel_id, episode):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT max(episode) FROM episodes WHERE novel_id = %s', 
                   (novel_id,))
    max_episode = cursor.fetchone()['max(episode)']
    is_last = True if max_episode == episode else False

    cursor.execute('SELECT * FROM episodes WHERE novel_id = %s AND episode = %s', 
                   (novel_id, episode))
    novel_episodes = cursor.fetchone()
    cursor.execute('UPDATE novels SET views = views + 1 WHERE novel_id = %s', 
                   (novel_id,))
    cursor.execute('UPDATE episodes SET views = views + 1 WHERE novel_id = %s AND episode = %s', 
                   (novel_id, episode))
    db.commit()
    if not novel_episodes:
        return jsonify({"message": "Welcome to the MTE World!"}), 409
    
    novel_episodes['is_last'] = is_last
    return jsonify({"novel_text": novel_episodes})

@novels_bp.route('/<int:novel_id>/episode', methods=['POST'])
@jwt_required(locations=["cookies", "headers"])
def upload_episode(novel_id):
    db = get_db()
    data = request.get_json()
    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM novels WHERE novel_id = %s AND author_id = %s', 
                   (novel_id, current_user))
    is_author = cursor.fetchone()
    if not is_author:
        return jsonify({"message": "Not a novel author"}), 401
    
    cursor.execute('SELECT max(episode) FROM episodes WHERE novel_id = %s', 
                   (novel_id,))
    current_episode = cursor.fetchone()['max(episode)']

    auth_header = request.headers.get('Authorization', None)
    access_token = auth_header.split()[1]

    if not current_episode: current_episode = 0
    upload_episode_images_to_api(novel_id, current_episode + 1, access_token, data['content'])
    
    def replace_img_tags(data):
        ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
        img_tags = re.findall(r'<img src="data:image/(\w+);base64,([^"]+)">', data)
        new_data = data

        for i, (ext, base64_data) in enumerate(img_tags, start=1):
            if ext.lower() not in ALLOWED_EXTENSIONS: continue
            new_url = f"https://webnovelarchive1.s3.amazonaws.com/episode_image/{novel_id}/{current_episode + 1}/{i}.{ext}"
            new_tag = f"<img src='{new_url}'>"
            img_tag = f'<img src="data:image/{ext};base64,{base64_data}">'
            new_data = new_data.replace(img_tag, new_tag)

        return new_data

    cursor.execute('INSERT INTO episodes (episode, novel_id, title, content, author_note) VALUES (%s, %s, %s, %s, %s)', 
                   (current_episode + 1, novel_id, data['title'], replace_img_tags(data['content']), data['author_note']))
    cursor.execute('UPDATE novels SET episode = episode + 1 WHERE novel_id = %s',
                   (novel_id,))
    db.commit()
    return jsonify({"episode": current_episode + 1}), 201

@novels_bp.route('/<int:novel_id>/episode/<int:episode>', methods=['PUT'])
@jwt_required(locations=["cookies", "headers"])
def edit_episode(novel_id, episode):
    db = get_db()
    data = request.get_json()
    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)

    cursor.execute('SELECT * FROM novels WHERE novel_id = %s AND author_id = %s', 
                   (novel_id, current_user))
    is_author = cursor.fetchone()
    if not is_author:
        return jsonify({"message": "Not a novel author"}), 401
    
    auth_header = request.headers.get('Authorization', None)
    access_token = auth_header.split()[1]
    upload_episode_images_to_api(novel_id, episode, access_token, data['content'])

    def replace_img_tags(data):
        img_tags = re.findall(r'<img src="data:image/(\w+);base64,([^"]+)">', data)
        new_data = data

        for i, (ext, base64_data) in enumerate(img_tags, start=1):
            new_url = f"https://webnovelarchive1.s3.amazonaws.com/episode_image/{novel_id}/{episode}/{i}.{ext}"
            img_tag = f'<img src="data:image/{ext};base64,{base64_data}">'
            new_tag = f"<img src='{new_url}'>"
            new_data = new_data.replace(img_tag, new_tag)

        return new_data

    cursor.execute('UPDATE episodes SET title = %s, content = %s, author_note = %s WHERE novel_id = %s AND episode = %s', 
                   (data['title'], data['content'], replace_img_tags(data['author_note']), novel_id, episode))
    db.commit()
    return jsonify({"message": "Successfully edited"}), 201

@novels_bp.route('/<int:novel_id>/episode/<int:episode>', methods=['DELETE'])
@jwt_required(locations=["cookies", "headers"])
def delete_episode(novel_id, episode):
    db = get_db()
    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)

    cursor.execute('SELECT * FROM novels WHERE novel_id = %s AND author_id = %s', 
                   (novel_id, current_user))
    is_author = cursor.fetchone()
    if not is_author:
        return jsonify({"message": "Not a novel author"}), 401
    
    auth_header = request.headers.get('Authorization', None)

    if not auth_header:
        access_token = request.cookies.get('access_token') 
        header = {'Authorization': 'Bearer ' + access_token}
    else:
        access_token = auth_header.split()[1]
        header = {'Authorization': 'Bearer ' + access_token}

    api_resp = requests.delete(f'http://api:5000/api/uploads/novel/{novel_id}/episode/{episode}/', headers=header)

    if api_resp.status_code != 201:
        return jsonify({"message": "Episode images are not successfully deleted."}), 201

    cursor.execute('DELETE FROM episodes WHERE novel_id = %s AND episode = %s', 
                   (novel_id, episode))
    cursor.execute('UPDATE novels SET episode = episode - 1 WHERE novel_id = %s',
                   (novel_id, ))
    db.commit()
    return jsonify({"message": "Episode Successfully deleted"}), 201

@novels_bp.route('/<int:novel_id>/episode/<int:episode>/like', methods=['POST'])
@jwt_required(locations=["cookies", "headers"])
def like_episode(novel_id, episode):
    db = get_db()
    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM like_episode_table WHERE user_id = %s AND novel_id = %s AND episode = %s', 
                   (current_user, novel_id, episode))
    
    try: 
        is_like = cursor.fetchone()["is_like"]
    except TypeError: # like
        cursor.execute('INSERT INTO like_episode_table (is_like, user_id, novel_id, episode) VALUES (%s, %s, %s, %s)', 
                       (True, current_user, novel_id, episode))
        cursor.execute('UPDATE episodes SET recommendations = recommendations + 1 WHERE novel_id = %s AND episode = %s', 
                       (novel_id, episode))
        db.commit()
        return jsonify({"message": "Successfully liked!"}), 201

    if is_like: # cancel like
        cursor.execute('DELETE FROM like_episode_table WHERE user_id = %s AND novel_id = %s AND episode = %s', 
                       (current_user, novel_id, episode))
        cursor.execute('UPDATE episodes SET recommendations = recommendations - 1 WHERE novel_id = %s AND episode = %s', 
                       (novel_id, episode))
        db.commit()
        return jsonify({"message": "like successfully canceled!"}), 201
    else: # dislike to like
        cursor.execute('UPDATE like_episode_table SET is_like = TRUE WHERE user_id = %s AND novel_id = %s AND episode = %s', 
                       (current_user, novel_id, episode))
        cursor.execute('UPDATE episodes SET recommendations = recommendations + 1, dislikes = dislikes - 1 WHERE novel_id = %s AND episode = %s', 
                       (novel_id, episode))
        db.commit()
        return jsonify({"message": "Successfully liked!"}), 201

@novels_bp.route('/<int:novel_id>/episode/<int:episode>/dislike', methods=['POST'])
@jwt_required(locations=["cookies", "headers"])
def dislike_episode(novel_id, episode):
    db = get_db()
    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM like_episode_table WHERE user_id = %s AND novel_id = %s AND episode = %s', 
                   (current_user, novel_id, episode))

    try: 
        is_like = cursor.fetchone()["is_like"]
    except TypeError: # dislike
        cursor.execute('INSERT INTO like_episode_table (is_like, user_id, novel_id, episode) VALUES (%s, %s, %s, %s)', 
                       (False, current_user, novel_id, episode))
        cursor.execute('UPDATE episodes SET dislikes = dislikes + 1 WHERE novel_id = %s AND episode = %s', 
                       (novel_id, episode))
        db.commit()
        return jsonify({"message": "Successfully disliked!"}), 201
    
    if is_like: # like to dislike
        cursor.execute('UPDATE like_episode_table SET is_like = FALSE WHERE user_id = %s AND novel_id = %s AND episode = %s', 
                       (current_user, novel_id, episode))
        cursor.execute('UPDATE episodes SET dislikes = dislikes + 1, recommendations = recommendations - 1 WHERE novel_id = %s AND episode = %s', 
                       (novel_id, episode))
        db.commit()
        return jsonify({"message": "Successfully disliked!"}), 201
    else: # cancel dislike
        cursor.execute('DELETE FROM like_episode_table WHERE user_id = %s AND novel_id = %s AND episode = %s', 
                       (current_user, novel_id, episode))
        cursor.execute('UPDATE episodes SET dislikes = dislikes - 1 WHERE novel_id = %s AND episode = %s', 
                       (novel_id, episode))
        db.commit()
        return jsonify({"message": "dislike successfully canceled!"}), 201

@novels_bp.route('/<int:novel_id>/notice/<int:number>', methods=['GET'])
@jwt_required()
def get_novel_notice(novel_id, number):
    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute('SELECT max(num) FROM notice WHERE novel_id = %s', 
                   (novel_id,))
    max_number = cursor.fetchone()['max(num)']
    is_last = True if max_number == number else False
    cursor.execute('SELECT * FROM notice WHERE novel_id = %s AND num = %s',
                   (novel_id, number))
    novel_notice = cursor.fetchone()

    if novel_notice:
        cursor.execute('UPDATE notice SET views = views + 1 WHERE novel_id = %s AND num = %s', 
                    (novel_id, number))
        db.commit()

    novel_notice['is_last'] = is_last
    return jsonify({"notice": novel_notice}), 201

@novels_bp.route('/<int:novel_id>/notice', methods=['GET'])
@jwt_required()
def get_novel_notices(novel_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM notice WHERE novel_id = %s', 
                   (novel_id,))
    notice_list = cursor.fetchall()
    return jsonify({"notice_list": notice_list}), 201

@novels_bp.route('/<int:novel_id>/notice', methods=['POST'])
@jwt_required()
def upload_novel_notice(novel_id):
    db = get_db()
    current_user = get_jwt_identity()
    data = request.get_json()
    cursor = db.cursor(dictionary=True)

    cursor.execute('SELECT * FROM novels WHERE novel_id = %s AND author_id = %s', 
                   (novel_id, current_user))
    is_author = cursor.fetchone()
    if not is_author:
        return jsonify({"message": "Not a novel author"}), 401
    
    cursor.execute('SELECT max(num) FROM notice WHERE novel_id = %s', (novel_id,))
    upload_number = cursor.fetchone()['max(num)']

    if not upload_number: upload_number = 1

    auth_header = request.headers.get('Authorization', None)
    access_token = auth_header.split()[1]
    upload_notice_images_to_api(novel_id, upload_number, access_token, data['content'])

    def replace_img_tags(data):
        img_tags = re.findall(r'<img src="data:image/(\w+);base64,([^"]+)">', data)
        new_data = data

        for i, (ext, base64_data) in enumerate(img_tags, start=1):
            new_url = f"https://webnovelarchive1.s3.amazonaws.com/notice_image/{novel_id}/{upload_number}/{i}.{ext}"
            img_tag = f'<img src="data:image/{ext};base64,{base64_data}">'
            new_tag  = f"<img src='{new_url}'>"
            new_data = new_data.replace(img_tag, new_tag)

        return new_data
    
    cursor.execute('INSERT INTO notice (novel_id, num, title, content, author_note, author_id) VALUES (%s, %s, %s, %s, %s, %s)', 
                   (novel_id, upload_number, data['title'], replace_img_tags(data['content']), data['author_note'], current_user))
    db.commit()
    return jsonify({"message": "Successfully uploaded."}), 201

@novels_bp.route('/<int:novel_id>/notice/<int:number>', methods=['PUT'])
@jwt_required()
def edit_novel_notice(novel_id, number):
    db = get_db()
    current_user = get_jwt_identity()
    data = request.get_json()
    cursor = db.cursor(dictionary=True)

    cursor.execute('SELECT * FROM novels WHERE novel_id = %s AND author_id = %s', 
                   (novel_id, current_user))
    is_author = cursor.fetchone()
    if not is_author:
        return jsonify({"message": "Not a novel author"}), 401
    
    cursor.execute('SELECT max(num) FROM notice WHERE novel_id = %s', (novel_id,))

    auth_header = request.headers.get('Authorization', None)
    access_token = auth_header.split()[1]
    upload_notice_images_to_api(novel_id, number, access_token, data['content'])

    def replace_img_tags(data):
        img_tags = re.findall(r'<img src="data:image/(\w+);base64,([^"]+)">', data)
        new_data = data

        for i, (ext, base64_data) in enumerate(img_tags, start=1):
            new_url = f"https://webnovelarchive1.s3.amazonaws.com/notice_image/{novel_id}/{number}/{i}.{ext}"
            img_tag = f'<img src="data:image/{ext};base64,{base64_data}">'
            new_data = new_data.replace(img_tag, new_url)

        return new_data
    
    cursor.execute('UPDATE notice SET title = %s, content = %s, author_note = %s WHERE novel_id = %s AND num = %s', 
                   (data['title'], replace_img_tags(data['content']), data['author_note'], novel_id, number))
    db.commit()
    return jsonify({"message": "Successfully uploaded."}), 201

@novels_bp.route('/<int:novel_id>/notice/<int:number>', methods=['DELETE'])
@jwt_required()
def delete_novel_notice(novel_id, number):
    db = get_db()
    current_user = get_jwt_identity()
    cursor = db.cursor()

    cursor.execute('SELECT * FROM novels WHERE novel_id = %s AND author_id = %s', 
                   (novel_id, current_user))
    is_author = cursor.fetchone()
    if not is_author:
        return jsonify({"message": "Not a novel author"}), 401
    
    cursor.execute('DELETE FROM notice WHERE novel_id = %s AND num = %s', 
                   (novel_id, number))
    
    db.commit()
    return jsonify({"message": "Successfully deleted."}), 201

@novels_bp.route('/<int:novel_id>/notice/<int:number>/like', methods=['POST'])
@jwt_required(locations=["cookies", "headers"])
def like_notice(novel_id, number):
    db = get_db()
    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM like_notice_table WHERE user_id = %s AND novel_id = %s AND num = %s',
                   (current_user, novel_id, number))

    try:
        is_like = cursor.fetchone()["is_like"]
    except TypeError: # like
        cursor.execute('INSERT INTO like_notice_table (is_like, user_id, novel_id, num) VALUES (%s, %s, %s, %s)',
                       (True, current_user, novel_id, number))
        cursor.execute('UPDATE notice SET recommendations = recommendations + 1 WHERE novel_id = %s AND num = %s',
                       (novel_id, number))
        db.commit()
        return jsonify({"message": "Successfully liked!"}), 201

    if is_like: # cancel like
        cursor.execute('DELETE FROM like_notice_table WHERE user_id = %s AND novel_id = %s AND num = %s',
                       (current_user, novel_id, number))
        cursor.execute('UPDATE notice SET recommendations = recommendations - 1 WHERE novel_id = %s AND num = %s',
                       (novel_id, number))
        db.commit()
        return jsonify({"message": "like successfully canceled!"}), 201
    else:
        cursor.execute('UPDATE like_notice_table SET is_like = TRUE WHERE user_id = %s AND novel_id = %s AND num = %s',
                       (current_user, novel_id, number))
        cursor.execute('UPDATE notice SET recommendations = recommendations + 1, dislike = dislike - 1 WHERE novel_id = %s AND num = %s',
                       (novel_id, number))
        db.commit()
        return jsonify({"message": "Successfully liked!"}), 201

@novels_bp.route('/<int:novel_id>/notice/<int:number>/dislike', methods=['POST'])
@jwt_required(locations=["cookies", "headers"])
def dislike_notice(novel_id, number):
    db = get_db()
    current_user = get_jwt_identity()
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM like_notice_table WHERE user_id = %s AND novel_id = %s AND num = %s',
                   (current_user, novel_id, number))

    try:
        is_like = cursor.fetchone()["is_like"]
    except TypeError: # dislike
        cursor.execute('INSERT INTO like_notice_table (is_like, user_id, novel_id, num) VALUES (%s, %s, %s, %s)',
                       (False, current_user, novel_id, number))
        cursor.execute('UPDATE notice SET dislike = dislike + 1 WHERE novel_id = %s AND num = %s',
                       (novel_id, number))
        db.commit()
        return jsonify({"message": "Successfully disliked!"}), 201

    if is_like: # like to dislike
        cursor.execute('UPDATE like_notice_table SET is_like = FALSE WHERE user_id = %s AND novel_id = %s AND num = %s',
                       (current_user, novel_id, number))
        cursor.execute('UPDATE notice SET dislike = dislike + 1, recommendations = recommendations - 1 WHERE novel_id = %s AND num = %s',
                       (novel_id, number))
        db.commit()
        return jsonify({"message": "Successfully disliked!"}), 201
    else: # cancel dislike
        cursor.execute('DELETE FROM like_notice_table WHERE user_id = %s AND novel_id = %s AND num = %s',
                       (current_user, novel_id, number))
        cursor.execute('UPDATE notice SET dislike = dislike - 1 WHERE novel_id = %s AND num = %s',
                       (novel_id, number))
        db.commit()
        return jsonify({"message": "dislike successfully canceled!"}), 201
    
    