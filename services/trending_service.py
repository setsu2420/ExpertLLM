"""热点榜单服务 - 处理热点消息排行"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from models import db, PublicMessage, Users


class TrendingService:
    """热点榜单服务"""
    
    def get_school_trending(
        self,
        school: str,
        limit: int = 10,
        *,
        start_utc: Optional[datetime] = None,
        end_utc: Optional[datetime] = None,
    ) -> List[Dict]:
        """获取指定学校昨日热点消息（按点赞数排序）
        
        Args:
            school: 学校名称
            limit: 返回数量
            
        Returns:
            热点消息列表，每条包含：
            - message_id: 消息ID
            - content: 消息内容
            - like_count: 点赞数
            - profession: 发布者专业
            - user_id: 发布者学号
            - created_at: 发布时间
        """
        # 计算昨天的时间范围（默认 UTC），可由调用方传入用户时区换算后的 UTC 窗口
        if start_utc is None or end_utc is None:
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_start = today - timedelta(days=1)
            yesterday_end = today
        else:
            yesterday_start, yesterday_end = start_utc, end_utc
        
        # 查询昨天发布的消息，按点赞数降序
        trending_messages = (
            db.session.query(PublicMessage, Users)
            .join(Users, PublicMessage.user_id == Users.user_id)
            .filter(
                Users.school == school,
                PublicMessage.created_at >= yesterday_start,
                PublicMessage.created_at < yesterday_end
            )
            .order_by(PublicMessage.like_count.desc())
            .limit(limit)
            .all()
        )
        
        result = []
        for msg, user in trending_messages:
            # 确保返回 UTC 时间的 ISO 格式（带 Z 后缀表示 UTC）
            iso_time = None
            if msg.created_at:
                # 如果时间对象有 tzinfo，确保转换为 UTC
                if msg.created_at.tzinfo is None:
                    # 无时区信息，假设为 UTC
                    iso_time = msg.created_at.isoformat() + 'Z'
                else:
                    # 有时区信息，转换为 UTC 后返回
                    from datetime import timezone
                    utc_time = msg.created_at.astimezone(timezone.utc)
                    iso_time = utc_time.replace(tzinfo=None).isoformat() + 'Z'
            
            result.append({
                "message_id": msg.message_id,
                "content": msg.content,
                "like_count": msg.like_count,
                "dislike_count": msg.dislike_count,
                "profession": msg.profession,
                "user_id": msg.user_id,
                "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M:%S") if msg.created_at else "",
                "created_at_iso": iso_time
            })
        
        return result

    def get_question_trending():
        """
        get_question_trending 的 Docstring
        """


        return 0

# 全局单例
trending_service = TrendingService()
