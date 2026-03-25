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
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_engine, get_async_session, AsyncSessionLocal
from models import Base, Location, Message, Presence, init_models


# 昵称生成词库
ADJECTIVES = [
    "安静的", "快乐的", "迷路的", "认真的", "困困的", "饥饿的", "好奇的", "勇敢的",
    "害羞的", "暴躁的", "优雅的", "沉默的", "活泼的", "懒散的", "机智的", "温柔的",
    "神秘的", "倔强的", "疲惫的", "淡定的"
]

ANIMALS = [
    "海豹", "熊猫", "柴犬", "猫头鹰", "企鹅", "水獭", "仓鼠", "考拉", "狐狸", "刺猬",
    "兔子", "鹦鹉", "海龟", "松鼠", "浣熊", "树懒", "白鲸", "柯基", "河马", "火烈鸟"
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化数据库"""
    async with async_engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)
    yield


# 创建 FastAPI 应用
app = FastAPI(
    title="weisuandi.com",
    description="基于NFC/二维码的地点匿名留言平台",
    version="1.0.0",
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

        # 查询最近50条留言
        msg_result = await db.execute(
            select(Message)
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

        await db.commit()

        return {
            "location": location.to_dict(),
            "messages": [msg.to_dict() for msg in messages],
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
            created_at=datetime.utcnow()
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)

        return message.to_dict()


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

            stats.append({
                "id": loc.id,
                "name": loc.name,
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
    """根路径：重定向到欢迎页"""
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>weisuandi.com - 地点留言</title>
        <style>
            body {
                font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
                background: #0a0a0a;
                color: #e0e0e0;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                margin: 0;
                padding: 20px;
            }
            .container {
                max-width: 480px;
                text-align: center;
            }
            h1 {
                font-size: 2em;
                margin-bottom: 10px;
            }
            p {
                color: #888;
                margin-bottom: 30px;
            }
            .locations {
                text-align: left;
            }
            .location-item {
                display: block;
                padding: 15px 20px;
                background: #1a1a1a;
                border-radius: 12px;
                margin-bottom: 10px;
                text-decoration: none;
                color: #e0e0e0;
                transition: background 0.2s;
            }
            .location-item:hover {
                background: #2a2a2a;
            }
            .location-name {
                font-weight: bold;
            }
            .location-desc {
                font-size: 0.85em;
                color: #888;
                margin-top: 5px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>weisuandi.com</h1>
            <p>扫描身边的二维码，留下你的话</p>
            <div class="locations">
                <a class="location-item" href="/loc/library-main">
                    <div class="location-name">图书馆</div>
                    <div class="location-desc">知识的海洋，卷王的战场</div>
                </a>
                <a class="location-item" href="/loc/east9">
                    <div class="location-name">东九教学楼</div>
                    <div class="location-desc">上课、自习、发呆的地方</div>
                </a>
                <a class="location-item" href="/loc/canteen-baiwei">
                    <div class="location-name">百味食堂</div>
                    <div class="location-desc">今天吃什么是永恒的难题</div>
                </a>
                <a class="location-item" href="/loc/gym">
                    <div class="location-name">光谷体育馆</div>
                    <div class="location-desc">挥洒汗水的地方</div>
                </a>
                <a class="location-item" href="/loc/dorm-south">
                    <div class="location-name">南边宿舍区</div>
                    <div class="location-desc">回到温暖的小窝</div>
                </a>
            </div>
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
