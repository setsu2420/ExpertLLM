"""语义热点问句路由，从 Redis 读取 Top 问句列表。"""
from flask import Blueprint, jsonify

from utils.decorators import login_required
from utils.redis_client import get_redis, safe_json_loads


question_trending_bp = Blueprint('question_trending', __name__, url_prefix='/api/trending')


@question_trending_bp.route('/questions', methods=['GET'])
@login_required
def get_question_trending():
    r = get_redis()
    if not r:
        return jsonify({"status": "success", "trending": [], "count": 0})
    raw = r.get('question_trending_top')
    if not raw:
        return jsonify({"status": "success", "trending": [], "count": 0})
    data = safe_json_loads(raw) or []
    if not isinstance(data, list):
        data = []
    return jsonify({"status": "success", "trending": data, "count": len(data)})
