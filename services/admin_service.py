"""Admin service: permissions and operations for admin users"""
from __future__ import annotations

from typing import List, Dict, Tuple
from werkzeug.security import check_password_hash

from models import db, Users, Project, Session, Turn, AdminUser


class AdminService:
    def is_admin(self, user_id: str | None) -> bool:
        if not user_id:
            return False
        return AdminUser.query.filter_by(user_id=user_id).first() is not None

    def list_admins(self) -> List[Dict]:
        items = AdminUser.query.order_by(AdminUser.created_at.asc()).all()
        out: List[Dict] = []
        for a in items:
            iso = None
            if a.created_at:
                if a.created_at.tzinfo is None:
                    iso = a.created_at.isoformat() + 'Z'
                else:
                    from datetime import timezone
                    iso = a.created_at.astimezone(timezone.utc).replace(tzinfo=None).isoformat() + 'Z'
            out.append({
                "user_id": a.user_id,
                "level": a.level,
                "created_at": a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else "",
                "created_at_iso": iso,
            })
        return out

    def _verify_password(self, user_id: str, password: str) -> bool:
        u = Users.query.filter_by(user_id=user_id).first()
        if not u:
            return False
        try:
            return check_password_hash(u.password, password)
        except Exception:
            return False

    def add_admin(self, current_user_id: str, target_user_id: str, level: int, current_password: str) -> Tuple[bool, str]:
        target_user_id = (target_user_id or "").strip()
        if not target_user_id or not current_password:
            return False, "缺少必要参数"

        # 首个管理员豁免：若没有任何管理员，允许任意登录用户自举创建首个管理员
        total_admins = AdminUser.query.count()
        need_admin_right = total_admins > 0

        if need_admin_right and not self.is_admin(current_user_id):
            return False, "需要管理员权限"

        # 验证当前管理员密码
        if not self._verify_password(current_user_id, current_password):
            return False, "密码验证失败"

        # 目标用户必须存在
        target = Users.query.filter_by(user_id=target_user_id).first()
        if not target:
            return False, "目标用户不存在"

        # 已存在则更新权限等级
        rec = AdminUser.query.filter_by(user_id=target_user_id).first()
        if rec:
            rec.level = int(level or 1)
        else:
            rec = AdminUser(user_id=target_user_id, level=int(level or 1))
            db.session.add(rec)
        try:
            db.session.commit()
            return True, "操作成功"
        except Exception as e:
            db.session.rollback()
            return False, f"保存失败: {e}"

    def list_projects(self, limit: int = 50) -> List[Dict]:
        limit = max(1, min(int(limit or 50), 200))
        projects = (
            Project.query
            .filter(Project.expert_data.isnot(None), Project.expert_data != "")
            .order_by(Project.updated_at.desc())
            .limit(limit)
            .all()
        )
        result: List[Dict] = []
        for p in projects:
            # 统计该项目的总对话轮次数
            turn_count = 0
            for s in p.sessions:
                turn_count += Turn.query.filter_by(session_id_fk=s.id).count()

            # ISO UTC 时间
            iso = None
            if p.updated_at:
                if p.updated_at.tzinfo is None:
                    iso = p.updated_at.isoformat() + 'Z'
                else:
                    from datetime import timezone
                    iso = p.updated_at.astimezone(timezone.utc).replace(tzinfo=None).isoformat() + 'Z'

            result.append({
                "project_id": p.project_id,
                "project_name": p.project_name or "",
                "user_id": p.user_id or "",
                "updated_at": p.updated_at.strftime("%Y-%m-%d %H:%M:%S") if p.updated_at else "",
                "updated_at_iso": iso,
                "turn_count": turn_count,
                "expert_preview": (p.expert_data or "")[:120],
                "expert_data": p.expert_data or "",
            })
        return result


admin_service = AdminService()
