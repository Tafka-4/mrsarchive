
from flask import Flask, jsonify, request
from users.routes import users_bp
from novels.routes import novels_bp
from comments.routes import comments_bp
from novels.routes import novels_bp
from uploads.routes import uploads_bp
from extensions import jwt
from db import init_db, close_db, get_redis
import datetime
import os
import time

REQUEST_LIMIT = 300
TIME_WINDOW = 60  # seconds
BAN_TIME = 300  # seconds

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

def create_app():
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY').encode()
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(hours=4)
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = datetime.timedelta(days=2)
    app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token'
    app.config['JWT_REFRESH_COOKIE_NAME'] = 'refresh_token'
    app.config["JWT_SESSION_COOKIE"] = "session_cookie"
    app.config['JWT_COOKIE_CSRF_PROTECT'] = True
    app.config['JSON_AS_ASCII'] = False
    app.config['MAX_CONTENT_PATH'] = 16 * 1024 * 1024  # 16 MB limit

    app.config['AWS_ACCESS_KEY_ID'] = os.environ.get('AWS_ACCESS_KEY_ID')
    app.config['AWS_SECRET_ACCESS_KEY'] = os.environ.get('AWS_SECRET_ACCESS_KEY')

    jwt.init_app(app)

    # Register Blueprints
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(novels_bp, url_prefix='/api/novels')
    app.register_blueprint(comments_bp, url_prefx='/api/comments')
    app.register_blueprint(uploads_bp, url_prefix='/api/uploads')

    # Initialize the database
    with app.app_context():
        init_db()

    # Error Handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500

    @app.teardown_appcontext
    def teardown_db(exception):
        close_db(exception)

    @app.before_request
    def check_rate_limit():
        # BLOCKED!
        ip = request.remote_addr
        if is_rate_limited(ip):
            return jsonify({'error': 'Too much requests'})
        
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=False, port=5000)
