# weisuandi.com - 基于 NFC/二维码的地点匿名留言平台

一个极简的地点绑定匿名留言平台。用户在校园里扫 NFC 贴纸或二维码，浏览器自动打开对应地点的网页，可以看到该地点的匿名留言、当前在场人数，也可以留下自己的话。

## 功能特点

- 扫码即可查看地点留言
- 匿名昵称自动生成（形容词+动物）
- 实时显示在场人数
- 暗色主题，克制安静的界面设计
- 移动端优先，适配各种屏幕

## 技术栈

- **后端**: Python 3.11 + FastAPI + SQLAlchemy + asyncpg
- **前端**: 纯 HTML + CSS + vanilla JS（无框架）
- **数据库**: PostgreSQL（生产）/ SQLite（开发）
- **部署**: Railway

## 本地开发

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 初始化数据

```bash
python seed.py
```

这会创建 5 个华科校园地点和种子留言数据。

### 3. 启动服务

```bash
uvicorn main:app --reload
```

访问 http://localhost:8000 查看效果。

### 4. 生成二维码

```bash
python gen_qr.py
```

二维码图片会保存在 `qrcodes/` 目录下。

## 部署到 Railway

1. 将代码推送到 GitHub
2. 在 Railway 创建新项目，连接 GitHub 仓库
3. 添加 PostgreSQL 插件
4. Railway 会自动检测 FastAPI 项目并部署

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/loc/{location_id}` | 获取地点信息、留言列表、在场人数 |
| POST | `/api/loc/{location_id}/msg` | 发送留言 |
| POST | `/api/loc/{location_id}/heartbeat` | 心跳保活 |
| GET | `/api/stats` | 统计数据 |

## 项目结构

```
weisuandi/
├── main.py              # FastAPI 应用入口
├── models.py            # SQLAlchemy 数据模型
├── database.py          # 数据库连接配置
├── seed.py              # 初始化地点 + 种子留言
├── gen_qr.py            # 批量生成二维码
├── requirements.txt     # Python 依赖
├── Procfile             # Railway 启动命令
├── static/
│   ├── index.html       # 地点留言页面
│   ├── style.css        # 样式
│   └── app.js           # 前端逻辑
└── README.md
```

## License

MIT
