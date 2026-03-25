# 项目：weisuandi.com — 基于NFC/二维码的地点匿名留言平台

## 项目概述

一个极简的地点绑定匿名留言平台。用户在校园里扫NFC贴纸或二维码，浏览器自动打开对应地点的网页，可以看到该地点的匿名留言、当前在场人数，也可以留下自己的话。

域名：weisuandi.com  
部署平台：Railway（免费tier）  
数据库：Railway PostgreSQL 插件

---

## 技术栈

- **后端**: Python 3.11 + FastAPI + SQLAlchemy + asyncpg
- **前端**: 纯 HTML + CSS + vanilla JS（无框架）
- **数据库**: PostgreSQL（Railway 插件）
- **部署**: Railway（自动从 GitHub 部署）

---

## 项目结构

```
weisuandi/
├── main.py              # FastAPI 应用入口
├── models.py            # SQLAlchemy 数据模型（3张表）
├── database.py          # 数据库连接配置
├── seed.py              # 初始化地点 + 种子留言脚本
├── gen_qr.py            # 批量生成二维码脚本
├── requirements.txt     # Python 依赖
├── Procfile             # Railway 启动命令
├── static/
│   ├── index.html       # 地点留言页面
│   ├── style.css        # 样式
│   └── app.js           # 前端逻辑
└── README.md
```

---

## 数据库设计（3张表）

### locations 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(50) PK | 地点标识，如 "library-3f" |
| name | VARCHAR(100) | 展示名，如 "图书馆三楼" |
| description | VARCHAR(200) | 简短描述，可选 |
| scan_count | INTEGER DEFAULT 0 | 累计扫码次数 |
| created_at | TIMESTAMP | 创建时间 |

### messages 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 自增主键 |
| location_id | VARCHAR(50) FK | 关联地点 |
| content | VARCHAR(280) | 留言内容，限280字 |
| nickname | VARCHAR(30) | 随机匿名昵称 |
| session_id | VARCHAR(64) | 浏览器 session 标识 |
| created_at | TIMESTAMP | 发布时间 |

### presence 表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 自增主键 |
| location_id | VARCHAR(50) FK | 关联地点 |
| session_id | VARCHAR(64) | 浏览器 session 标识 |
| last_seen | TIMESTAMP | 最后活跃时间 |
| UNIQUE(location_id, session_id) | | 联合唯一约束 |

---

## 后端 API 设计（4个 endpoint）

### 1. GET /api/loc/{location_id}
获取地点信息 + 最近50条留言 + 当前在场人数。

- 同时将 scan_count + 1
- 同时更新或插入调用者的 presence 记录
- session_id 从 cookie 读取，如果没有则在响应中 set-cookie 一个随机 UUID

响应示例：
```json
{
  "location": { "id": "library-3f", "name": "图书馆三楼", "description": "..." },
  "messages": [
    { "id": 1, "content": "四楼靠窗那排插座最多", "nickname": "安静的海豹", "created_at": "..." }
  ],
  "presence_count": 3,
  "my_nickname": "安静的海豹"
}
```

### 2. POST /api/loc/{location_id}/msg
发一条留言。

- request body: `{ "content": "留言内容" }`
- content 不能为空，最长280字符
- nickname 逻辑：同一个 session_id 在同一个 location 用同一个昵称。如果是该 session 第一次在该地点发言，从词库随机生成一个（形容词+动物），存入 messages 表。后续同 session 同 location 复用。
- 返回创建的 message 对象

### 3. POST /api/loc/{location_id}/heartbeat
前端每5分钟调一次，刷新 presence 的 last_seen。

- 仅更新 last_seen = now()
- 返回 `{ "ok": true }`

### 4. GET /api/stats
简易后台统计，返回所有地点的汇总数据。

- 返回每个 location 的 scan_count、total_messages、today_messages、current_presence
- 无需鉴权（MVP阶段）

---

## 匿名昵称生成

用两个中文列表随机组合：

形容词列表（至少20个）：安静的、快乐的、迷路的、认真的、困困的、饥饿的、好奇的、勇敢的、害羞的、暴躁的、优雅的、沉默的、活泼的、懒散的、机智的、温柔的、神秘的、倔强的、疲惫的、淡定的

动物列表（至少20个）：海豹、熊猫、柴犬、猫头鹰、企鹅、水獭、仓鼠、考拉、狐狸、刺猬、兔子、鹦鹉、海龟、松鼠、浣熊、树懒、白鲸、柯基、河马、火烈鸟

生成格式："形容词+动物"，如 "安静的海豹"、"迷路的企鹅"

---

## 前端设计要求

### index.html
- 单页面，URL path 为 `/loc/{location_id}`
- FastAPI 对所有 `/loc/*` 路径返回同一个 index.html，前端 JS 从 URL 解析 location_id

### 页面结构（从上到下）
1. **顶部区域**：地点名称（大字）+ 地点描述（小字）
2. **在场指示器**：一个小 pill/badge 显示 "当前 X 人在此"，带一个小圆点呼吸动画表示实时
3. **留言流**：按时间倒序，每条显示 nickname、content、相对时间（如"3分钟前"）
4. **底部输入栏**：固定在底部，一个输入框 + 发送按钮。placeholder 文字："在这里留下你的话..."

### 样式要求
- Mobile-first，宽度 100%，max-width 480px 居中
- 暗色主题，背景 #0a0a0a，文字 #e0e0e0
- 留言卡片用微妙的深灰色背景 #1a1a1a，圆角 12px
- nickname 用一个随机但固定的柔和色彩（基于 nickname 字符串 hash）
- 底部输入栏背景略深，有上边框分隔
- 字体用系统默认：-apple-system, "PingFang SC", "Microsoft YaHei", sans-serif
- 整体感觉：克制、安静、像一面隐形的墙

### app.js 逻辑
1. 页面加载时从 URL 解析 location_id
2. 检查 cookie 中有无 session_id，没有则生成 UUID 并写入 cookie
3. 调用 GET /api/loc/{location_id} 获取数据并渲染
4. 发送留言：POST 后乐观更新 UI（先显示，不等后端返回）
5. 设置 setInterval 每5分钟调 heartbeat
6. 设置 setInterval 每30秒刷新留言列表（轮询）
7. 相对时间显示：用 JS 计算 "刚刚"、"X分钟前"、"X小时前"、"X天前"
8. 如果 location_id 不存在（API 返回 404），显示一个友好的 "这个地点还没有被开启" 提示页

---

## seed.py — 初始化数据

创建以下5个华科校园地点，并为每个地点插入3-5条种子留言：

```python
locations = [
    {"id": "library-main", "name": "图书馆", "description": "知识的海洋，卷王的战场"},
    {"id": "east9", "name": "东九教学楼", "description": "上课、自习、发呆的地方"},
    {"id": "canteen-baiwei", "name": "百味食堂", "description": "今天吃什么是永恒的难题"},
    {"id": "gym", "name": "光谷体育馆", "description": "挥洒汗水的地方"},
    {"id": "dorm-south", "name": "南边宿舍区", "description": "回到温暖的小窝"},
]
```

种子留言要写得像真实用户会说的话，有生活气息，比如：
- 图书馆："三楼西区今天人好少，赚到了"
- 东九："这个教室的空调永远是个谜"
- 食堂："二楼新来的麻辣香锅可以的"
- 体育馆："有没有人周末打羽毛球"
- 宿舍："又到了纠结洗不洗澡的时间"

每条种子留言用不同的随机昵称。

---

## gen_qr.py — 生成二维码

- 读取数据库中所有 location
- 为每个 location 生成一个二维码 PNG
- 二维码内容为 `https://weisuandi.com/loc/{location_id}`
- 文件保存为 `qrcodes/{location_id}.png`
- 二维码下方附带地点名称文字（用 Pillow 添加）

依赖：qrcode, Pillow

---

## Railway 部署配置

### Procfile
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### requirements.txt
```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy[asyncio]==2.0.35
asyncpg==0.30.0
psycopg2-binary==2.9.9
python-multipart==0.0.12
qrcode[pil]==7.4.2
Pillow==10.4.0
```

### 环境变量
Railway 添加 PostgreSQL 插件后会自动注入 `DATABASE_URL` 环境变量。
database.py 从 `os.environ["DATABASE_URL"]` 读取连接字符串。
注意 Railway 的 DATABASE_URL 格式是 `postgresql://...`，SQLAlchemy 需要 `postgresql+asyncpg://...`，代码里做个替换。

### 静态文件服务
FastAPI 用 `StaticFiles` mount `/static` 目录。
对于 `/loc/{path:path}` 路由，返回 `static/index.html`（让前端 JS 处理路由）。
根路径 `/` 重定向到一个简单的欢迎页或者第一个地点。

---

## CORS 配置

允许所有来源（MVP阶段）：
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)
```

---

## 关键实现细节

1. **Session Cookie**: 用 `httponly=False` 的 cookie 存 session_id（前端也需要读取来发送 heartbeat）。过期时间设30天。

2. **在场人数计算**: `SELECT COUNT(DISTINCT session_id) FROM presence WHERE location_id = ? AND last_seen > NOW() - INTERVAL '30 minutes'`

3. **昵称一致性**: 同一个 session_id 在同一个 location_id 下昵称不变。查询逻辑：先查 messages 表中该 session+location 的已有昵称，有就复用，没有就新生成。

4. **时区**: 所有时间存 UTC。前端用 JS 转换为本地时间显示。

5. **安全**: MVP 阶段不需要用户注册登录。留言内容做基本的 HTML 转义防 XSS。限制 content 长度 <= 280。

---

## 请帮我完成

请按照以上规格，生成完整的项目代码。确保：

1. 所有文件都可以直接运行
2. 本地开发时支持 SQLite 作为 fallback（当 DATABASE_URL 环境变量不存在时）
3. 代码有清晰的中文注释
4. 先 `python seed.py` 初始化数据，然后 `uvicorn main:app --reload` 就能在本地跑起来
5. push 到 GitHub 后 Railway 能直接部署
