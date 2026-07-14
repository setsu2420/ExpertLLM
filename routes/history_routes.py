"""项目历史路由 - 保存、查询、删除历史记录"""
from flask import Blueprint, request, jsonify, session

import db_service
from models import Project, db
from models import Turn, Message_
import json
from services.chat_service import chat_service
from utils.decorators import login_required


history_bp = Blueprint('history', __name__, url_prefix='/api')


@history_bp.route("/save", methods=["POST"])
@login_required
def save_data():
    """保存项目数据"""
    current_user_id = session.get('user_id')
    data = request.json or {}
    
    record_id = (data.get("record_id") or "").strip()
    session_id = (data.get("session_id") or "").strip()
    
    username = data.get("username")
    project_name = data.get("project_name")
    expert_data = data.get("expert_data")
    
    # 如果没传 record_id，用 session_id 找
    if not record_id and session_id:
        with chat_service.record_lock:
            session_data = db_service.load_chat_session(session_id, user_id=current_user_id)
            if session_data:
                record_id = session_data.get("record_id")
            else:
                return jsonify({
                    "status": "error",
                    "content": "Session not found or forbidden"
                }), 404
            
            if not record_id:
                import uuid
                record_id = str(uuid.uuid4())
                # 不在这里命名，延迟到第一次对话时使用项目的创建时间命名
                db_service.ensure_project(record_id, user_id=current_user_id)
                db_service.link_session_to_project(session_id, record_id, user_id=current_user_id)
    
    if not record_id:
        return jsonify({
            "status": "error",
            "content": "Missing record_id/session_id"
        }), 400
    
    with chat_service.record_lock:
        project = Project.query.filter_by(
            project_id=record_id,
            user_id=current_user_id
        ).first()
        
        if project:
            project.username = username
            project.project_name = project_name
            project.expert_data = expert_data
            db.session.commit()
        else:
            return jsonify({
                "status": "error",
                "content": "Not found or forbidden"
            }), 404
    
    return jsonify({"status": "success", "id": record_id})


@history_bp.route("/history", methods=["GET"])
@login_required
def get_history():
    """获取历史记录列表"""
    current_user_id = session.get('user_id')
    return jsonify(db_service.load_history_summaries(current_user_id))


@history_bp.route("/history/detail", methods=["GET"])
@login_required
def get_history_detail():
    """获取历史记录详情"""
    current_user_id = session.get('user_id')
    record_id = (request.args.get("id") or "").strip()
    
    if not record_id:
        return jsonify({"status": "error", "content": "Missing id"}), 400
    
    rec = db_service.load_history_detail(record_id, user_id=current_user_id)
    if not rec:
        return jsonify({"status": "error", "content": "Not found"}), 404

    # 为兼容前端展示：标注每个 turn 中的响应是否为结构化 JSON（deep 模式）或纯文本（stream 模式）
    try:
        for turn in rec.get('turns', []):
            # responses: { model_key: [{role, content}, ...], ... }
            responses = turn.get('responses') or {}
            for mkey, arr in list(responses.items()):
                if isinstance(arr, list):
                    for r in arr:
                        content = (r.get('content') if isinstance(r, dict) else None) or ''
                        # 尝试解析为 JSON
                        try:
                            import json
                            parsed = json.loads(content)
                            # 标记为结构化结果
                            r['is_structured'] = True
                            r['parsed'] = parsed
                        except Exception:
                            # 非 JSON，标记为流式/纯文本
                            r['is_structured'] = False
                            r['raw'] = content


            # 同时尝试从 messages_ 表中读取深度模型的最终保存（若存在）
            try:
                turn_obj = Turn.query.filter_by(turn_id=turn.get('id')).first()
                if turn_obj:
                    msgs = Message_.query.filter_by(turn_id_fk=turn_obj.id, role='assistant').all()
                    if msgs:
                        parsed_msgs = []
                        for m in msgs:
                            entry = { 'model_key': m.model_key }
                            content = m.content or ''
                            entry['content'] = content
                            # 尝试将 content 解析为 JSON 结构，若成功则返回 parsed 字段并标注 is_structured
                            try:
                                parsed = json.loads(content)
                                entry['is_structured'] = True
                                entry['parsed'] = parsed
                            except Exception:
                                entry['is_structured'] = False
                                entry['raw'] = content
                            parsed_msgs.append(entry)
                        turn['_messages_'] = parsed_msgs
            except Exception:
                # 忽略数据库读取错误，保持向后兼容
                pass
    except Exception:
        # 容错：若处理失败，不阻塞原始数据返回
        pass

    return jsonify({"status": "success", "record": rec})


@history_bp.route("/history/delete", methods=["POST"])
@login_required
def delete_history():
    """删除历史记录"""
    current_user_id = session.get('user_id')
    data = request.json or {}
    record_id = data.get("id")
    
    with chat_service.record_lock:
        project = Project.query.filter_by(
            project_id=record_id,
            user_id=current_user_id
        ).first()
        
        if project:
            db.session.delete(project)
            db.session.commit()
            ok = True
        else:
            ok = False
    
    return jsonify({"status": "success" if ok else "error"}), (200 if ok else 500)


@history_bp.route("/history/rename", methods=["POST"])
@login_required
def rename_history():
    """重命名历史记录"""
    current_user_id = session.get('user_id')
    data = request.json or {}
    record_id = data.get("id")
    new_name = data.get("new_name")
    
    with chat_service.record_lock:
        project = Project.query.filter_by(
            project_id=record_id,
            user_id=current_user_id
        ).first()
        
        if project:
            project.project_name = new_name
            db.session.commit()
            ok = True
        else:
            ok = False
    
    return jsonify({"status": "success" if ok else "error"}), (200 if ok else 500)
