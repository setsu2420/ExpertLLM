"""用户页面路由 - /user 及历史问答API"""
from flask import Blueprint, render_template, session, jsonify, request
from utils.decorators import login_required
import db_service
from services.user_service import user_service
import re

user_bp = Blueprint('user', __name__, url_prefix='')
@user_bp.route('/user', methods=['GET'])
@login_required
def user_page():
    current_user_id = session.get('user_id')
    return render_template('user.html', current_user_id=current_user_id)

# API: 获取当前用户历史问答（项目、问题、AI回答）
@user_bp.route("/user/history", methods=["GET"])
@login_required
def user_history():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"status": "error", "content": "未登录"}), 401
    # 获取所有项目及详细内容
    projects = db_service.load_history_summaries(user_id)
    detail_list = []
    for proj in projects:
        detail = db_service.load_history_detail(proj["record_id"], user_id=user_id)
        if detail:
            detail_list.append(detail)
    return jsonify({"status": "success", "projects": detail_list})

@user_bp.route('/api/user/profile', methods=['GET'])
@login_required
def get_profile():
    user_id = session.get('user_id')
    user = user_service.get_user_by_id(user_id)
    if not user:
        return jsonify({'status': 'error', 'content': '用户不存在'}), 404
    return jsonify({
        'status': 'success',
        'user': {
            'user_id': user.user_id,
            'school': user.school,
            'major': user.major,
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(user, 'created_at') and user.created_at else '',
        }
    })


# 新增：修改密码接口
@user_bp.route('/api/user/change-password', methods=['POST'])
@login_required
def change_password():
    user_id = session.get('user_id')
    user = user_service.get_user_by_id(user_id)
    if not user:
        return jsonify({'status': 'error', 'content': '用户不存在'}), 404
    data = request.json or {}
    old_password = data.get('old_password', '').strip()
    new_password = data.get('new_password', '').strip()
    if not old_password or not new_password:
        return jsonify({'status': 'error', 'content': '请输入原密码和新密码'}), 400
    from werkzeug.security import check_password_hash, generate_password_hash
    if not check_password_hash(user.password, old_password):
        return jsonify({'status': 'error', 'content': '原密码错误'}), 400
    # 禁止将新密码设置为与旧密码相同
    if old_password == new_password:
        return jsonify({'status': 'error', 'content': '新密码不能与原密码相同'}), 400
    # 新密码格式检查：不包含空白字符且不超过 128 字符
    if not re.match(r'^\S{1,128}$', new_password):
        return jsonify({'status': 'error', 'content': '新密码格式不正确，请不要包含空白字符，最长 128 字符'}), 400
    user.password = generate_password_hash(new_password)
    user_service.save_user(user)
    return jsonify({'status': 'success', 'content': '密码修改成功'})
