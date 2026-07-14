"""热点榜单路由"""
from flask import Blueprint, request, jsonify, session
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import config
from services.user_service import user_service
from services.trending_service import trending_service
from utils.decorators import login_required


trending_bp = Blueprint('trending', __name__, url_prefix='/api/trending')


@trending_bp.route("/school", methods=["GET"])
@login_required
def get_school_trending():
    """获取用户学校的昨日热点榜单"""
    current_user_id = session.get('user_id')
    user, _ = user_service.get_user_and_profession(current_user_id)
    
    if not user or not user.school:
        return jsonify({
            "status": "error",
            "content": "User or school not found"
        }), 404
    
    try:
        limit = int(request.args.get("limit", str(config.TRENDING_BOARD_SIZE)))
    except ValueError:
        limit = config.TRENDING_BOARD_SIZE
    
    # 限制范围
    limit = max(1, min(limit, 50))
    
    # 根据用户时区计算“昨日”窗口（本地昨日 00:00-24:00 转成 UTC），供服务使用
    tz_name = (request.args.get("tz") or "").strip()
    tz_offset = request.args.get("tz_offset")
    start_utc = end_utc = None
    try:
        now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
        if tz_name:
            try:
                tz = ZoneInfo(tz_name)
                now_local = now_utc.astimezone(tz)
                # 本地昨天起止
                today_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
                start_local = today_local - timedelta(days=1)
                end_local = today_local
                start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
                end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                tz_name = ""
        if not tz_name and tz_offset is not None:
            minutes = int(tz_offset)
            # 先得到本地当前时间（通过偏移近似，无 DST 语义）
            now_local_naive = (now_utc - timedelta(minutes=minutes)).replace(tzinfo=None)
            today_local_naive = now_local_naive.replace(hour=0, minute=0, second=0, microsecond=0)
            start_local_naive = today_local_naive - timedelta(days=1)
            # 转回 UTC（本地 + offset = UTC）
            start_utc = start_local_naive + timedelta(minutes=minutes)
            end_utc = today_local_naive + timedelta(minutes=minutes)

        trending = trending_service.get_school_trending(
            school=user.school,
            limit=limit,
            start_utc=start_utc,
            end_utc=end_utc,
        )
        
        return jsonify({
            "status": "success",
            "school": user.school,
            "trending": trending,
            "count": len(trending)
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "content": str(e)
        }), 400
