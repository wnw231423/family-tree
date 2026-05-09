import time
import psycopg2
from psycopg2 import pool
from flask import current_app, g

connection_pool = None


def init_pool(app):
    global connection_pool
    db_params = app.config['DB_PARAMS']
    retries = 10
    while retries > 0:
        try:
            connection_pool = pool.ThreadedConnectionPool(1, 10, **db_params)
            app.logger.info("数据库连接池初始化成功")
            return
        except psycopg2.OperationalError:
            retries -= 1
            if retries == 0:
                raise
            app.logger.warning(f"数据库未就绪，{retries} 次重试……")
            time.sleep(2)


def get_db():
    if 'db' not in g:
        g.db = connection_pool.getconn()
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        connection_pool.putconn(db)
