"""Database setup and model exports."""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func

db = SQLAlchemy()


class TimestampMixin:
	created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
	updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


def init_app(app):
	"""Initialize the SQLAlchemy extension."""
	db.init_app(app)


# Import models so Flask-Migrate can auto-detect them
from .users import Users  # noqa: E402,F401
from .database import Project, Session, Turn, Message, Message_, Thread, PublicMessage, PublicVote, QuestionEmbedding  # noqa: E402,F401
from .admin import AdminUser  # noqa: E402,F401

__all__ = [
	"db",
	"TimestampMixin",
	"Users",
	"Project",
	"Session",
	"Turn",
	"Message",
	"Message_",
	"Thread",
	"PublicMessage",
	"PublicVote",
	"QuestionEmbedding",
	"AdminUser",
	"init_app",
]
