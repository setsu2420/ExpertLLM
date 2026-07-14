"""
数据库服务层 - 替代 data_manager 的数据库版本

提供与 data_manager 相同的接口，但使用 MySQL 数据库存储
支持多模型扩展，添加新模型无需修改数据库结构
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from models import db, Project, Session, Turn, Message, Message_, Thread, PublicMessage, PublicVote
from services import metrics


# =========================
# Session（用于上下文记忆）
# =========================

def create_chat_session(session_id: str | None = None, *, user_id: str | None = None) -> str:
    """创建新的聊天会话；若提供 session_id 则优先使用"""
    sid = session_id or str(uuid.uuid4())

    existing = Session.query.filter_by(session_id=sid).first()
    if existing:
        if user_id and existing.user_id and existing.user_id != user_id:
            raise ValueError("Session is owned by another user")
        return existing.session_id

    new_session = Session(session_id=sid, user_id=user_id)
    db.session.add(new_session)
    db.session.commit()
    metrics.record_db_query("create_chat_session")
    return sid


def load_chat_session(session_id: str, *, user_id: str | None = None) -> Optional[Dict]:
    """
    加载聊天会话及其所有对话历史
    
    返回格式与 data_manager 保持一致：
    {
        "id": session_id,
        "created_at": "...",
        "updated_at": "...",
        "record_id": "...",
        "threads": {model_key: [{role, content, timestamp}, ...]},
        "turns": [{id, timestamp, prompt, selected_models, responses}, ...]
    }
    """
    session = Session.query.filter_by(session_id=session_id).first()
    if not session:
        return None
    if user_id and session.user_id and session.user_id != user_id:
        return None
    if user_id and not session.user_id:
        session.user_id = user_id
        db.session.commit()
    
    # 获取项目ID（如果关联了项目）
    record_id = session.project_id or ""
    
    # 构建 threads（每个模型的对话历史）
    threads = {}
    thread_messages = Thread.query.filter_by(session_id_fk=session.id).order_by(Thread.sequence).all()
    for msg in thread_messages:
        if msg.model_key not in threads:
            threads[msg.model_key] = []
        threads[msg.model_key].append({
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    # 构建 turns（对话轮次）
    turns = []
    db_turns = Turn.query.filter_by(session_id_fk=session.id).order_by(Turn.created_at).all()
    for turn in db_turns:
        # 获取该轮次的所有模型响应
        responses = {}
        messages = Message.query.filter_by(turn_id_fk=turn.id).all()
        for msg in messages:
            if msg.model_key not in responses:
                responses[msg.model_key] = []
            responses[msg.model_key].append({
                "role": msg.role,
                "content": msg.content
            })
        
        turns.append({
            "id": turn.turn_id,
            "timestamp": turn.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "prompt": turn.prompt,
            "selected_models": turn.selected_models or [],
            "responses": responses
        })
    
    return {
        "id": session_id,
        "created_at": session.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": session.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        "created_at_iso": (session.created_at.isoformat() if session.created_at else None),
        "updated_at_iso": (session.updated_at.isoformat() if session.updated_at else None),
        "record_id": record_id,
        "threads": threads,
        "turns": turns
    }


def upsert_chat_turn(session: Dict, turn_id: str, prompt: str, selected_models=None, model_order=None):
    """
    创建或更新对话轮次
    
    Args:
        session: load_chat_session 返回的会话字典
        turn_id: 轮次ID
        prompt: 用户提问
        selected_models: 选择的模型列表
    """
    session_id = session.get("id")
    db_session = Session.query.filter_by(session_id=session_id).first()
    if not db_session:
        raise ValueError(f"Session not found: {session_id}")
    
    order_keys = None
    if isinstance(model_order, list):
        order_keys = model_order
    elif isinstance(selected_models, list):
        order_keys = [m.get("key") for m in selected_models if isinstance(m, dict) and m.get("key")]

    # 查找或创建 Turn
    turn = Turn.query.filter_by(session_id_fk=db_session.id, turn_id=turn_id).first()
    if turn:
        turn.prompt = prompt
        if selected_models is not None:
            turn.selected_models = selected_models
        if order_keys is not None:
            turn.model_order = order_keys
    else:
        turn = Turn(
            turn_id=turn_id,
            session_id_fk=db_session.id,
            prompt=prompt,
            selected_models=selected_models or [],
            model_order=order_keys or []
        )
        db.session.add(turn)
    
    db.session.commit()


def add_turn_message(session_id: str, turn_id: str, model_key: str, role: str, content: str, *, user_id: str | None = None):
    """
    为对话轮次添加消息（支持任意模型）
    
    Args:
        session_id: 会话ID
        turn_id: 轮次ID
        model_key: 模型标识符（如 "gemini", "gpt", "silicon" 或任何新模型）
        role: "user" 或 "assistant"
        content: 消息内容
    """
    db_session = Session.query.filter_by(session_id=session_id).first()
    if not db_session:
        raise ValueError(f"Session not found: {session_id}")
    if user_id and db_session.user_id and db_session.user_id != user_id:
        raise ValueError("Session is owned by another user")
    
    turn = Turn.query.filter_by(session_id_fk=db_session.id, turn_id=turn_id).first()
    if not turn:
        raise ValueError(f"Turn not found: {turn_id}")
    
    # 添加消息到 Message 表
    message = Message(
        turn_id_fk=turn.id,
        model_key=model_key,
        role=role,
        content=content
    )
    db.session.add(message)
    db.session.commit()
    metrics.record_db_query("add_turn_message")


def add_turn_message_(session_id: str, turn_id: str, model_key: str, role: str, content: str, *, user_id: str | None = None):
    """
    为对话轮次添加消息（支持任意模型）
    
    Args:
        session_id: 会话ID
        turn_id: 轮次ID
        model_key: 模型标识符（如 "gemini", "gpt", "silicon" 或任何新模型）
        role: "user" 或 "assistant"
        content: 消息内容
    """
    db_session = Session.query.filter_by(session_id=session_id).first()
    if not db_session:
        raise ValueError(f"Session not found: {session_id}")
    if user_id and db_session.user_id and db_session.user_id != user_id:
        raise ValueError("Session is owned by another user")
    
    turn = Turn.query.filter_by(session_id_fk=db_session.id, turn_id=turn_id).first()
    if not turn:
        raise ValueError(f"Turn not found: {turn_id}")
    
    # 添加消息到 Message 表
    message_ = Message_(
        turn_id_fk=turn.id,
        model_key=model_key,
        role=role,
        content=content
    )
    db.session.add(message_)
    db.session.commit()
    metrics.record_db_query("add_turn_message_")


def set_turn_order(session_id: str, turn_id: str, model_order: List[str], *, user_id: str | None = None):
    """更新会话中某轮次的模型顺序"""
    db_session = Session.query.filter_by(session_id=session_id).first()
    if not db_session:
        raise ValueError(f"Session not found: {session_id}")
    if user_id and db_session.user_id and db_session.user_id != user_id:
        raise ValueError("Session is owned by another user")

    turn = Turn.query.filter_by(session_id_fk=db_session.id, turn_id=turn_id).first()
    if not turn:
        raise ValueError(f"Turn not found: {turn_id}")

    turn.model_order = model_order or []
    db.session.commit()


def set_record_turn_order(record_id: str, turn_id: str, model_order: List[str], *, user_id: str | None = None):
    """更新历史记录中某轮次的模型顺序"""
    project = Project.query.filter_by(project_id=record_id).first()
    if not project:
        raise ValueError("Project not found")
    # 旧数据允许（user_id 为空也行），只在明确冲突时拒绝
    if user_id and project.user_id and project.user_id != user_id:
        raise ValueError("Project forbidden")

    target_turn: Turn | None = None
    for session in project.sessions:
        turn = Turn.query.filter_by(session_id_fk=session.id, turn_id=turn_id).first()
        if turn:
            target_turn = turn
            break

    if not target_turn:
        raise ValueError(f"Turn not found: {turn_id}")

    target_turn.model_order = model_order or []
    db.session.commit()


def append_thread_message(session_id: str, model_key: str, role: str, content: str, *, user_id: str | None = None):
    """
    向对话线程添加消息（用于上下文记忆）
    
    Args:
        session_id: 会话ID
        model_key: 模型标识符
        role: "user" 或 "assistant"
        content: 消息内容
    """
    db_session = Session.query.filter_by(session_id=session_id).first()
    if not db_session:
        raise ValueError(f"Session not found: {session_id}")
    if user_id and db_session.user_id and db_session.user_id != user_id:
        raise ValueError("Session is owned by another user")
    
    # 获取当前最大序号
    max_seq = db.session.query(db.func.max(Thread.sequence)).filter_by(
        session_id_fk=db_session.id,
        model_key=model_key
    ).scalar() or 0
    
    # 添加新消息
    thread_msg = Thread(
        session_id_fk=db_session.id,
        model_key=model_key,
        role=role,
        content=content,
        sequence=max_seq + 1
    )
    db.session.add(thread_msg)
    db.session.commit()
    metrics.record_db_query("append_thread_message")

# =========================
# Record/Project（历史记录）
# =========================

def ensure_project(project_id: str, username: str = "", project_name: str = "", expert_data: str = "", *, user_id: str | None = None) -> Project:
    """确保项目存在，不存在则创建"""
    project = Project.query.filter_by(project_id=project_id).first()
    if not project:
        # 不在这里命名，延迟到第一次对话时使用对话时间命名
        project = Project(
            project_id=project_id,
            user_id=user_id,
            username=username,
            project_name=project_name or "",  # 允许为空，稍后命名
            expert_data=expert_data
        )
        db.session.add(project)
        db.session.commit()
    elif user_id and project.user_id and project.user_id != user_id:
        raise ValueError("Project is owned by another user")
    elif user_id and not project.user_id:
        project.user_id = user_id
        db.session.commit()
    return project


def link_session_to_project(session_id: str, project_id: str, *, user_id: str | None = None):
    """将会话关联到项目"""
    db_session = Session.query.filter_by(session_id=session_id).first()
    if db_session:
        if user_id and db_session.user_id and db_session.user_id != user_id:
            raise ValueError("Session is owned by another user")
        project = Project.query.filter_by(project_id=project_id).first()
        if project and user_id and project.user_id and project.user_id != user_id:
            raise ValueError("Project is owned by another user")
        db_session.project_id = project_id
        if user_id and not db_session.user_id:
            db_session.user_id = user_id
        if project and user_id and not project.user_id:
            project.user_id = user_id
        db.session.commit()


def upsert_record_turn(record_id: str, turn_id: str, prompt: str, selected_models=None, model_order=None, *, user_id: str | None = None):
    """
    为项目创建或更新对话轮次
    
    注意：这个函数用于历史记录，会自动创建项目（如果不存在）
    """
    # 确保项目存在
    ensure_project(record_id, user_id=user_id)
    
    # 查找该项目下是否已有对应的 session
    # 这里我们使用项目的最新 session，如果没有则创建一个
    project = Project.query.filter_by(project_id=record_id).first()
    if not project.sessions:
        # 创建一个新 session 并关联到项目
        new_session_id = str(uuid.uuid4())
        new_session = Session(session_id=new_session_id, project_id=record_id, user_id=user_id)
        db.session.add(new_session)
        db.session.commit()
        db_session = new_session
    else:
        # 使用最新的 session
        db_session = project.sessions[-1]
    
    order_keys = None
    if isinstance(model_order, list):
        order_keys = model_order
    elif isinstance(selected_models, list):
        order_keys = [m.get("key") for m in selected_models if isinstance(m, dict) and m.get("key")]

    # 查找或创建 Turn
    turn = Turn.query.filter_by(session_id_fk=db_session.id, turn_id=turn_id).first()
    is_new_turn = False
    if turn:
        turn.prompt = prompt
        if selected_models is not None:
            turn.selected_models = selected_models
        if order_keys is not None:
            turn.model_order = order_keys
    else:
        is_new_turn = True
        turn = Turn(
            turn_id=turn_id,
            session_id_fk=db_session.id,
            prompt=prompt,
            selected_models=selected_models or [],
            model_order=order_keys or []
        )
        db.session.add(turn)
        db.session.flush()  # 刷新以获取 turn.created_at
    
    # 如果是新对话且项目没有名称，使用第一次对话的时间命名（这是用户实际提问的时间）
    if is_new_turn:
        project = Project.query.filter_by(project_id=record_id).first()
        if project and (not project.project_name or project.project_name.strip() == ""):
            # 使用 turn 的创建时间（第一次对话的时间，更准确）
            if turn.created_at:
                # turn.created_at 是数据库自动生成的时间，已经是正确的时区
                project.project_name = turn.created_at.strftime("%Y-%m-%d %H:%M:%S")
            elif project.created_at:
                # 如果 turn.created_at 不存在，使用项目的创建时间
                project.project_name = project.created_at.strftime("%Y-%m-%d %H:%M:%S")
            else:
                # 如果都不存在，使用当前时间
                from datetime import datetime
                project.project_name = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 如果项目没有名称，检查是否是项目的第一个 turn（即使 turn 已存在）
    if not is_new_turn:
        project = Project.query.filter_by(project_id=record_id).first()
        if project and (not project.project_name or project.project_name.strip() == ""):
            # 检查该项目下所有 session 的 turn 总数（即这是第一个 turn）
            total_turn_count = 0
            for session in project.sessions:
                total_turn_count += Turn.query.filter_by(session_id_fk=session.id).count()
            if total_turn_count == 1:
                # 使用这个 turn 的创建时间命名
                if turn.created_at:
                    project.project_name = turn.created_at.strftime("%Y-%m-%d %H:%M:%S")
                elif project.created_at:
                    project.project_name = project.created_at.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    from datetime import datetime
                    project.project_name = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    db.session.commit()


def set_record_turn_response(record_id: str, turn_id: str, model_key: str, response: Dict, *, user_id: str | None = None, isMessages_ = False):
    """
    设置项目对话轮次的模型响应（支持任意模型）
    
    Args:
        record_id: 项目ID
        turn_id: 轮次ID
        model_key: 模型标识符（任意字符串，如 "gemini", "gpt", "new_model"）
        response: 响应数据，包含 role 和 content
    """
    project = Project.query.filter_by(project_id=record_id).first()
    if not project or not project.sessions:
        raise ValueError(f"Project or session not found: {record_id}")
    if user_id and project.user_id and project.user_id != user_id:
        raise ValueError("Project is owned by another user")
    
    # 获取项目的最新 session
    db_session = project.sessions[-1]
    
    # 查找 turn
    turn = Turn.query.filter_by(session_id_fk=db_session.id, turn_id=turn_id).first()
    if not turn:
        raise ValueError(f"Turn not found: {turn_id}")
    
    # 添加或更新消息
    role = response.get("role", "assistant")
    content = response.get("content", "")
    

    if isMessages_:
        existing_msg = Message_.query.filter_by(
            turn_id_fk=turn.id,
            model_key=model_key,
            role=role
        ).first()
        if existing_msg:
            existing_msg.content = content
        else:
            message_ = Message_(
                turn_id_fk=turn.id,
                model_key=model_key,
                role=role,
                content=content
            )
            db.session.add(message_)
    else:
        # 检查是否已存在该模型的消息
        existing_msg = Message.query.filter_by(
            turn_id_fk=turn.id,
            model_key=model_key,
            role=role
        ).first()
        if existing_msg:
            existing_msg.content = content
        else:
            message = Message(
                turn_id_fk=turn.id,
                model_key=model_key,
                role=role,
                content=content
            )
            db.session.add(message)
    
    db.session.commit()


# =========================
# 历史记录查询
# =========================

def load_history_summaries(user_id: str) -> List[Dict]:
    """
    加载所有项目的摘要列表
    
    返回格式：
    [
        {
            "record_id": "...",
            "username": "...",
            "project_name": "...",
            "created_at": "...",
            "updated_at": "...",
            "turn_count": 5
        },
        ...
    ]
    """
    projects = Project.query.filter_by(user_id=user_id).order_by(Project.updated_at.desc()).all()
    summaries = []
    
    for project in projects:
        # 统计该项目的总对话轮次数
        turn_count = 0
        for session in project.sessions:
            turn_count += Turn.query.filter_by(session_id_fk=session.id).count()
        
        # 确保返回 UTC 时间的 ISO 格式（带 Z 后缀表示 UTC）
        def _get_utc_iso(dt):
            if not dt:
                return None
            if dt.tzinfo is None:
                # 无时区信息，假设为 UTC
                return dt.isoformat() + 'Z'
            else:
                # 有时区信息，转换为 UTC 后返回
                from datetime import timezone
                utc_time = dt.astimezone(timezone.utc)
                return utc_time.replace(tzinfo=None).isoformat() + 'Z'
        
        summaries.append({
            "record_id": project.project_id,
            "username": project.username or "",
            "project_name": project.project_name or "",
            "created_at": project.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": project.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            "created_at_iso": _get_utc_iso(project.created_at),
            "updated_at_iso": _get_utc_iso(project.updated_at),
            "timestamp": project.updated_at.strftime("%Y-%m-%d %H:%M:%S"),  # 兼容前端旧字段
            "timestamp_iso": _get_utc_iso(project.updated_at),
            "turn_count": turn_count,
            "has_expert_data": bool((project.expert_data or "").strip()),
        })
    
    return summaries


def load_history_detail(record_id: str, *, user_id: str) -> Optional[Dict]:
    """
    加载项目的详细历史记录
    
    返回格式：
    {
        "record_id": "...",
        "username": "...",
        "project_name": "...",
        "expert_data": "...",
        "created_at": "...",
        "updated_at": "...",
        "turns": [
            {
                "id": "turn_id",
                "timestamp": "...",
                "prompt": "...",
                "selected_models": [...],
                "responses": {
                    "gemini": [{role, content}, ...],
                    "gpt": [{role, content}, ...],
                    ...
                }
            },
            ...
        ]
    }
    """
    project = Project.query.filter_by(project_id=record_id, user_id=user_id).first()
    if not project:
        return None
    
    # 收集所有 session 的 turns
    all_turns = []
    for session in project.sessions:
        db_turns = Turn.query.filter_by(session_id_fk=session.id).order_by(Turn.created_at).all()
        for turn in db_turns:
            # 获取该轮次的所有模型响应
            responses = {}
            messages = Message.query.filter_by(turn_id_fk=turn.id).all()
            for msg in messages:
                if msg.model_key not in responses:
                    responses[msg.model_key] = []
                responses[msg.model_key].append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            selected_models = turn.selected_models or []
            order_keys = turn.model_order or []
            if order_keys and isinstance(selected_models, list):
                # 按 model_order 排序 selected_models；未在列表中的保持原顺序追加在后
                key_to_model = {m.get("key"): m for m in selected_models if isinstance(m, dict) and m.get("key")}
                ordered = [key_to_model[k] for k in order_keys if k in key_to_model]
                for m in selected_models:
                    k = m.get("key") if isinstance(m, dict) else None
                    if k not in order_keys:
                        ordered.append(m)
                selected_models = ordered

            # 确保返回 UTC 时间的 ISO 格式（带 Z 后缀表示 UTC）
            def _get_utc_iso(dt):
                if not dt:
                    return None
                if dt.tzinfo is None:
                    # 无时区信息，假设为 UTC
                    return dt.isoformat() + 'Z'
                else:
                    # 有时区信息，转换为 UTC 后返回
                    from datetime import timezone
                    utc_time = dt.astimezone(timezone.utc)
                    return utc_time.replace(tzinfo=None).isoformat() + 'Z'
            
            all_turns.append({
                "id": turn.turn_id,
                "timestamp": turn.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "timestamp_iso": _get_utc_iso(turn.created_at),
                "prompt": turn.prompt,
                "selected_models": selected_models,
                "model_order": order_keys,
                "responses": responses
            })
    
    return {
        "record_id": project.project_id,
        "username": project.username or "",
        "project_name": project.project_name or "",
        "expert_data": project.expert_data or "",
        "created_at": project.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": project.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        "created_at_iso": _get_utc_iso(project.created_at),
        "updated_at_iso": _get_utc_iso(project.updated_at),
        "turns": all_turns
    }


# =========================
# 辅助函数
# =========================

def get_thread_history(session_id: str, model_key: str, *, user_id: str | None = None) -> List[Dict]:
    """
    获取某个模型在某个会话中的完整对话历史
    
    返回格式：[{role, content}, ...]
    """
    db_session = Session.query.filter_by(session_id=session_id).first()
    if not db_session:
        return []
    if user_id and db_session.user_id and db_session.user_id != user_id:
        return []
    
    thread_messages = Thread.query.filter_by(
        session_id_fk=db_session.id,
        model_key=model_key
    ).order_by(Thread.sequence).all()
    
    return [
        {"role": msg.role, "content": msg.content}
        for msg in thread_messages
    ]


# =========================
# Public Chat
# =========================

def _public_message_to_dict(msg: PublicMessage, my_vote: Optional[str] = None) -> Dict:
    # 确保返回 UTC 时间的 ISO 格式（带 Z 后缀表示 UTC）
    iso_time = None
    if msg.created_at:
        if msg.created_at.tzinfo is None:
            # 无时区信息，假设为 UTC
            iso_time = msg.created_at.isoformat() + 'Z'
        else:
            # 有时区信息，转换为 UTC 后返回
            from datetime import timezone
            utc_time = msg.created_at.astimezone(timezone.utc)
            iso_time = utc_time.replace(tzinfo=None).isoformat() + 'Z'
    
    return {
        "message_id": msg.message_id,
        "user_id": msg.user_id,
        "profession": msg.profession,
        "content": msg.content,
        "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M:%S") if msg.created_at else "",
        "created_at_iso": iso_time,
        "like_count": msg.like_count,
        "dislike_count": msg.dislike_count,
        "my_vote": my_vote,
    }


def list_public_messages(
    limit: int = 100,
    *,
    user_id: str | None = None,
    user_profession: str | None = None,
    start_utc: Optional[datetime] = None,
    end_utc: Optional[datetime] = None,
) -> List[Dict]:
    """获取公屏消息（可按专业过滤）"""
    limit = max(1, min(limit or 100, 500))
    
    # 构建查询：如果提供专业则过滤，否则获取所有专业
    query = PublicMessage.query
    if user_profession:
        query = query.filter_by(profession=user_profession)
    # 如果提供时间窗口则过滤；否则返回最近 limit 条（按时间升序）
    if start_utc is not None and end_utc is not None:
        query = query.filter(PublicMessage.created_at >= start_utc, PublicMessage.created_at < end_utc)
    
    messages = query.order_by(PublicMessage.created_at.asc()).limit(limit).all()
    
    vote_map: Dict[str, str] = {}
    if user_id and messages:
        ids = [m.message_id for m in messages]
        votes = PublicVote.query.filter(
            PublicVote.message_id.in_(ids),
            PublicVote.user_id == user_id
        ).all()
        vote_map = {v.message_id: v.vote for v in votes}

    metrics.record_db_query("list_public_messages")
    return [
        _public_message_to_dict(m, vote_map.get(m.message_id))
        for m in messages
    ]


def create_public_message(user_id: str, content: str, profession: str) -> Dict:
    """创建公屏消息，关联用户专业"""
    content = (content or "").strip()
    if not content:
        raise ValueError("content is empty")
    if not profession:
        raise ValueError("profession is required")
    
    msg = PublicMessage(
        message_id=str(uuid.uuid4()),
        user_id=user_id,
        profession=profession,
        content=content,
        like_count=0,
        dislike_count=0,
    )
    db.session.add(msg)
    db.session.commit()
    metrics.record_db_query("create_public_message")
    return _public_message_to_dict(msg, my_vote=None)


def vote_public_message(user_id: str, message_id: str, vote: str, user_profession: str | None = None) -> Dict:
    """投票公屏消息，确保只能投同专业消息"""
    vote = (vote or "").strip().lower()
    if vote not in {"like", "dislike"}:
        raise ValueError("vote must be 'like' or 'dislike'")

    msg = PublicMessage.query.filter_by(message_id=message_id).first()
    if not msg:
        raise ValueError("Message not found")
    
    # 专业隔离：只能投同专业的消息
    if user_profession and msg.profession != user_profession:
        raise ValueError("Cannot vote on messages from other professions")

    existing = PublicVote.query.filter_by(message_id=message_id, user_id=user_id).first()

    if not existing:
        # 新投票
        new_vote = PublicVote(message_id=message_id, user_id=user_id, vote=vote)
        db.session.add(new_vote)
        if vote == "like":
            msg.like_count += 1
        else:
            msg.dislike_count += 1
    else:
        if existing.vote == vote:
            # 如果与之前相同，视为取消投票：删除投票记录并回退计数
            if existing.vote == "like":
                msg.like_count = max(0, (msg.like_count or 0) - 1)
            elif existing.vote == "dislike":
                msg.dislike_count = max(0, (msg.dislike_count or 0) - 1)
            db.session.delete(existing)
            db.session.commit()
            metrics.record_db_query("vote_public_message")
            return _public_message_to_dict(msg, my_vote=None)
        # 改变投票，需先回滚旧计数
        if existing.vote == "like":
            msg.like_count = max(0, (msg.like_count or 0) - 1)
        elif existing.vote == "dislike":
            msg.dislike_count = max(0, (msg.dislike_count or 0) - 1)

        # 设置新投票
        existing.vote = vote
        if vote == "like":
            msg.like_count += 1
        else:
            msg.dislike_count += 1

    db.session.commit()
    metrics.record_db_query("vote_public_message")
    return _public_message_to_dict(msg, my_vote=vote)
