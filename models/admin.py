"""Admin model for storing admin users"""

from . import db, TimestampMixin


class AdminUser(db.Model, TimestampMixin):
    __tablename__ = "admin_users"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), db.ForeignKey("users.user_id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    level = db.Column(db.Integer, nullable=False, default=1)

    user = db.relationship('Users', foreign_keys=[user_id], backref='admin_record')
