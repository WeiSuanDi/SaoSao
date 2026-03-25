/**
 * weisuandi.com 前端逻辑
 */

// 配置
const HEARTBEAT_INTERVAL = 5 * 60 * 1000; // 5分钟
const REFRESH_INTERVAL = 30 * 1000; // 30秒

// 状态
let locationId = null;
let myNickname = null;
let heartbeatTimer = null;
let refreshTimer = null;

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
    // 没有则创建一个新的
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
    } else if (days < 30) {
        return `${days}天前`;
    } else {
        return date.toLocaleDateString('zh-CN');
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
    container.innerHTML = '';

    messages.forEach(msg => {
        const card = document.createElement('div');
        card.className = 'message-card';
        card.innerHTML = `
            <div class="message-header">
                <span class="message-nickname ${getNicknameColorClass(msg.nickname)}">${escapeHtml(msg.nickname)}</span>
                <span class="message-time">${formatRelativeTime(msg.created_at)}</span>
            </div>
            <div class="message-content">${escapeHtml(msg.content)}</div>
        `;
        container.appendChild(card);
    });
}

/**
 * 添加一条新留言到顶部（乐观更新）
 */
function prependMessage(msg) {
    const container = document.getElementById('messages');
    const card = document.createElement('div');
    card.className = 'message-card';
    card.innerHTML = `
        <div class="message-header">
            <span class="message-nickname ${getNicknameColorClass(msg.nickname)}">${escapeHtml(msg.nickname)}</span>
            <span class="message-time">刚刚</span>
        </div>
        <div class="message-content">${escapeHtml(msg.content)}</div>
    `;
    container.insertBefore(card, container.firstChild);
}

/**
 * 显示 404 页面
 */
function showNotFound() {
    document.querySelector('.header').style.display = 'none';
    document.querySelector('.presence-indicator').style.display = 'none';
    document.getElementById('messages').style.display = 'none';
    document.getElementById('inputBar').style.display = 'none';
    document.getElementById('notFound').style.display = 'block';
}

/**
 * 加载地点数据
 */
async function loadLocation() {
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

        // 更新在场人数
        document.getElementById('presenceCount').textContent = data.presence_count;

        // 保存我的昵称
        myNickname = data.my_nickname;

        // 渲染留言
        renderMessages(data.messages);

        // 启动心跳
        startHeartbeat();

        // 启动轮询刷新
        startRefresh();

    } catch (error) {
        console.error('加载地点数据失败:', error);
        document.getElementById('locationName').textContent = '加载失败';
    }
}

/**
 * 发送留言
 */
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const content = input.value.trim();

    if (!content) {
        return;
    }

    // 清空输入框
    input.value = '';

    // 乐观更新：先显示留言
    const tempMsg = {
        nickname: myNickname || '匿名用户',
        content: content
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

        // 更新刚插入的卡片的昵称（如果之前是临时的）
        const firstCard = document.querySelector('.message-card');
        if (firstCard) {
            const nicknameEl = firstCard.querySelector('.message-nickname');
            nicknameEl.textContent = msg.nickname;
            nicknameEl.className = `message-nickname ${getNicknameColorClass(msg.nickname)}`;
        }

    } catch (error) {
        console.error('发送留言失败:', error);
        alert('发送失败，请重试');
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
 * 刷新留言列表
 */
async function refreshMessages() {
    try {
        const response = await fetch(`/api/loc/${locationId}`);
        if (!response.ok) return;

        const data = await response.json();

        // 更新在场人数
        document.getElementById('presenceCount').textContent = data.presence_count;

        // 渲染留言
        renderMessages(data.messages);

    } catch (error) {
        console.error('刷新失败:', error);
    }
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

    // 加载数据
    loadLocation();

    // 绑定回车发送
    document.getElementById('messageInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', init);
