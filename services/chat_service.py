"""聊天服务 - 处理聊天会话、消息历史等业务逻辑"""
from __future__ import annotations

import uuid
import threading
from typing import Dict, List, Optional, Tuple

import db_service


class ChatService:
    """聊天服务"""
    
    def __init__(self):
        # records.json 写锁
        self.record_lock = threading.Lock()
        
        # session 文件写锁（按 session_id 分锁）
        self._session_locks: Dict[str, threading.Lock] = {}
        self._session_locks_guard = threading.Lock()
    
    def get_session_lock(self, session_id: str) -> threading.Lock:
        """获取指定 session 的锁"""
        with self._session_locks_guard:
            if session_id not in self._session_locks:
                self._session_locks[session_id] = threading.Lock()
            return self._session_locks[session_id]
    
    def trim_thread(self, messages: List[Dict[str, str]], max_messages: int) -> List[Dict[str, str]]:
        """截断消息历史"""
        if max_messages <= 0:
            return messages
        return messages[-max_messages:] if len(messages) > max_messages else messages
    
    def compose_display(self, reasoning_text: str, content_text: str) -> str:
        """组合显示内容（包含思考过程）"""
        reasoning_text = reasoning_text or ""
        content_text = content_text or ""
        
        if reasoning_text.strip():
            return (
                "<details open>\n"
                "<summary>思考过程</summary>\n\n"
                "```text\n"
                f"{reasoning_text}\n"
                "```\n\n"
                "</details>\n\n"
                f"{content_text}"
            )
        return content_text
    
    def ensure_session_and_project(
        self,
        session_id: str,
        user_id: str
    ) -> Tuple[dict, str]:
        """确保会话和项目存在，返回 (session_data, record_id)"""
        session_data = db_service.load_chat_session(session_id, user_id=user_id)
        if not session_data:
            db_service.create_chat_session(session_id, user_id=user_id)
            session_data = db_service.load_chat_session(session_id, user_id=user_id)
        
        record_id = (session_data.get("record_id") or "").strip()
        if not record_id:
            with self.record_lock:
                record_id = str(uuid.uuid4())
                db_service.ensure_project(record_id, user_id=user_id)
                db_service.link_session_to_project(session_id, record_id, user_id=user_id)
        
        return session_data, record_id
    
    def create_new_session(self, user_id: str) -> str:
        """创建新会话"""
        return db_service.create_chat_session(user_id=user_id)
    
    def save_turn_message(
        self,
        session_id: str,
        turn_id: str,
        prompt: str,
        selected_models: List[str],
        user_id: str
    ):
        """保存 turn 和用户消息"""
        session_lock = self.get_session_lock(session_id)
        with session_lock:
            session_data = db_service.load_chat_session(session_id, user_id=user_id)
            db_service.upsert_chat_turn(session_data, turn_id, prompt, selected_models=selected_models)
    
    def save_assistant_message(
        self,
        session_id: str,
        turn_id: str,
        model_key: str,
        content: str,
        display_content: str,
        user_id: str
    ):
        """保存助手回复"""
        session_lock = self.get_session_lock(session_id)
        with session_lock:
            if content:
                db_service.append_thread_message(
                    session_id, model_key, 
                    role="assistant", 
                    content=content, 
                    user_id=user_id
                )
            db_service.add_turn_message(
                session_id, turn_id, model_key,
                role="assistant",
                content=display_content,
                user_id=user_id
            )
    
    def save_assistant_message_(
        self,
        session_id: str,
        turn_id: str,
        model_key: str,
        content: str,
        display_content: str,
        user_id: str
    ):
        """保存助手回复"""
        session_lock = self.get_session_lock(session_id)
        with session_lock:
            db_service.add_turn_message_(
                session_id, turn_id, model_key,
                role="assistant",
                content=display_content,
                user_id=user_id
            )
    
    def save_record_turn(
        self,
        record_id: str,
        turn_id: str,
        prompt: str,
        model_key: str,
        display_content: str,
        selected_models: List[str],
        user_id: str,
        isMessages_ = False
    ):
        """保存到 records（历史记录）"""
        with self.record_lock:
            db_service.upsert_record_turn(
                record_id, turn_id, prompt,
                selected_models=selected_models,
                user_id=user_id
            )
            db_service.set_record_turn_response(
                record_id, turn_id, model_key,
                {"role": "assistant", "content": display_content},
                user_id=user_id,
                isMessages_= isMessages_
            )


# 全局单例
chat_service = ChatService()
