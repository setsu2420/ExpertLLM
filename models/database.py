"""数据库模型定义 - 替代原有的 chat.py 和 record.py"""

from . import db, TimestampMixin


class Project(db.Model, TimestampMixin):
    """对话项目表 - 用于组织和管理对话历史"""
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.String(255), db.ForeignKey("users.user_id", ondelete="SET NULL"), index=True)
    username = db.Column(db.String(128))
    project_name = db.Column(db.String(255))
    expert_data = db.Column(db.Text)  # 存储专家数据（JSON格式）

    # 关系：一个项目包含多个会话
    sessions = db.relationship("Session", backref="project", cascade="all, delete-orphan", lazy=True)


class Session(db.Model, TimestampMixin):
    """对话会话表 - 一次完整的对话上下文"""
    __tablename__ = "sessions"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    project_id = db.Column(db.String(64), db.ForeignKey("projects.project_id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = db.Column(db.String(255), db.ForeignKey("users.user_id", ondelete="SET NULL"), index=True)

    # 关系：一个会话包含多个对话轮次
    turns = db.relationship("Turn", backref="session", cascade="all, delete-orphan", lazy=True)


class Turn(db.Model, TimestampMixin):
    """对话轮次表 - 一次用户提问和所有模型的回答"""
    __tablename__ = "turns"

    id = db.Column(db.Integer, primary_key=True)
    turn_id = db.Column(db.String(64), nullable=False, index=True)
    session_id_fk = db.Column(db.Integer, db.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    prompt = db.Column(db.Text, nullable=False)  # 用户的提问
    selected_models = db.Column(db.JSON, default=list)  # 选择的模型列表，如 ["gemini", "gpt", "silicon"]
    model_order = db.Column(db.JSON, default=list)  # 模型顺序（数组，元素为模型 key）

    # 关系：一个轮次包含多个模型的消息
    messages = db.relationship("Message", backref="turn", cascade="all, delete-orphan", lazy=True)

    # 添加唯一约束：同一个 session 中 turn_id 唯一
    __table_args__ = (
        db.UniqueConstraint('session_id_fk', 'turn_id', name='uix_session_turn'),
    )


class Message(db.Model, TimestampMixin):
    """
    模型消息表 - 存储所有模型的响应（可扩展设计）
    
    核心设计思想：
    - 所有模型的响应都存储在这一个表中
    - 通过 model_key 字段区分不同的模型（如 "gemini", "gpt", "silicon"）
    - 添加新模型时，无需修改数据库结构，只需插入新的 model_key
    - role 字段区分用户消息和模型响应（"user" 或 "assistant"）
    """
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    turn_id_fk = db.Column(db.Integer, db.ForeignKey("turns.id", ondelete="CASCADE"), nullable=False, index=True)
    model_key = db.Column(db.String(64), nullable=False, index=True)  # 模型标识符：gemini, gpt, silicon 等
    role = db.Column(db.String(16), nullable=False)  # "user" 或 "assistant"
    content = db.Column(db.Text, nullable=False)  # 消息内容

    # 添加索引以优化查询性能
    __table_args__ = (
        db.Index('ix_turn_model', 'turn_id_fk', 'model_key'),
    )


class Message_(db.Model, TimestampMixin):
    """
    模型消息表 - 存储所有模型的响应（可扩展设计）
    
    核心设计思想：
    - 所有模型的响应都存储在这一个表中
    - 通过 model_key 字段区分不同的模型（如 "gemini", "gpt", "silicon"）
    - 添加新模型时，无需修改数据库结构，只需插入新的 model_key
    - role 字段区分用户消息和模型响应（"user" 或 "assistant"）
    """
    __tablename__ = "messages_"

    id = db.Column(db.Integer, primary_key=True)
    turn_id_fk = db.Column(db.Integer, db.ForeignKey("turns.id", ondelete="CASCADE"), nullable=False, index=True)
    model_key = db.Column(db.String(64), nullable=False, index=True)  # 模型标识符：gemini, gpt, silicon 等
    role = db.Column(db.String(16), nullable=False)  # "user" 或 "assistant"
    content = db.Column(db.Text, nullable=False)  # 消息内容

    # 添加索引以优化查询性能
    __table_args__ = (
        db.Index('ix_turn_model', 'turn_id_fk', 'model_key'),
    )


class Thread(db.Model, TimestampMixin):
    """
    对话线程表 - 存储每个模型的完整对话历史（用于上下文记忆）
    
    设计说明：
    - 每个 session + model_key 组合对应一个独立的对话线程
    - 用于实现多轮对话时的上下文记忆功能
    - role 和 content 字段存储历史消息
    """
    __tablename__ = "threads"

    id = db.Column(db.Integer, primary_key=True)
    session_id_fk = db.Column(db.Integer, db.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    model_key = db.Column(db.String(64), nullable=False, index=True)  # 模型标识符
    role = db.Column(db.String(16), nullable=False)  # "user" 或 "assistant"
    content = db.Column(db.Text, nullable=False)  # 消息内容
    sequence = db.Column(db.Integer, nullable=False, default=0)  # 消息顺序

    # 添加索引以优化查询性能
    __table_args__ = (
        db.Index('ix_session_model', 'session_id_fk', 'model_key'),
    )


class PublicMessage(db.Model, TimestampMixin):
    """公屏消息表"""
    __tablename__ = "public_messages"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.String(255), db.ForeignKey("users.user_id", ondelete="SET NULL"), index=True)
    profession = db.Column(db.String(255), nullable=False, index=True)  # 消息发布者的专业
    content = db.Column(db.Text, nullable=False)
    like_count = db.Column(db.Integer, nullable=False, default=0)
    dislike_count = db.Column(db.Integer, nullable=False, default=0)
    
    # 关联用户，获取学校信息
    user = db.relationship('Users', foreign_keys=[user_id], backref='public_messages')


class QuestionEmbedding(db.Model, TimestampMixin):
    """问题句向量表，用于语义热点问句聚类。"""
    __tablename__ = "question_embeddings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), db.ForeignKey("users.user_id", ondelete="SET NULL"), index=True)
    prompt = db.Column(db.Text, nullable=False)
    prompt_hash = db.Column(db.String(128), nullable=False, index=True, unique=True)
    embedding = db.Column(db.LargeBinary, nullable=False)
    turn_created_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)

    __table_args__ = (
        db.Index('ix_question_embeddings_user_prompt', 'user_id', 'prompt_hash'),
    )


class PublicVote(db.Model, TimestampMixin):
    """公屏消息点赞/点踩表"""
    __tablename__ = "public_votes"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.String(64), db.ForeignKey("public_messages.message_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.String(255), db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    vote = db.Column(db.String(8), nullable=False)  # "like" 或 "dislike"

    __table_args__ = (
        db.UniqueConstraint('message_id', 'user_id', name='uix_public_vote_msg_user'),
    )
