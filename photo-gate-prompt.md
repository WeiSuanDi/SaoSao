# 新功能：拍照入场 + 地点照片时间线

## 功能概述

用户扫码进入地点页面时，需要先拍一张现场照片才能解锁留言内容。这张照片会汇入该地点的"照片时间线"，成为这个空间的集体视觉记忆。

## 用户流程

### 首次到访某地点
1. 扫码 → 进入地点页面
2. 看到地点名称 + 大按钮"拍一张你眼前的画面，解锁这个空间"
3. 点击按钮 → 手机相机被唤起（使用后置摄像头）
4. 拍照完成 → 照片上传（显示上传进度）
5. 上传成功 → 过渡动画 → 进入留言页面
6. 留言页面顶部多了一个"照片时间线"区域，可以横向滑动浏览所有人拍的照片

### 再次到访同一地点
1. 扫码 → 进入地点页面
2. 看到一个轻提示："再拍一张？记录此刻的这里" + 拍照按钮 + 右上角小字"跳过"
3. 选择拍照 → 同上流程
4. 选择跳过 → 直接进入留言页面

### 判断逻辑
- 用 session_id（cookie）+ location_id 判断用户是否在该地点拍过照片
- 后端新增 API：GET /api/loc/{id}/has-photo?session_id=xxx，返回 true/false
- 或者直接在 GET /api/loc/{id} 的返回数据里加一个 has_photo 字段

## 数据库改动

### 新增 photos 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 自增主键 |
| location_id | VARCHAR(50) FK | 关联地点 |
| session_id | VARCHAR(64) | 上传者 session |
| image_url | VARCHAR(500) | 图片访问URL |
| thumbnail_url | VARCHAR(500) | 缩略图URL（可选，MVP先不做） |
| created_at | TIMESTAMP | 上传时间 |

### 修改 GET /api/loc/{id} 返回值
在返回的JSON里新增：
```json
{
  "has_photo": false,
  "photos": [
    { "id": 1, "image_url": "...", "created_at": "..." },
    { "id": 2, "image_url": "...", "created_at": "..." }
  ]
}
```
- has_photo: 当前 session 在该地点是否已上传过照片
- photos: 该地点最近的20张照片（按时间倒序）

## 后端新增 API

### POST /api/loc/{location_id}/photo
上传一张照片。

- 接收 multipart/form-data，字段名 "photo"
- 限制文件大小 <= 5MB
- 只接受 image/jpeg, image/png, image/webp
- 后端处理：
  1. 用 Pillow 压缩图片：max 1200px 宽，质量 80%，转为 JPEG
  2. 保存图片文件到服务器本地 `uploads/` 目录（MVP方案）
  3. 文件名格式：`{location_id}_{timestamp}_{random6}.jpg`
  4. image_url 存为 `/uploads/{filename}`
  5. 插入 photos 表记录
  6. 返回 `{ "ok": true, "photo": { ... } }`

### 静态文件服务
- FastAPI 挂载 `uploads/` 目录为静态文件路由：`/uploads/`
- 注意：Railway 部署时 uploads 目录在容器内，重新部署会丢失
- MVP阶段先接受这个限制，后续可迁移到 Cloudflare R2 或 S3

## 前端改动

### 拍照门禁页面（photo-gate）

在 app.js 里，加载地点数据后判断 has_photo：
- 如果 has_photo === false：显示拍照门禁页面
- 如果 has_photo === true：显示轻提示（可跳过），然后进入留言页

#### 拍照门禁页面 UI
```
[地点图标]
[地点名称]

"拍一张你眼前的画面"
"解锁这个空间"

[ 📷 拍照按钮（大的、居中的圆形按钮）]
```

#### 再次到访轻提示 UI
```
顶部横幅，半透明背景：
"再拍一张？记录此刻的这里"  [📷 拍] [跳过 →]
```
横幅3秒后自动淡出，也可以手动关掉。

#### 拍照实现
```html
<!-- 隐藏的 input，capture="environment" 打开后置摄像头 -->
<input type="file" id="camera-input" accept="image/*" capture="environment" style="display:none">
```
JS里点击拍照按钮时触发 `document.getElementById('camera-input').click()`。
监听 input 的 change 事件获取文件，用 FormData 上传到后端。

#### 上传过程
- 显示上传进度动画（一个简单的圆形进度或脉搏动画就行）
- 上传成功后，播放一个短暂的过渡效果（比如照片缩小飞到顶部照片区域的位置），然后显示留言内容

### 照片时间线区域

在留言页面的地点信息区域下方、留言列表上方，插入一个可以横向滚动的照片条：

```
照片时间线样式：
- 高度约 120px
- 照片以正方形缩略图展示，80x80px，圆角 8px
- 横向排列，可左右滑动（overflow-x: auto, scroll-snap）
- 每张照片下方小字显示相对时间（"2小时前"、"昨天"）
- 点击某张照片可放大查看（简易 lightbox，全屏黑色背景 + 图片居中）
- 如果没有照片（新地点），显示占位文字："还没有人记录这里的样子"
```

### 发留言时也可以附图（可选增强）

在留言输入栏的左侧加一个小相机图标，点击可以附带一张图片和留言一起发送。
这个功能如果增加工作量太大，可以先不做，先把拍照门禁和时间线做好。

## 样式要求

- 拍照门禁页面延续现有暗色主题
- 拍照按钮用紫色渐变圆形（和现有 UI 的紫色调一致），大而明显
- 照片时间线区域背景略深于页面背景，有微妙的分隔感
- 照片加载时显示一个灰色骨架屏占位
- lightbox 查看时背景用 rgba(0,0,0,0.9)

## 关键注意事项

1. **隐私**：照片里可能拍到人脸。MVP阶段在拍照页面加一行小字提示："请避免拍摄他人面部"
2. **存储**：MVP用本地文件存储，Railway重新部署会丢失数据。可以接受，后续迁移到对象存储
3. **压缩**：手机拍的照片动辄5-10MB，后端必须用Pillow压缩后再存储
4. **体验**：上传过程要有明确的反馈，不能让用户觉得卡住了
5. **Fallback**：如果用户拒绝相机权限，提示"需要相机权限来记录这个空间"，但也提供一个"从相册选择"的备选
