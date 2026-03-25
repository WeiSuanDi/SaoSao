"""
数据库连接配置
支持 PostgreSQL (生产环境) 和 SQLite (本地开发)
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# 获取数据库连接字符串
DATABASE_URL = os.environ.get("DATABASE_URL")

# 根据环境选择数据库
if DATABASE_URL:
    # Railway PostgreSQL
    # 将 postgresql:// 转换为 postgresql+asyncpg://
    if DATABASE_URL.startswith("postgresql://"):
        ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    else:
        ASYNC_DATABASE_URL = DATABASE_URL
    SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://")
else:
    # 本地 SQLite (异步)
    ASYNC_DATABASE_URL = "sqlite+aiosqlite:///./weisuandi.db"
    SYNC_DATABASE_URL = "sqlite:///./weisuandi.db"

# 创建异步引擎
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,  # 设为 True 可以看到 SQL 日志
)

# 创建同步引擎 (用于 seed.py 等脚本)
sync_engine = create_engine(SYNC_DATABASE_URL, echo=False)

# 创建异步会话工厂
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# 创建同步会话工厂
SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
)


# 异步依赖注入
async def get_async_session():
    """获取异步数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# 同步依赖注入
def get_sync_session():
    """获取同步数据库会话"""
    session = SyncSessionLocal()
    try:
        yield session
    finally:
        session.close()
