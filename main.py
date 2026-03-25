"""
FastAPI 应用入口
基于NFC/二维码的地点匿名留言平台
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Cookie, Response, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, update, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import async_engine, get_async_session, AsyncSessionLocal
from models import Base, Location, Message, Presence, Like, init_models


# 昵称生成词库
ADJECTIVES = [
    "安静的", "快乐的", "迷路的", "认真的", "困困的", "饥饿的", "好奇的", "勇敢的",
    "害羞的", "暴躁的", "优雅的", "沉默的", "活泼的", "懒散的", "机智的", "温柔的",
    "神秘的", "倔强的", "疲惫的", "淡定的", "慵懒的", "调皮的", "呆萌的", "傲娇的"
]

ANIMALS = [
    "海豹", "熊猫", "柴犬", "猫头鹰", "企鹅", "水獭", "仓鼠", "考拉", "狐狸", "刺猬",
    "兔子", "鹦鹉", "海龟", "松鼠", "浣熊", "树懒", "白鲸", "柯基", "河马", "火烈鸟",
    "小猫", "小狗", "海豚", "小鹿"
]

import random


def generate_nickname() -> str:
    """生成随机昵称：形容词+动物"""
    adj = random.choice(ADJECTIVES)
    animal = random.choice(ANIMALS)
    return adj + animal


async def get_or_create_session_id(session_id: Optional[str]) -> str:
    """获取或创建 session_id"""
    if session_id:
        return session_id
    return str(uuid.uuid4())


# 种子数据
LOCATIONS = [
    {"id": "library-main", "name": "图书馆", "description": "知识的海洋，卷王的战场", "emoji": "📚"},
    {"id": "east9", "name": "东九教学楼", "description": "上课、自习、发呆的地方", "emoji": "🎓"},
    {"id": "canteen-baiwei", "name": "百味食堂", "description": "今天吃什么是永恒的难题", "emoji": "🍜"},
    {"id": "gym", "name": "光谷体育馆", "description": "挥洒汗水的地方", "emoji": "🏃"},
    {"id": "dorm-south", "name": "南边宿舍区", "description": "回到温暖的小窝", "emoji": "🏠"},
]

SEED_MESSAGES = {
    "library-main": ["三楼西区今天人好少，赚到了", "四楼靠窗那排插座最多", "闭馆音乐响起的时候，才发现外面天都黑了"],
    "east9": ["这个教室的空调永远是个谜", "下午三点的阳光正好，适合发呆", "期中考试周，这里变成了战场"],
    "canteen-baiwei": ["二楼新来的麻辣香锅可以的", "中午12点来排队简直是自虐", "推荐一楼的煲仔饭，分量足"],
    "gym": ["有没有人周末打羽毛球", "游泳馆的水温刚刚好", "篮球场今天居然空着"],
    "dorm-south": ["又到了纠结洗不洗澡的时间", "楼下那只猫又在蹭吃蹭喝", "今晚外卖点什么好呢"],
}


async def init_seed_data():
    """初始化种子数据"""
    async with AsyncSessionLocal() as db:
        # 检查是否已有数据
        result = await db.execute(select(Location).limit(1))
        if result.scalar_one_or_none():
            return  # 已有数据，跳过

        # 创建地点
        for loc_data in LOCATIONS:
            location = Location(
                id=loc_data["id"],
                name=loc_data["name"],
                description=loc_data["description"],
                scan_count=random.randint(10, 100),
                created_at=datetime.utcnow()
            )
            db.add(location)

        await db.commit()

        # 创建种子留言（带随机点赞数）
        for loc_id, messages in SEED_MESSAGES.items():
            for content in messages:
                message = Message(
                    location_id=loc_id,
                    content=content,
                    nickname=generate_nickname(),
                    session_id=f"seed-{random.randint(1000, 9999)}",
                    like_count=random.randint(0, 20),
                    created_at=datetime.utcnow() - timedelta(minutes=random.randint(1, 1440))
                )
                db.add(message)

        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化数据库和种子数据"""
    async with async_engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)

        # 数据库迁移：添加缺失的列和表（兼容旧数据库）
        try:
            # 添加 like_count 列到 messages 表
            await conn.execute(text(
                "ALTER TABLE messages ADD COLUMN IF NOT EXISTS like_count INTEGER DEFAULT 0"
            ))
            # 创建 likes 表（如果不存在）
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS likes (
                    id SERIAL PRIMARY KEY,
                    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                    session_id VARCHAR(64) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(message_id, session_id)
                )
            """))
            print("✅ Database migration completed")
        except Exception as e:
            print(f"Migration info: {e}")

    # 初始化种子数据
    await init_seed_data()

    yield


# 创建 FastAPI 应用
app = FastAPI(
    title="weisuandi.com",
    description="基于NFC/二维码的地点匿名留言平台",
    version="2.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


# ==================== API 端点 ====================

@app.get("/api/loc/{location_id}")
async def get_location(
    location_id: str,
    request: Request,
    response: Response,
    session_id: Optional[str] = Cookie(None)
):
    """
    获取地点信息 + 最近50条留言 + 当前在场人数
    同时更新 scan_count 和 presence 记录
    """
    # 生成或复用 session_id
    sid = await get_or_create_session_id(session_id)
    if not session_id:
        response.set_cookie(
            key="session_id",
            value=sid,
            max_age=30 * 24 * 60 * 60,  # 30天
            httponly=False,  # 前端需要读取
            samesite="lax"
        )

    async with AsyncSessionLocal() as db:
        # 查询地点
        result = await db.execute(
            select(Location).where(Location.id == location_id)
        )
        location = result.scalar_one_or_none()

        if not location:
            raise HTTPException(status_code=404, detail="地点不存在")

        # 增加 scan_count
        location.scan_count += 1

        # 查询最近50条留言（预加载点赞）
        msg_result = await db.execute(
            select(Message)
            .options(selectinload(Message.likes))
            .where(Message.location_id == location_id)
            .order_by(Message.created_at.desc())
            .limit(50)
        )
        messages = msg_result.scalars().all()

        # 查询在场人数（30分钟内活跃）
        thirty_min_ago = datetime.utcnow() - timedelta(minutes=30)
        presence_result = await db.execute(
            select(func.count(func.distinct(Presence.session_id)))
            .where(Presence.location_id == location_id)
            .where(Presence.last_seen > thirty_min_ago)
        )
        presence_count = presence_result.scalar() or 0

        # 更新或插入 presence 记录
        presence_result = await db.execute(
            select(Presence)
            .where(Presence.location_id == location_id)
            .where(Presence.session_id == sid)
        )
        presence = presence_result.scalar_one_or_none()

        if presence:
            presence.last_seen = datetime.utcnow()
        else:
            presence = Presence(
                location_id=location_id,
                session_id=sid,
                last_seen=datetime.utcnow()
            )
            db.add(presence)

        # 查询当前用户在该地点的昵称
        my_nickname = None
        nickname_result = await db.execute(
            select(Message.nickname)
            .where(Message.location_id == location_id)
            .where(Message.session_id == sid)
            .limit(1)
        )
        nickname_row = nickname_result.scalar_one_or_none()
        if nickname_row:
            my_nickname = nickname_row

        # 获取地点emoji
        location_emoji = next((loc["emoji"] for loc in LOCATIONS if loc["id"] == location_id), "📍")

        await db.commit()

        return {
            "location": {**location.to_dict(), "emoji": location_emoji},
            "messages": [msg.to_dict(sid) for msg in messages],
            "presence_count": presence_count,
            "my_nickname": my_nickname
        }


@app.post("/api/loc/{location_id}/msg")
async def post_message(
    location_id: str,
    request: Request,
    response: Response,
    session_id: Optional[str] = Cookie(None)
):
    """
    发送留言
    同一个 session_id 在同一个 location 用同一个昵称
    """
    # 生成或复用 session_id
    sid = await get_or_create_session_id(session_id)
    if not session_id:
        response.set_cookie(
            key="session_id",
            value=sid,
            max_age=30 * 24 * 60 * 60,
            httponly=False,
            samesite="lax"
        )

    # 解析请求体
    body = await request.json()
    content = body.get("content", "").strip()

    # 验证内容
    if not content:
        raise HTTPException(status_code=400, detail="留言内容不能为空")
    if len(content) > 280:
        raise HTTPException(status_code=400, detail="留言内容不能超过280字")

    async with AsyncSessionLocal() as db:
        # 检查地点是否存在
        result = await db.execute(
            select(Location).where(Location.id == location_id)
        )
        location = result.scalar_one_or_none()

        if not location:
            raise HTTPException(status_code=404, detail="地点不存在")

        # 查找该 session 在该地点的已有昵称
        nickname_result = await db.execute(
            select(Message.nickname)
            .where(Message.location_id == location_id)
            .where(Message.session_id == sid)
            .limit(1)
        )
        existing_nickname = nickname_result.scalar_one_or_none()

        if existing_nickname:
            nickname = existing_nickname
        else:
            nickname = generate_nickname()

        # 创建留言
        message = Message(
            location_id=location_id,
            content=content,
            nickname=nickname,
            session_id=sid,
            like_count=0,
            created_at=datetime.utcnow()
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)

        return message.to_dict(sid, check_likes=False)


@app.post("/api/loc/{location_id}/heartbeat")
async def heartbeat(
    location_id: str,
    request: Request,
    response: Response,
    session_id: Optional[str] = Cookie(None)
):
    """
    心跳：刷新 presence 的 last_seen
    前端每5分钟调用一次
    """
    # 生成或复用 session_id
    sid = await get_or_create_session_id(session_id)
    if not session_id:
        response.set_cookie(
            key="session_id",
            value=sid,
            max_age=30 * 24 * 60 * 60,
            httponly=False,
            samesite="lax"
        )

    async with AsyncSessionLocal() as db:
        # 检查地点是否存在
        result = await db.execute(
            select(Location).where(Location.id == location_id)
        )
        location = result.scalar_one_or_none()

        if not location:
            raise HTTPException(status_code=404, detail="地点不存在")

        # 更新或插入 presence 记录
        presence_result = await db.execute(
            select(Presence)
            .where(Presence.location_id == location_id)
            .where(Presence.session_id == sid)
        )
        presence = presence_result.scalar_one_or_none()

        if presence:
            presence.last_seen = datetime.utcnow()
        else:
            presence = Presence(
                location_id=location_id,
                session_id=sid,
                last_seen=datetime.utcnow()
            )
            db.add(presence)

        await db.commit()

        return {"ok": True}


@app.post("/api/msg/{message_id}/like")
async def toggle_like(
    message_id: int,
    request: Request,
    response: Response,
    session_id: Optional[str] = Cookie(None)
):
    """
    点赞/取消点赞留言
    """
    # 生成或复用 session_id
    sid = await get_or_create_session_id(session_id)
    if not session_id:
        response.set_cookie(
            key="session_id",
            value=sid,
            max_age=30 * 24 * 60 * 60,
            httponly=False,
            samesite="lax"
        )

    async with AsyncSessionLocal() as db:
        # 查询留言
        result = await db.execute(
            select(Message).where(Message.id == message_id)
        )
        message = result.scalar_one_or_none()

        if not message:
            raise HTTPException(status_code=404, detail="留言不存在")

        # 查询是否已点赞
        like_result = await db.execute(
            select(Like)
            .where(Like.message_id == message_id)
            .where(Like.session_id == sid)
        )
        existing_like = like_result.scalar_one_or_none()

        if existing_like:
            # 取消点赞
            await db.delete(existing_like)
            message.like_count = max(0, message.like_count - 1)
            liked = False
        else:
            # 添加点赞
            new_like = Like(
                message_id=message_id,
                session_id=sid,
                created_at=datetime.utcnow()
            )
            db.add(new_like)
            message.like_count += 1
            liked = True

        await db.commit()

        return {
            "liked": liked,
            "like_count": message.like_count
        }


@app.get("/api/stats")
async def get_stats():
    """
    简易后台统计
    返回所有地点的汇总数据
    """
    async with AsyncSessionLocal() as db:
        # 查询所有地点
        loc_result = await db.execute(select(Location).order_by(Location.created_at))
        locations = loc_result.scalars().all()

        thirty_min_ago = datetime.utcnow() - timedelta(minutes=30)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        stats = []
        for loc in locations:
            # 总留言数
            total_msg_result = await db.execute(
                select(func.count(Message.id))
                .where(Message.location_id == loc.id)
            )
            total_messages = total_msg_result.scalar() or 0

            # 今日留言数
            today_msg_result = await db.execute(
                select(func.count(Message.id))
                .where(Message.location_id == loc.id)
                .where(Message.created_at >= today_start)
            )
            today_messages = today_msg_result.scalar() or 0

            # 当前在场人数
            presence_result = await db.execute(
                select(func.count(func.distinct(Presence.session_id)))
                .where(Presence.location_id == loc.id)
                .where(Presence.last_seen > thirty_min_ago)
            )
            current_presence = presence_result.scalar() or 0

            # 获取emoji
            location_emoji = next((l["emoji"] for l in LOCATIONS if l["id"] == loc.id), "📍")

            stats.append({
                "id": loc.id,
                "name": loc.name,
                "emoji": location_emoji,
                "scan_count": loc.scan_count,
                "total_messages": total_messages,
                "today_messages": today_messages,
                "current_presence": current_presence
            })

        return {"locations": stats}


# ==================== 静态文件和前端路由 ====================

# 挂载静态文件目录
import os
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    """根路径：展示首页"""
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>weisuandi.com - 地点留言</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
                color: #e0e0e0;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 40px 20px;
            }
            .header {
                text-align: center;
                margin-bottom: 40px;
            }
            .logo {
                font-size: 3em;
                margin-bottom: 10px;
            }
            h1 {
                font-size: 2.5em;
                background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                margin-bottom: 10px;
            }
            .subtitle {
                color: #888;
                font-size: 1.1em;
            }
            .locations {
                max-width: 500px;
                width: 100%;
                display: flex;
                flex-direction: column;
                gap: 15px;
            }
            .location-item {
                display: flex;
                align-items: center;
                gap: 15px;
                padding: 20px;
                background: rgba(255,255,255,0.05);
                backdrop-filter: blur(10px);
                border-radius: 16px;
                text-decoration: none;
                color: #e0e0e0;
                transition: all 0.3s ease;
                border: 1px solid rgba(255,255,255,0.1);
            }
            .location-item:hover {
                transform: translateY(-3px);
                background: rgba(255,255,255,0.1);
                box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            }
            .location-emoji {
                font-size: 2.5em;
            }
            .location-info {
                flex: 1;
            }
            .location-name {
                font-size: 1.2em;
                font-weight: 600;
                margin-bottom: 5px;
            }
            .location-desc {
                font-size: 0.9em;
                color: #888;
            }
            .arrow {
                color: #666;
                font-size: 1.2em;
            }
            .footer {
                margin-top: 50px;
                text-align: center;
                color: #555;
                font-size: 0.85em;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <div class="logo">📍</div>
            <h1>weisuandi.com</h1>
            <p class="subtitle">扫描身边的二维码，留下你的话</p>
        </div>
        <div class="locations">
            <a class="location-item" href="/loc/library-main">
                <span class="location-emoji">📚</span>
                <div class="location-info">
                    <div class="location-name">图书馆</div>
                    <div class="location-desc">知识的海洋，卷王的战场</div>
                </div>
                <span class="arrow">→</span>
            </a>
            <a class="location-item" href="/loc/east9">
                <span class="location-emoji">🎓</span>
                <div class="location-info">
                    <div class="location-name">东九教学楼</div>
                    <div class="location-desc">上课、自习、发呆的地方</div>
                </div>
                <span class="arrow">→</span>
            </a>
            <a class="location-item" href="/loc/canteen-baiwei">
                <span class="location-emoji">🍜</span>
                <div class="location-info">
                    <div class="location-name">百味食堂</div>
                    <div class="location-desc">今天吃什么是永恒的难题</div>
                </div>
                <span class="arrow">→</span>
            </a>
            <a class="location-item" href="/loc/gym">
                <span class="location-emoji">🏃</span>
                <div class="location-info">
                    <div class="location-name">光谷体育馆</div>
                    <div class="location-desc">挥洒汗水的地方</div>
                </div>
                <span class="arrow">→</span>
            </a>
            <a class="location-item" href="/loc/dorm-south">
                <span class="location-emoji">🏠</span>
                <div class="location-info">
                    <div class="location-name">南边宿舍区</div>
                    <div class="location-desc">回到温暖的小窝</div>
                </div>
                <span class="arrow">→</span>
            </a>
        </div>
        <div class="footer">
            <p>Made with ❤️ for HUST</p>
        </div>
    </body>
    </html>
    """
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content)


@app.get("/loc/{path:path}")
async def serve_spa():
    """所有 /loc/* 路径返回 index.html，由前端 JS 处理路由"""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        from fastapi.responses import FileResponse
        return FileResponse(index_path)
    else:
        return {"error": "index.html not found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
