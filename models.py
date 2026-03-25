"""
SQLAlchemy 数据模型
包含四张表：locations, messages, presence, likes
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Location(Base):
    """地点表"""
    __tablename__ = "locations"

    id = Column(String(50), primary_key=True)  # 地点标识，如 "library-3f"
    name = Column(String(100), nullable=False)  # 展示名，如 "图书馆三楼"
    description = Column(String(200), nullable=True)  # 简短描述
    scan_count = Column(Integer, default=0)  # 累计扫码次数
    created_at = Column(DateTime, default=datetime.utcnow)  # 创建时间

    # 关联关系
    messages = relationship("Message", back_populates="location", cascade="all, delete-orphan")
    presences = relationship("Presence", back_populates="location", cascade="all, delete-orphan")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "scan_count": self.scan_count,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Message(Base):
    """留言表"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)  # 自增主键
    location_id = Column(String(50), ForeignKey("locations.id"), nullable=False)  # 关联地点
    content = Column(String(280), nullable=False)  # 留言内容，限280字
    nickname = Column(String(30), nullable=False)  # 随机匿名昵称
    session_id = Column(String(64), nullable=False)  # 浏览器 session 标识
    like_count = Column(Integer, default=0)  # 点赞数
    created_at = Column(DateTime, default=datetime.utcnow)  # 发布时间

    # 关联关系
    location = relationship("Location", back_populates="messages")
    likes = relationship("Like", back_populates="message", cascade="all, delete-orphan")

    def to_dict(self, session_id=None, check_likes=True):
        """转换为字典"""
        result = {
            "id": self.id,
            "content": self.content,
            "nickname": self.nickname,
            "like_count": self.like_count or 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "liked": False
        }
        return result


class Like(Base):
    """点赞表"""
    __tablename__ = "likes"
    __table_args__ = (
        UniqueConstraint('message_id', 'session_id', name='uq_message_session'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)  # 自增主键
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)  # 关联留言
    session_id = Column(String(64), nullable=False)  # 浏览器 session 标识
    created_at = Column(DateTime, default=datetime.utcnow)  # 点赞时间

    # 关联关系
    message = relationship("Message", back_populates="likes")


class Presence(Base):
    """在场记录表"""
    __tablename__ = "presence"
    __table_args__ = (
        UniqueConstraint('location_id', 'session_id', name='uq_location_session'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)  # 自增主键
    location_id = Column(String(50), ForeignKey("locations.id"), nullable=False)  # 关联地点
    session_id = Column(String(64), nullable=False)  # 浏览器 session 标识
    last_seen = Column(DateTime, default=datetime.utcnow)  # 最后活跃时间

    # 关联关系
    location = relationship("Location", back_populates="presences")


def init_models(engine):
    """初始化数据库表结构"""
    Base.metadata.create_all(engine)
