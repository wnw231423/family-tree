import time
import psycopg2
from psycopg2 import pool
from psycopg2.extensions import TRANSACTION_STATUS_IDLE
from flask import g

connection_pool = None


def init_pool(app):
    global connection_pool
    db_params = app.config['DB_PARAMS']
    retries = 10
    while retries > 0:
        try:
            connection_pool = pool.ThreadedConnectionPool(1, 10, **db_params)
            app.logger.info("Database connection pool initialized.")
            return
        except psycopg2.OperationalError:
            retries -= 1
            if retries == 0:
                raise
            app.logger.warning(
                "Database is not ready. Retrying %s more time(s).", retries
            )
            time.sleep(2)


def get_db():
    if 'db' not in g:
        g.db = connection_pool.getconn()
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        if db.get_transaction_status() != TRANSACTION_STATUS_IDLE:
            db.rollback()
        connection_pool.putconn(db)
