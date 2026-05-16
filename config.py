import os

from dotenv import load_dotenv


load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    INIT_DB_POOL = os.getenv('INIT_DB_POOL', 'true').lower() == 'true'
    DB_PARAMS = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 5432)),
        'dbname': os.getenv('DB_NAME', 'family_tree'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres'),
    }
