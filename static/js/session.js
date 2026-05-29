/**
 * MOMOKA 会话管理 — 会话列表页前端逻辑
 */

let sessions = [];

// ── 加载会话列表 ──
async function loadSessions() {
    try {
        const data = await apiGet('/sessions');
        sessions = data.sessions || [];
        renderSessionList();
    } catch (err) {
        showError('加载会话列表失败: ' + err.message);
    }
}

// ── 渲染会话列表 ──
function renderSessionList() {
    const list = document.getElementById('sessionList');
    const empty = document.getElementById('emptyHint');

    if (!sessions.length) {
        list.innerHTML = '';
        empty.style.display = 'block';
        return;
    }

    empty.style.display = 'none';
    list.innerHTML = sessions.map(s => {
        const folderDisplay = s.folder_path ? s.folder_path.replace(/\\/g, '/') : '';
        const msgCount = s.message_count || 0;
        const lastTime = formatDate(s.last_message_at) || formatDate(s.created_at);
        return `
            <div class="session-card" data-id="${s.id}" onclick="openSession('${s.id}')">
                <div class="session-card-main">
                    <div class="session-card-name">${escapeHtml(s.name)}</div>
                    <div class="session-card-goal">${escapeHtml(s.goal)}</div>
                    <div class="session-card-meta">
                        <span class="session-card-folder">${escapeHtml(folderDisplay)}</span>
                    </div>
                </div>
                <div class="session-card-side">
                    <div class="session-card-msgs">${msgCount} 条消息</div>
                    <div class="session-card-time">${lastTime}</div>
                    <button class="session-card-del" onclick="event.stopPropagation(); deleteSession('${s.id}')" title="删除会话">✕</button>
                </div>
            </div>
        `;
    }).join('');
}

// ── 打开会话（进入聊天页） ──
function openSession(sessionId) {
    window.location.href = `chat.html?id=${sessionId}`;
}

// ── 删除会话 ──
async function deleteSession(sessionId) {
    if (!confirm('确定删除此会话及其所有消息？')) return;
    try {
        await apiDelete(`/sessions/${sessionId}`);
        sessions = sessions.filter(s => s.id !== sessionId);
        renderSessionList();
    } catch (err) {
        showError('删除会话失败: ' + err.message);
    }
}

// ── 创建会话弹窗 ──
function showCreateModal() {
    document.getElementById('createModal').classList.add('open');
    document.getElementById('goalInput').focus();
}

function hideCreateModal() {
    document.getElementById('createModal').classList.remove('open');
}

async function createSession() {
    const goal = document.getElementById('goalInput').value.trim();
    const folderPath = document.getElementById('folderInput').value.trim();

    if (!goal) {
        showError('请输入会话核心目标');
        return;
    }
    if (!folderPath) {
        showError('请选择工作文件夹');
        return;
    }

    const btn = document.getElementById('createBtn');
    btn.disabled = true;
    btn.textContent = '创建中...';

    try {
        const data = await apiPost('/sessions', { goal, folder_path: folderPath });
        // 跳转到聊天页
        window.location.href = `chat.html?id=${data.session.id}`;
    } catch (err) {
        showError(err.message);
        btn.disabled = false;
        btn.textContent = '创建会话';
    }
}

// ── 文件夹选择 ──
async function selectFolder() {
    try {
        // 使用 File System Access API（Chrome 86+）
        const dirHandle = await window.showDirectoryPicker();
        const path = dirHandle.name;
        // 只能拿到名字，需要用户输入完整路径或浏览器提供 full path
        // 这里我们在输入框中显示「已选择: 目录名」，让用户确认完整路径
        document.getElementById('folderInput').value = path;
        // 实际我们无法从 showDirectoryPicker 获取完整系统路径
        // 因此保留用户手动输入或粘贴路径的方式
    } catch (err) {
        if (err.name !== 'AbortError' && err.name !== 'SecurityError') {
            console.warn('目录选择器不可用，请手动输入路径:', err);
        }
    }
}

// 回车快捷创建
function onGoalKeydown(e) {
    if (e.key === 'Enter') {
        document.getElementById('folderInput').focus();
    }
}
function onFolderKeydown(e) {
    if (e.key === 'Enter') {
        createSession();
    }
}

// ── 错误提示 ──
function showError(msg) {
    const el = document.getElementById('errorToast');
    if (!el) return;
    el.textContent = msg;
    el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), 4000);
}

// ── 初始化 ──
document.addEventListener('DOMContentLoaded', loadSessions);

// 点击弹窗外部关闭
document.addEventListener('click', function(e) {
    const modal = document.getElementById('createModal');
    if (e.target === modal) hideCreateModal();
});
