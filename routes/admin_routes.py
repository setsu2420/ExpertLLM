"""Admin routes: page, admin management, and projects query"""
from __future__ import annotations

from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for

from utils.decorators import login_required, admin_required
from services.admin_service import admin_service

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('', methods=['GET'])
def admin_page():
    current_user_id = session.get('user_id')
    if not current_user_id:
        return redirect(url_for('auth.login'))
    if not admin_service.is_admin(current_user_id):
        return redirect(url_for('index'))
    return render_template('admin.html', current_user_id=current_user_id)


@admin_bp.route('/api/status', methods=['GET'])
@login_required
def admin_status():
    current_user_id = session.get('user_id')
    try:
        return jsonify({
            "status": "success",
            "is_admin": admin_service.is_admin(current_user_id)
        })
    except Exception as e:
        return jsonify({"status": "error", "content": str(e)}), 400


@admin_bp.route('/api/admins', methods=['GET'])
@login_required
def list_admins():
    try:
        items = admin_service.list_admins()
        return jsonify({"status": "success", "admins": items})
    except Exception as e:
        return jsonify({"status": "error", "content": str(e)}), 400


@admin_bp.route('/api/admins', methods=['POST'])
@login_required
def add_admin():
    data = request.get_json(silent=True) or {}
    target_user_id = (data.get('user_id') or '').strip()
    level = int(data.get('level') or 1)
    password = (data.get('password') or '').strip()

    current_user_id = session.get('user_id')

    ok, msg = admin_service.add_admin(current_user_id, target_user_id, level, password)
    if not ok:
        return jsonify({"status": "error", "content": msg}), 400
    return jsonify({"status": "success", "content": msg})


@admin_bp.route('/api/projects', methods=['GET'])
@admin_required
def list_projects():
    try:
        limit = int(request.args.get('limit', '50') or 50)
    except Exception:
        limit = 50
    try:
        items = admin_service.list_projects(limit=limit)
        return jsonify({"status": "success", "projects": items})
    except Exception as e:
        return jsonify({"status": "error", "content": str(e)}), 400
