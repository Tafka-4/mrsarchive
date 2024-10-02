"""
파일 분할 해야하는데,,,
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, g, jsonify
from flask_jwt_extended import jwt_required
from flask_jwt_extended import create_access_token
from flask_jwt_extended import get_jwt
from flask_jwt_extended import set_access_cookies
from flask_jwt_extended import set_refresh_cookies
from flask_jwt_extended import unset_jwt_cookies
from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended.exceptions import NoAuthorizationError

from jwt import ExpiredSignatureError

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from utils import *

import requests
import redis
import time

API = "http://api:5000"
REQUEST_LIMIT = 100
TIME_WINDOW = 60  # seconds
BAN_TIME = 300  # seconds

main = Blueprint('main', __name__)

def get_redis():
    if 'redis' not in g:
        g.redis = redis.ConnectionPool(
            host='redis', 
            port=6379, 
            db=0
        )
    return redis.Redis(connection_pool=g.redis)

def is_rate_limited(ip):
    redis_client = get_redis()
    current_time = int(time.time())
    key = f"rate_limit:{ip}"
    ban_key = f"ban:{ip}"

    if redis_client.exists(ban_key):
        return True

    request_times = redis_client.lrange(key, 0, -1)
    request_times = [int(rt) for rt in request_times]

    request_times = [rt for rt in request_times if current_time - rt < TIME_WINDOW]
    redis_client.delete(key)
    for rt in request_times:
        redis_client.rpush(key, rt)

    if len(request_times) >= REQUEST_LIMIT:
        redis_client.setex(ban_key, BAN_TIME, 'banned')
        redis_client.delete(key)
        return True

    redis_client.rpush(key, current_time)
    return False

@main.before_request
def check_rate_limit():
    # BLOCKED!
    ip = request.remote_addr
    if is_rate_limited(ip):
        return None

@main.errorhandler(NoAuthorizationError)
def handle_auth_error(e):
    return redirect(url_for('main.logout'))

@main.errorhandler(ExpiredSignatureError)
def handle_auth_error(e):
    try:
        jwt_required(refresh=True)(lambda: None)()
    except Exception:
        refresh_token = request.cookies.get('refresh_token')
        if refresh_token:
            try:
                api_resp = requests.post(
                    API + '/api/users/refresh', 
                    json={'refresh': refresh_token}, 
                    headers={'Authorization': 'Bearer ' + refresh_token})

                if api_resp.status_code == 201:
                    new_access_token = api_resp.json().get('access_token')
                    if new_access_token:
                        resp = make_response(redirect(request.referrer or url_for('main.index')))
                        set_access_cookies(resp, new_access_token)
                        return resp
                else:
                    raise Exception
            except Exception:
                return redirect(url_for('main.logout'))
        else:
            return redirect(url_for('main.logout'))
    # Ensure a valid response is returned in all cases
    return redirect(url_for('main.logout'))  # Or any appropriate response

    
@main.route('/', methods=['GET'])
@jwt_required(optional=True, locations=["cookies"])
def index(): # should be cleaned...
    if get_jwt_identity() is None: return redirect(url_for('main.logout'))
    page = request.args.get('page', default=1, type=int)
    search_query = request.args.get('search', default='', type=str)

    access_token = request.cookies.get('access_token')
    header = {'Authorization': 'Bearer ' + access_token}

    if search_query != '':
        param = {'keyword': search_query}
        api_resp = requests.get(API + '/api/novels/search-novel-count', params=param, headers=header)
        count = api_resp.json()['count']
        total_page = count // 10 + 1

        if page > total_page: 
            page = total_page
        param = {'start': (page - 1) * 10 + 1, 'amount': 10}
        if page == total_page: 
            param = {'start': (page - 1) * 10 + 1, 'amount': count - (count // 10) * 10}

        param = {'keyword': search_query} | param

        api_resp = requests.get(API + '/api/novels/search-novel', params=param, headers=header)
        if api_resp.status_code != 201:
            return render_template('index.html', novels=[], page=page)
        novels = api_resp.json()['novels']
        
    else:
        api_resp = requests.get(API + '/api/novels/count', headers=header)
        count = api_resp.json()['count']

        total_page = count // 10 + 1

        if page > total_page: 
            page = total_page
        param = {'start': (page - 1) * 10 + 1, 'amount': 10}
        if page == total_page: 
            param = {'start': (page - 1) * 10 + 1, 'amount': count - (count // 10) * 10}

        api_resp = requests.get(API + '/api/novels/', params=param, headers=header)
        if api_resp.status_code != 201:
            return render_template('index.html', novels=[], page=page)
        novels = api_resp.json()['novels']

    api_resp = requests.post(API + '/api/novels/set', headers=header, json=novels)

    if api_resp.status_code != 201:
        return make_response(redirect(url_for('main.index')))
    
    novels = api_resp.json()["novels"]

    for novel in novels:
        novel["is_author"] = True if novel["author_id"] == get_jwt_identity() else False

    return render_template('index.html', novels=novels, page=page, total_page=total_page)

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = {
            'email': request.form['email'],
            'password': request.form['password'],
            'nickname': request.form['username']
        }
        response = requests.post(API + '/api/users/register', json=data)
        if response.status_code == 201:
            flash('Registration successful!', 'success')
            return redirect(url_for('main.login'))
        else:
            flash('Registration failed.')
    return render_template('register.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        api_resp = requests.post(API + '/api/users/login', json={'email': email, 'password': password})
        if api_resp.status_code == 409:
            flash('존재하지 않는 계정이거나, 이메일 또는 비밀번호가 틀렸습니다.')
        if api_resp.status_code == 201:
            resp = make_response(redirect(url_for('main.index')))
            tokens = api_resp.json()
            set_access_cookies(response=resp, encoded_access_token=tokens['access_token'])
            set_refresh_cookies(response=resp, encoded_refresh_token=tokens['refresh_token'])
            return resp
        else:
            return jsonify({"data": api_resp.json()})
    return render_template('login.html')

@main.route('/logout', methods=['GET'])
def logout(): # need to fix
    resp = make_response(redirect(url_for('main.login')))
    access_token = request.cookies.get('access_token')

    if not access_token:
        for cookie in request.cookies:
            resp.delete_cookie(cookie)
        return resp
    
    unset_jwt_cookies(response=resp)

    for cookie in request.cookies:
        resp.delete_cookie(cookie)
    return resp

@main.route('/view/episode/<int:novel_id>/<int:episode>', methods=['GET'])
@jwt_required(locations=["cookies"])
def novel_episode_view(novel_id, episode):
    access_token = request.cookies.get('access_token')
    headers = {'Authorization': 'Bearer ' + access_token}

    content = requests.get(API + f'/api/novels/{novel_id}/episode/{episode}', headers=headers)
    try:
        content = content.json()["novel_text"] | {"type": 'episode'}
        sanitize_html(content["content"])
    except:
        return make_response(redirect(url_for('main.index')))
    return render_template('viewer.html', content=content)

@main.route('/view/notice/<int:novel_id>/<int:notice_num>', methods=['GET'])
@jwt_required(locations=["cookies"])
def novel_notice_view(novel_id, notice_num):
    access_token = request.cookies.get('access_token')
    header = {'Authorization': 'Bearer ' + access_token}

    content = requests.get(API + f'/api/novels/{novel_id}/notice/{notice_num}', headers=header)
    try:
        content = content.json()["notice"] | {"type": 'notice'}
        sanitize_html(content["content"])
    except:
        return make_response(redirect(url_for('main.index')))
    return render_template('viewer.html', content=content)

@main.route('/novel/<int:novel_id>/comment/notice/<int:number>', methods=['GET'])
@jwt_required(locations=["cookies"])
def novel_notice_comment(novel_id, number):
    access_token = request.cookies.get('access_token')
    header = {'Authorization': 'Bearer ' + access_token}
    api_resp = requests.get(API + f'/api/comments/notice-comment/{novel_id}/{number}', headers=header)
    if api_resp.status_code != 201:
        return make_response(redirect(url_for('main.novel_notice_view', novel_id=novel_id, notice_num=number)))
    comments = api_resp.json()['comments']

    return render_template('novel_notice_comment.html', comments=comments)

@main.route('/novel/<int:novel_id>/comment/episode/<int:episode>', methods=['GET'])
@jwt_required(locations=["cookies"])
def novel_episode_comment(novel_id, episode):
    access_token = request.cookies.get('access_token')
    header = {'Authorization': 'Bearer ' + access_token}
    api_resp = requests.get(API + f'/api/comments/episodes-comment/{novel_id}/{episode}', headers=header)
    if api_resp.status_code != 201:
        return make_response(redirect(url_for('main.novel_episode_view', novel_id=novel_id, episode=episode)))
    comments = api_resp.json()['comments']

    return render_template('novel_episode_comment.html', comments=comments)


@main.route('/novel/<int:novel_id>/comment', methods=['GET', 'POST'])
@jwt_required(locations=["cookies"])
def novel_comment(novel_id):
    current_user = get_jwt_identity()
    return render_template('novel_comment.html', user_id=current_user, novel_id=novel_id)

@main.route('/novel/<int:novel_id>', methods=['GET'])
@jwt_required(locations=["cookies"])
def novel(novel_id):
    page = request.args.get('page', default=1, type=int)
    current_user = get_jwt_identity()
    access_token = request.cookies.get('access_token')
    header = {'Authorization': 'Bearer ' + access_token}
    
    api_resp = requests.get(API + f'/api/novels/get-episodes/{novel_id}', headers=header)
    count = api_resp.json()["episode"]
    
    total_page = count // 20 + 1
    if page > total_page: page = total_page
    param = {'start': (page - 1) * 20 + 1, 'amount': 20}
    if page == total_page:
        param = {'start': (page - 1) * 20 + 1, 'amount': count - (count // 20) * 20}
    api_resp = requests.get(API + f'/api/novels/{novel_id}', headers=header, params=param)

    if api_resp.status_code != 201:
        return make_response(redirect(url_for('main.index')))
    
    novel = [api_resp.json()["novel"],]
    
    api_resp = requests.post(API + f'/api/novels/set', headers=header, json=novel)
    if api_resp.status_code != 201: return make_response(redirect(url_for('main.index')))
    else: novel = api_resp.json()["novels"]

    api_resp = requests.get(API + f'/api/novels/{novel_id}/notice', headers=header)
    if api_resp.status_code != 201: return make_response(redirect(url_for('main.index')))
    else: notices = api_resp.json()["notice_list"]

    if novel[0]["author_id"] == current_user: is_author = True
    else: is_author = False
    
    return render_template('novel.html', novel=novel[0], is_author=is_author, total_pages=total_page, notices=notices, page=page)

@main.route('/novel/upload/', methods=['GET', 'POST'])
@jwt_required(locations=["cookies"])
def novel_upload():
    return render_template('novel_upload.html')

@main.route('/novel/<int:novel_id>/episode/upload', methods=['GET', 'POST'])
@jwt_required(locations=["cookies"])
def novel_episode_upload(novel_id):
    access_token = request.cookies.get('access_token')
    header = {'Authorization': 'Bearer ' + access_token}
    current_user = get_jwt_identity()

    api_resp = requests.get(API + f'/api/novels/{novel_id}', headers=header)
    novel = api_resp.json()["novel"]

    if current_user != novel["author_id"]: return make_response(redirect(url_for('main.index')))

    if request.method == 'POST':
        data = {
            'title': request.form['title'],
            'content': request.form['content'],
            'author_note': request.form['author_note']
        }

        api_resp = requests.post(API + f'/api/novels/{novel_id}/episode', headers=header, json=data)

        if api_resp.status_code != 201:
            flash("Upload failed.")
            resp = make_response(redirect(url_for('main.novel_episode_upload', novel_id=novel_id)))
            return resp

        flash("Upload successfully.")
        resp = make_response(redirect(url_for('main.novel', novel_id=novel_id)))
        return resp
    
    return render_template('novel_episode_upload.html', novel=novel, edit=None, notice=False)

@main.route('/novel/<int:novel_id>/episode/<int:episode>/edit', methods=['GET', 'POST'])
@jwt_required(locations=["cookies"])
def novel_episode_edit(novel_id, episode):
    access_token = request.cookies.get('access_token')
    header = {'Authorization': 'Bearer ' + access_token}
    current_user = get_jwt_identity()

    api_resp = requests.get(API + f'/api/novels/{novel_id}', headers=header)
    novel = api_resp.json()["novel"]
    api_resp = requests.get(API + f'/api/novels/{novel_id}/episode/{episode}', headers=header)
    episode_data = api_resp.json()["novel_text"]

    if current_user != novel["author_id"]: return make_response(redirect(url_for('main.index')))

    if request.method == 'POST':
        data = {
            'title': request.form['title'],
            'content': request.form['content'],
            'author_note': request.form['author_note']
        }
        
        api_resp = requests.put(API + f'/api/novels/{novel_id}/episode/{episode}', headers=header, json=data)
        if api_resp.status_code != 201:
            flash("Upload failed.")
            resp = make_response(redirect(url_for('main.novel_episode_edit', novel_id=novel_id, episode=episode)))
            return resp
            
        flash("Upload successfully.")
        resp = make_response(redirect(url_for('main.novel', novel_id=novel_id)))
        return resp
    
    return render_template('novel_episode_upload.html', novel=novel, edit=episode_data, notice=False)

@main.route('/novel/<int:novel_id>/notice/upload', methods=['GET', 'POST'])
@jwt_required(locations=["cookies"])
def novel_notice_upload(novel_id):
    access_token = request.cookies.get('access_token')
    header = {'Authorization': 'Bearer ' + access_token}
    current_user = get_jwt_identity()

    api_resp = requests.get(API + f'/api/novels/{novel_id}', headers=header)

    novel = api_resp.json()["novel"]

    if current_user != novel["author_id"]: return make_response(redirect(url_for('main.index')))

    if request.method == 'POST':
        data = {
            'title': request.form['title'],
            'content': request.form['content'],
            'author_note': request.form['author_note']
        }

        api_resp = requests.post(API + f'/api/novels/{novel_id}/notice', headers=header, json=data)

        if api_resp.status_code != 201:
            flash("Upload failed.")
            resp = make_response(redirect(url_for('main.novel_notice_upload', novel_id=novel_id)))
            return resp

        flash("Upload successfully.")
        resp = make_response(redirect(url_for('main.novel', novel_id=novel_id)))
        return resp
    
    return render_template('novel_episode_upload.html', novel=novel, edit=None, notice=True)

@main.route('/novel/<int:novel_id>/notice/<int:number>/edit', methods=['GET', 'POST'])
@jwt_required(locations=["cookies"])
def novel_notice_edit(novel_id, number):
    access_token = request.cookies.get('access_token')
    header = {'Authorization': 'Bearer ' + access_token}
    current_user = get_jwt_identity()

    api_resp = requests.get(API + f'/api/novels/{novel_id}', headers=header)
    novel = api_resp.json()["novel"]
    api_resp = requests.get(API + f'/api/novels/{novel_id}/notice/{number}', headers=header)
    edit = api_resp.json()["notice"]

    if current_user != novel["author_id"]: return make_response(redirect(url_for('main.index')))

    if request.method == 'POST':
        data = {
            'title': request.form['title'],
            'content': request.form['content'],
            'author_note': request.form['author_note']
        }
        
        api_resp = requests.put(API + f'/api/novels/{novel_id}/notice/{number}', headers=header, json=data)
        if api_resp.status_code != 201:
            flash("Upload failed.")
            resp = make_response(redirect(url_for('main.novel_notice_edit', novel_id=novel_id, number=number)))
            return resp
            
        flash("Upload successfully.")
        resp = make_response(redirect(url_for('main.novel', novel_id=novel_id)))
        return resp
    
    return render_template('novel_episode_upload.html', novel=novel, edit=edit, notice=True)

@main.route('/mypage', methods=['GET', 'POST'])
@jwt_required(locations=["cookies"])
def mypage():
    access_token = request.cookies.get('access_token')
    header = {'Authorization': 'Bearer ' + access_token}
    
    api_resp = requests.get(API + '/api/users/', headers=header)
    user = api_resp.json()["users"]

    return render_template("mypage.html", user=user)