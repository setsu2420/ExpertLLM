"""User-related models."""

from sqlalchemy.dialects.mysql import MEDIUMBLOB

from . import db, TimestampMixin


class Users(db.Model, TimestampMixin):
	__tablename__ = "users"

	user_id = db.Column(db.String(255), primary_key=True)
	job = db.Column(db.String(255), nullable=False)
	company = db.Column(db.String(255), nullable=True)
	school = db.Column(db.String(255), nullable=False)
	major = db.Column(db.String(255), nullable=False)
	password = db.Column(db.String(255), nullable=False)
	student_card = db.Column(MEDIUMBLOB)

	def __repr__(self) -> str:
		return f"<User {self.user_id}>"
