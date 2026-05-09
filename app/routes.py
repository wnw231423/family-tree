from flask import Blueprint, current_app, render_template
from app.db import get_db

routes_bp = Blueprint('routes', __name__)


@routes_bp.route('/')
def index():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM members")
    count = cur.fetchone()[0]
    cur.close()
    return render_template('index.html', member_count=count)
