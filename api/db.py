import mysql.connector
import redis
from flask import g, current_app
import boto3

def get_db():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host='db',
            port='3306',
            user='root', 
            password='1234', 
            database='web_novel' 
        )
    return g.db

def get_redis():
    if 'redis' not in g:
        g.redis = redis.StrictRedis(
            host='redis', 
            port=6379, 
            db=0
        )
    return g.redis

def get_aws_s3_client():
    if 's3' not in g:
        g.s3 = boto3.client(
            's3',
            aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY'],
            region_name='ap-northeast-2'
        )
    return g.s3

def init_db():
    db = get_db()
    cursor = db.cursor()

    cursor.execute('SHOW TABLES;')
    tables = cursor.fetchall()
    if tables: return
    try:
        with current_app.open_resource('schema.sql', mode='r') as f:
            sql_commands = f.read().split(';')
            for command in sql_commands:
                if command.strip():
                    cursor.execute(command)
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        cursor.close()
        db.close()

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_app(app):
    app.teardown_appcontext(close_db)
