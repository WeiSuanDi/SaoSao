/**
 * weisuandi.com v2.0 前端逻辑
 */

// 配置
const HEARTBEAT_INTERVAL = 5 * 60 * 1000; // 5分钟
const REFRESH_INTERVAL = 30 * 1000; // 30秒
const TOAST_DURATION = 2500;

// 状态
let locationId = null;
let myNickname = null;
let heartbeatTimer = null;
let refreshTimer = null;
let isLoading = false;
let theme = localStorage.getItem('theme') || 'dark';

// 初始化主题
document.documentElement.setAttribute('data-theme', theme);

/**
 * 显示 Toast 提示
 */
function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, TOAST_DURATION);
}

/**
 * 切换主题
 */
function toggleTheme() {
    theme = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    showToast(theme === 'dark' ? '已切换到暗色模式' : '已切换到亮色模式');
}

/**
 * 滚动到输入框
 */
function scrollToInput() {
    document.getElementById('messageInput').focus();
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
}

/**
 * 从 URL 解析 location_id
 */
function parseLocationId() {
    const path = window.location.pathname;
    const match = path.match(/^\/loc\/(.+)$/);
    return match ? match[1] : null;
}

/**
 * 生成 UUID
 */
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

/**
 * 获取或创建 session_id
 */
function getOrCreateSessionId() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'session_id') {
            return value;
        }
    }
    const sessionId = generateUUID();
    document.cookie = `session_id=${sessionId}; max-age=${30 * 24 * 60 * 60}; path=/`;
    return sessionId;
}

/**
 * 根据昵称生成颜色类名
 */
function getNicknameColorClass(nickname) {
    let hash = 0;
    for (let i = 0; i < nickname.length; i++) {
        hash = nickname.charCodeAt(i) + ((hash << 5) - hash);
    }
    const index = Math.abs(hash) % 15 + 1;
    return `nick-${index}`;
}

/**
 * 格式化相对时间
 */
function formatRelativeTime(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;

    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (seconds < 60) {
        return '刚刚';
    } else if (minutes < 60) {
        return `${minutes}分钟前`;
    } else if (hours < 24) {
        return `${hours}小时前`;
    } else if (days < 7) {
        return `${days}天前`;
    } else {
        return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
    }
}

/**
 * HTML 转义防 XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 渲染留言列表
 */
function renderMessages(messages) {
    const container = document.getElementById('messages');
    const emptyState = document.getElementById('emptyState');

    container.innerHTML = '';

    if (messages.length === 0) {
        emptyState.style.display = 'block';
        return;
    }

    emptyState.style.display = 'none';

    messages.forEach(msg => {
        const card = document.createElement('div');
        card.className = 'message-card';
        card.dataset.id = msg.id;

        const liked = msg.liked ? 'liked' : '';
        const heartFill = msg.liked ? 'fill="currentColor"' : '';

        card.innerHTML = `
            <div class="message-header">
                <span class="message-nickname">
                    <span class="nickname-badge ${getNicknameColorClass(msg.nickname)}">${escapeHtml(msg.nickname)}</span>
                </span>
                <span class="message-time">${formatRelativeTime(msg.created_at)}</span>
            </div>
            <div class="message-content">${escapeHtml(msg.content)}</div>
            <div class="message-footer">
                <button class="like-btn ${liked}" onclick="toggleLike(${msg.id}, this)">
                    <svg class="heart-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ${heartFill}>
                        <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                    </svg>
                    <span class="like-count">${msg.like_count || 0}</span>
                </button>
            </div>
        `;
        container.appendChild(card);
    });
}

/**
 * 添加一条新留言到顶部（乐观更新）
 */
function prependMessage(msg) {
    const container = document.getElementById('messages');
    const emptyState = document.getElementById('emptyState');
    emptyState.style.display = 'none';

    const card = document.createElement('div');
    card.className = 'message-card new';
    card.dataset.id = msg.id;

    card.innerHTML = `
        <div class="message-header">
            <span class="message-nickname">
                <span class="nickname-badge ${getNicknameColorClass(msg.nickname)}">${escapeHtml(msg.nickname)}</span>
            </span>
            <span class="message-time">刚刚</span>
        </div>
        <div class="message-content">${escapeHtml(msg.content)}</div>
        <div class="message-footer">
            <button class="like-btn" onclick="toggleLike(${msg.id}, this)">
                <svg class="heart-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                </svg>
                <span class="like-count">0</span>
            </button>
        </div>
    `;
    container.insertBefore(card, container.firstChild);
}

/**
 * 点赞/取消点赞
 */
async function toggleLike(messageId, btn) {
    try {
        const response = await fetch(`/api/msg/${messageId}/like`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error('操作失败');
        }

        const data = await response.json();

        // 更新UI
        const countEl = btn.querySelector('.like-count');
        countEl.textContent = data.like_count;

        if (data.liked) {
            btn.classList.add('liked');
        } else {
            btn.classList.remove('liked');
        }
    } catch (error) {
        console.error('点赞失败:', error);
        showToast('操作失败，请重试');
    }
}

/**
 * 显示 404 页面
 */
function showNotFound() {
    document.querySelector('.header').style.display = 'none';
    document.querySelector('.quick-actions').style.display = 'none';
    document.getElementById('messages').style.display = 'none';
    document.getElementById('inputBar').style.display = 'none';
    document.getElementById('loading').style.display = 'none';
    document.getElementById('notFound').style.display = 'block';
}

/**
 * 显示/隐藏加载状态
 */
function setLoading(loading) {
    isLoading = loading;
    document.getElementById('loading').style.display = loading ? 'block' : 'none';
}

/**
 * 加载地点数据
 */
async function loadLocation() {
    setLoading(true);

    try {
        const response = await fetch(`/api/loc/${locationId}`);

        if (!response.ok) {
            if (response.status === 404) {
                showNotFound();
                return;
            }
            throw new Error('加载失败');
        }

        const data = await response.json();

        // 更新页面标题
        document.title = `${data.location.name} - weisuandi.com`;

        // 更新头部信息
        document.getElementById('locationName').textContent = data.location.name;
        document.getElementById('locationDesc').textContent = data.location.description || '';
        document.getElementById('locationEmoji').textContent = data.location.emoji || '📍';

        // 更新在场人数
        document.getElementById('presenceCount').textContent = data.presence_count;

        // 保存我的昵称
        myNickname = data.my_nickname;

        // 渲染照片时间线
        renderPhotos(data.photos || []);

        // 检查是否需要拍照门禁
        if (!data.has_photo) {
            // 首次访问，显示拍照门禁
            showPhotoGate(data.location);
        } else {
            // 已拍过照，显示留言页面
            showMainContent();
            renderMessages(data.messages);
        }

        // 启动心跳
        startHeartbeat();

        // 启动轮询刷新
        startRefresh();

    } catch (error) {
        console.error('加载地点数据失败:', error);
        showToast('加载失败，请刷新重试');
    } finally {
        setLoading(false);
    }
}

/**
 * 刷新留言列表
 */
async function refreshMessages() {
    if (isLoading) return;

    try {
        const response = await fetch(`/api/loc/${locationId}`);
        if (!response.ok) return;

        const data = await response.json();

        // 更新在场人数
        document.getElementById('presenceCount').textContent = data.presence_count;

        // 渲染留言（保持滚动位置）
        const scrollPos = window.scrollY;
        renderMessages(data.messages);
        window.scrollTo(0, scrollPos);

    } catch (error) {
        console.error('刷新失败:', error);
    }
}

/**
 * 发送留言
 */
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const content = input.value.trim();

    if (!content) {
        showToast('请输入留言内容');
        return;
    }

    // 清空输入框
    input.value = '';
    updateCharCount();

    // 乐观更新：先显示留言
    const tempMsg = {
        id: Date.now(),
        nickname: myNickname || '匿名用户',
        content: content,
        like_count: 0,
        liked: false
    };
    prependMessage(tempMsg);

    try {
        const response = await fetch(`/api/loc/${locationId}/msg`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ content })
        });

        if (!response.ok) {
            throw new Error('发送失败');
        }

        const msg = await response.json();

        // 更新我的昵称
        myNickname = msg.nickname;

        // 更新刚插入的卡片
        const firstCard = document.querySelector('.message-card');
        if (firstCard) {
            firstCard.dataset.id = msg.id;
            const nicknameEl = firstCard.querySelector('.nickname-badge');
            nicknameEl.textContent = msg.nickname;
            nicknameEl.className = `nickname-badge ${getNicknameColorClass(msg.nickname)}`;

            // 更新点赞按钮的onclick
            const likeBtn = firstCard.querySelector('.like-btn');
            likeBtn.setAttribute('onclick', `toggleLike(${msg.id}, this)`);
        }

        showToast('留言成功');

    } catch (error) {
        console.error('发送留言失败:', error);
        showToast('发送失败，请重试');
        // 移除乐观添加的卡片
        const firstCard = document.querySelector('.message-card');
        if (firstCard && firstCard.dataset.id == tempMsg.id) {
            firstCard.remove();
        }
    }
}


// ==================== 拍照门禁功能 ====================

/**
 * 显示拍照门禁页面
 */
function showPhotoGate(location) {
    document.getElementById('photoGate').style.display = 'flex';
    document.getElementById('gateEmoji').textContent = location.emoji || '📍';
    document.getElementById('gateLocationName').textContent = location.name;
    document.getElementById('mainContent').style.display = 'none';
    document.getElementById('inputBar').style.display = 'none';
}

/**
 * 显示主内容（已拍照后）
 */
function showMainContent() {
    document.getElementById('photoGate').style.display = 'none';
    document.getElementById('mainContent').style.display = 'block';
    document.getElementById('inputBar').style.display = 'flex';
    document.getElementById('photoTimeline').style.display = 'block';
}

/**
 * 打开相机
 */
function openCamera() {
    document.getElementById('camera-input').click();
}

/**
 * 处理照片选择
 */
async function handlePhotoSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    // 验证文件类型
    if (!file.type.startsWith('image/')) {
        showToast('请选择图片文件');
        return;
    }

    // 验证文件大小 (5MB)
    if (file.size > 5 * 1024 * 1024) {
        showToast('图片大小不能超过 5MB');
        return;
    }

    // 显示上传状态
    showUploadProgress();

    try {
        const formData = new FormData();
        formData.append('photo', file);

        const response = await fetch(`/api/loc/${locationId}/photo`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '上传失败');
        }

        const data = await response.json();

        // 隐藏上传进度
        hideUploadProgress();

        // 显示成功动画
        showToast('照片上传成功！');

        // 切换到主内容
        setTimeout(() => {
            showMainContent();
            // 刷新数据
            refreshMessages();
        }, 500);

    } catch (error) {
        console.error('上传照片失败:', error);
        hideUploadProgress();
        showToast(error.message || '上传失败，请重试');
    }

    // 清空input，允许再次选择同一文件
    event.target.value = '';
}

/**
 * 显示上传进度
 */
function showUploadProgress() {
    const gateContent = document.querySelector('.gate-content');
    gateContent.innerHTML = `
        <div class="upload-progress">
            <div class="upload-spinner"></div>
            <p>正在上传照片...</p>
        </div>
    `;
}

/**
 * 隐藏上传进度
 */
function hideUploadProgress() {
    // upload progress 会在 showMainContent 时被移除
}

/**
 * 渲染照片时间线
 */
function renderPhotos(photos) {
    const container = document.getElementById('timelinePhotos');
    const hint = document.getElementById('timelineHint');

    if (!photos || photos.length === 0) {
        hint.style.display = 'block';
        container.innerHTML = '';
        return;
    }

    hint.style.display = 'none';
    container.innerHTML = '';

    photos.forEach(photo => {
        const div = document.createElement('div');
        div.className = 'timeline-photo';
        div.innerHTML = `
            <img src="data:image/jpeg;base64,${photo.image_data}" alt="地点照片" loading="lazy">
            <div class="timeline-photo-time">${formatRelativeTime(photo.created_at)}</div>
        `;
        div.onclick = () => openLightbox(`data:image/jpeg;base64,${photo.image_data}`);
        container.appendChild(div);
    });
}

/**
 * 打开灯箱查看大图
 */
function openLightbox(imageUrl) {
    // 创建灯箱
    const lightbox = document.createElement('div');
    lightbox.className = 'lightbox';
    lightbox.id = 'lightbox';
    lightbox.innerHTML = `
        <img src="${imageUrl}" alt="大图">
        <button class="lightbox-close" onclick="closeLightbox()">✕</button>
    `;
    lightbox.onclick = (e) => {
        if (e.target === lightbox) {
            closeLightbox();
        }
    };
    document.body.appendChild(lightbox);
    document.body.style.overflow = 'hidden';
}

/**
 * 关闭灯箱
 */
function closeLightbox() {
    const lightbox = document.getElementById('lightbox');
    if (lightbox) {
        lightbox.remove();
        document.body.style.overflow = '';
    }
}

/**
 * 心跳：保持在线状态
 */
async function sendHeartbeat() {
    try {
        await fetch(`/api/loc/${locationId}/heartbeat`, {
            method: 'POST'
        });
    } catch (error) {
        console.error('心跳失败:', error);
    }
}

/**
 * 启动心跳定时器
 */
function startHeartbeat() {
    if (heartbeatTimer) {
        clearInterval(heartbeatTimer);
    }
    heartbeatTimer = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL);
}

/**
 * 启动刷新定时器
 */
function startRefresh() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
    }
    refreshTimer = setInterval(refreshMessages, REFRESH_INTERVAL);
}

/**
 * 更新字符计数
 */
function updateCharCount() {
    const input = document.getElementById('messageInput');
    const count = document.getElementById('charCount');
    const len = input.value.length;

    count.textContent = len;

    const countContainer = count.parentElement;
    countContainer.classList.remove('warning', 'error');

    if (len > 250) {
        countContainer.classList.add('error');
    } else if (len > 200) {
        countContainer.classList.add('warning');
    }
}

/**
 * 自动调整输入框高度
 */
function autoResize() {
    const input = document.getElementById('messageInput');
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
}

/**
 * 创建背景粒子
 */
function createParticles() {
    const container = document.getElementById('particles');
    const particleCount = 20;

    for (let i = 0; i < particleCount; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.animationDelay = Math.random() * 20 + 's';
        particle.style.animationDuration = (15 + Math.random() * 10) + 's';
        container.appendChild(particle);
    }
}

/**
 * 初始化
 */
function init() {
    // 解析 location_id
    locationId = parseLocationId();

    if (!locationId) {
        showNotFound();
        return;
    }

    // 确保 session_id 存在
    getOrCreateSessionId();

    // 创建背景粒子
    createParticles();

    // 初始化拍照功能
    initPhotoGate();

    // 加载数据
    loadLocation();

    // 绑定输入事件
    const input = document.getElementById('messageInput');

    input.addEventListener('input', () => {
        updateCharCount();
        autoResize();
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // 初始字符计数
    updateCharCount();
}

/**
 * 初始化拍照门禁功能
 */
function initPhotoGate() {
    // 绑定相机 input 事件
    const cameraInput = document.getElementById('camera-input');
    if (cameraInput) {
        cameraInput.addEventListener('change', handlePhotoSelect);
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', init);
