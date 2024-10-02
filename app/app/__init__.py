from flask import Flask, g
from flask_wtf.csrf import CSRFProtect
import datetime
from bs4 import BeautifulSoup
from .routes import main
from .extensions import jwt
import os

def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY').encode()
    app.config['JSON_AS_ASCII'] = False
    app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token'
    app.config['JWT_REFRESH_COOKIE_NAME'] = 'refresh_token'
    app.config["JWT_SESSION_COOKIE"] = "session_cookie"
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(hours=4)
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = datetime.timedelta(days=2)
    app.config['JWT_COOKIE_CSRF_PROTECT'] = True
    app.config["JWT_COOKIE_SECURE"] = False
    app.config["JWT_COOKIE_DOMAIN"] = None
    app.config["JWT_ACCESS_COOKIE_PATH"] = '/'
    app.config["JWT_COOKIE_SAMESITE"] = None
    app.config['JWT_CSRF_IN_COOKIES'] = True
    app.config["JWT_ACCESS_CSRF_COOKIE_NAME"] = "csrf_access_token"
    
    csrf = CSRFProtect(app)

    @app.teardown_appcontext
    def close_redis_connection(exception=None):
        redis_conn = g.pop('redis', None)
        if redis_conn is not None:
            redis_conn.disconnect()

    jwt.init_app(app)
    csrf.init_app(app)
    
    app.register_blueprint(main)

    return app
