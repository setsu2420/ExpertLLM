"""用户服务 - 处理用户相关业务逻辑"""
from __future__ import annotations

from typing import Optional, Tuple
from werkzeug.security import generate_password_hash, check_password_hash

from models import Users, db


class UserService:
    """用户服务"""
    def save_user(self, user: Users) -> None:
        """保存用户对象到数据库"""
        try:
            db.session.add(user)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e
    
    def get_user_and_profession(self, user_id: str) -> Tuple[Optional[Users], Optional[str]]:
        """获取用户和专业信息"""
        user = Users.query.filter_by(user_id=user_id).first()
        if not user:
            return None, None
        return user, user.major
    
    def authenticate(self, user_id: str, password: str) -> Optional[Users]:
        """验证用户登录
        
        Returns:
            验证成功返回 User 对象，失败返回 None
        """
        user = Users.query.filter_by(user_id=user_id).first()
        if not user or not check_password_hash(user.password, password):
            return None
        return user
    
    def register(
        self,
        user_id: str,
        password: str,
        school: str,
        major: str,
        job: str,
        company: str,
        student_card_binary: Optional[bytes] = None
    ) -> Tuple[bool, str]:
        """注册新用户
        
        Returns:
            (success, message) 元组
        """
        # 检查是否已存在
        existing_user = Users.query.filter_by(user_id=user_id).first()
        if existing_user:
            return False, "该用户已注册，请直接登录或更换手机号"
        
        # 创建新用户
        new_user = Users(
            user_id=user_id,
            school=school,
            major=major,
            job=job,
            company=company,
            password=generate_password_hash(password),
            student_card=student_card_binary
        )
        
        try:
            db.session.add(new_user)
            db.session.commit()
            return True, "注册成功"
        except Exception as e:
            db.session.rollback()
            return False, f"注册失败: {str(e)}"
    
    def get_major_room(self, profession: Optional[str]) -> Optional[str]:
        """获取专业房间名"""
        return f"major:{profession}" if profession else None

    def get_user_by_id(self, user_id: str) -> Optional[Users]:
        """通过 user_id 获取用户对象"""
        return Users.query.filter_by(user_id=user_id).first()


# 全局单例
user_service = UserService()
