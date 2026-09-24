from datetime import UTC, datetime

from sqlalchemy import DateTime, Text, String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Users(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True, default=None)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    image_file: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    posts: Mapped[list['Post']] = relationship(back_populates="author", cascade="all, delete-orphan")

    @property
    def image_path(self):
        if self.image_file is None:
            return "/static/profile_pics/default.jpg"

        return f"/media/profile_pics/{self.image_file}"


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    date_posted: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    author: Mapped[Users] = relationship(back_populates="posts")
