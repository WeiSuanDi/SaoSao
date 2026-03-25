# weisuandi.com - 基于 NFC/二维码的地点匿名留言平台

## 项目概述

一个极简的地点绑定匿名留言平台。用户在校园里扫 NFC 贴纸或二维码，浏览器自动打开对应地点的网页，可以看到该地点的匿名留言、当前在场人数，也可以留下自己的话。

- **域名**: weisuandi.com
- **部署平台**: Railway（免费 tier）
- **数据库**: Railway PostgreSQL 插件
- **GitHub**: https://github.com/WeiSuanDi/SaoSao

## 技术栈

- **后端**: Python 3.11+ FastAPI + SQLAlchemy + asyncpg
- **前端**: 纯 HTML + CSS + vanilla JS（无框架）
- **数据库**: PostgreSQL（生产）/ SQLite（本地开发）
- **部署**: Railway（自动从 GitHub 部署）

## 项目结构

```
weisuandi/
├── main.py              # FastAPI 应用入口
├── models.py            # SQLAlchemy 数据模型（4张表）
├── database.py          # 数据库连接配置
├── seed.py              # 初始化地点 + 种子留言脚本
├── gen_qr.py            # 批量生成二维码脚本
├── requirements.txt     # Python 依赖
├── Procfile             # Railway 启动命令
├── static/
│   ├── index.html       # 地点留言页面
│   ├── style.css        # 样式
│   └── app.js           # 前端逻辑
├── CLAUDE.md            # 项目说明（本文件）
└── README.md            # 项目文档
```

## 数据库模型

### locations 表
- `id`: VARCHAR(50) PK - 地点标识
- `name`: VARCHAR(100) - 展示名
- `description`: VARCHAR(200) - 简短描述
- `scan_count`: INTEGER - 累计扫码次数

### messages 表
- `id`: SERIAL PK
- `location_id`: VARCHAR(50) FK
- `content`: VARCHAR(280) - 留言内容
- `nickname`: VARCHAR(30) - 随机匿名昵称
- `session_id`: VARCHAR(64) - 浏览器 session 标识
- `like_count`: INTEGER - 点赞数
- `created_at`: TIMESTAMP

### likes 表
- `id`: SERIAL PK
- `message_id`: INTEGER FK
- `session_id`: VARCHAR(64)
- UNIQUE(message_id, session_id)

### presence 表
- `id`: SERIAL PK
- `location_id`: VARCHAR(50) FK
- `session_id`: VARCHAR(64)
- `last_seen`: TIMESTAMP

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/loc/{location_id}` | 获取地点信息、留言、在场人数 |
| POST | `/api/loc/{location_id}/msg` | 发送留言 |
| POST | `/api/loc/{location_id}/heartbeat` | 心跳保活 |
| POST | `/api/msg/{message_id}/like` | 点赞/取消点赞 |
| GET | `/api/stats` | 统计数据 |

## 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化数据
python seed.py

# 启动服务
uvicorn main:app --reload

# 生成二维码
python gen_qr.py
```

## 部署流程

1. 代码推送到 GitHub
2. Railway 自动检测并部署
3. 访问 https://weisuandi.com

## 开发约定

### 代码风格
- Python 使用中文注释
- 前端使用 ES6+ 语法
- 时间统一使用 UTC 存储，前端显示时转换为本地时间

### 昵称生成
- 格式：形容词 + 动物（如"安静的海豹"）
- 词库在 main.py 中定义
- 同一 session 在同一 location 保持昵称不变

### 前端主题
- 默认暗色主题
- 支持暗色/亮色切换
- CSS 变量定义在 :root 中

## 常见问题

### 发送留言报错
- 检查数据库迁移是否完成
- 检查 to_dict 方法是否正确处理

### 时间显示不正确
- 确保时间字符串以 'Z' 结尾表示 UTC
- 前端 formatRelativeTime 函数处理相对时间

### 自定义域名 502
- 检查 Railway Custom Domain 配置
- 确认 DNS CNAME 记录正确指向 Railway
