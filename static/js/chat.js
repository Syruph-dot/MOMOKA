/**
 * MOMOKA 聊天页 — 会话级对话界面
 */

let sessionId = '';
let session = null;
let lastOutputId = '';
let isProcessing = false;
let loadedMessageIds = new Set();

// ── 初始化 ──
document.addEventListener('DOMContentLoaded', initChat);

async function initChat() {
    // 从 URL 获取 session_id
    const params = new URLSearchParams(window.location.search);
    sessionId = params.get('id');
    if (!sessionId) {
        showPageError('缺少会话 ID，请从会话列表进入。');
        return;
    }

    try {
        const data = await apiGet(`/sessions/${sessionId}`);
        session = data.session;
        renderSessionHeader();
        await loadMessages();

        // 如果会话没有消息，自动将核心目标作为首条消息发给 Agent
        if (session.message_count === 0) {
            await sendGoalAsFirstMessage();
        }
    } catch (err) {
        showPageError('加载会话失败: ' + err.message);
    }
}

// ── 会话头部 ──
function renderSessionHeader() {
    document.getElementById('sessionName').textContent = session.name || '未命名会话';
    document.getElementById('sessionGoal').textContent = session.goal || '';
    const folderDisplay = session.folder_path ? session.folder_path.replace(/\\/g, '/') : '';
    document.getElementById('sessionFolder').textContent = folderDisplay;
    document.getElementById('sessionFolder').title = folderDisplay;
}

// ── 加载历史消息 ──
async function loadMessages() {
    try {
        const data = await apiGet(`/sessions/${sessionId}/messages`);
        const messages = data.messages || [];
        loadedMessageIds = new Set(messages.map(m => m.id));

        for (const msg of messages) {
            if (msg.role === 'user') {
                addMessage('user', msg.content, msg.id, false);
            } else {
                addMessage('agent', msg.content, msg.output_id || msg.id, false, msg.matched_skills, msg.tool_calls);
            }
        }
        scrollToBottom();
    } catch (err) {
        console.warn('加载历史消息失败:', err);
    }
}

// ── 发送消息 ──
async function sendMessage() {
    if (isProcessing) return;

    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message) return;

    isProcessing = true;
    input.value = '';
    input.disabled = true;
    document.getElementById('sendBtn').disabled = true;
    setStatus('thinking', '思考中...');

    addMessage('user', message, uid('msg'), false);

    try {
        const data = await apiPost('/chat', {
            session_id: sessionId,
            message: message,
            output_id: uid('out'),
            topic: session ? session.goal : message,
        });

        // 更新 session 信息
        if (data.session_id) {
            session.message_count = (session.message_count || 0) + 1;
            session.last_message_at = new Date().toISOString();
        }

        // 显示技能标签
        const skillPayload = data.skill_reasons || data.matched_skills;
        updateSkillTags(skillPayload);

        // 显示工具调用
        if (data.tool_calls && data.tool_calls.length > 0) {
            for (const tc of data.tool_calls) {
                addToolLog(tc.tool, tc.args, tc.result);
            }
        }

        // 显示 Agent 回复
        const outId = data.output_id || uid('out');
        addMessage('agent', data.response, outId, true, data.matched_skills, data.tool_calls);
        setStatus('idle', '就绪');

    } catch (err) {
        addMessage('agent', `错误: ${err.message}`, '', false);
        setStatus('error', '错误');
    } finally {
        isProcessing = false;
        input.disabled = false;
        document.getElementById('sendBtn').disabled = false;
        input.focus();
    }
}

// ── 自动将会话核心目标作为首条消息发送 ──
async function sendGoalAsFirstMessage() {
    if (!session || !session.goal || isProcessing) return;

    const goal = session.goal;
    isProcessing = true;
    setStatus('thinking', '思考中...');

    addMessage('user', goal, uid('msg'), false);

    try {
        const data = await apiPost('/chat', {
            session_id: sessionId,
            message: goal,
            output_id: uid('out'),
            topic: goal,
        });

        if (data.session_id) {
            session.message_count = (session.message_count || 0) + 1;
        }

        const skillPayload = data.skill_reasons || data.matched_skills;
        updateSkillTags(skillPayload);

        if (data.tool_calls && data.tool_calls.length > 0) {
            for (const tc of data.tool_calls) {
                addToolLog(tc.tool, tc.args, tc.result);
            }
        }

        const outId = data.output_id || uid('out');
        addMessage('agent', data.response, outId, true, data.matched_skills, data.tool_calls);
        setStatus('idle', '就绪');

    } catch (err) {
        addMessage('agent', `自动发送失败: ${err.message}`, '', false);
        setStatus('error', '错误');
    } finally {
        isProcessing = false;
    }
}

// ── 添加消息 ──
function addMessage(role, text, msgId, showJudge, matchedSkills, toolCalls) {
    const container = document.getElementById('chatMessages');
    if (!msgId) msgId = uid('msg');

    if (role === 'agent') {
        lastOutputId = msgId;
    }

    const div = document.createElement('div');
    div.className = `chat-message ${role}`;
    div.setAttribute('data-msg-id', msgId);

    const label = role === 'user' ? '你' : 'MOMOKA';

    let html = `<div class="msg-label">${label}</div>`;
    html += `<div class="msg-bubble">${escapeHtml(text).replace(/\n/g, '<br>')}</div>`;

    if (role === 'agent' && showJudge) {
        html += renderJudgeBar(msgId);
    }

    div.innerHTML = html;
    container.appendChild(div);
    scrollToBottom();
}

function scrollToBottom() {
    const container = document.getElementById('chatMessages');
    container.scrollTop = container.scrollHeight;
}

// ── 评分栏 ──
function renderJudgeBar(outputId) {
    const labels = [
        { score: 1, title: '强烈反对' },
        { score: 2, title: '反对' },
        { score: 3, title: '不太赞同' },
        { score: 4, cls: 'neutral', title: '中立' },
        { score: 5, title: '有点赞同' },
        { score: 6, title: '赞同' },
        { score: 7, title: '强烈赞同' },
    ];

    let html = `<div class="judge-bar" data-output-id="${outputId}">`;
    html += '<span class="judge-label">评分:</span>';
    for (const l of labels) {
        html += `<button class="judge-btn ${l.cls || ''}" onclick="sendJudge('${outputId}',${l.score})" title="${l.title}">${l.score}</button>`;
    }
    html += `<span class="judge-feedback" id="feedback-${outputId}"></span>`;
    html += '</div>';
    return html;
}

// ── 文本划选 ──
document.addEventListener('mouseup', function(e) {
    const bubble = e.target.closest('.chat-message.agent .msg-bubble');
    if (!bubble) return;
    const sel = window.getSelection().toString().trim();
    if (!sel) return;
    const bar = bubble.closest('.chat-message').querySelector('.judge-bar');
    if (bar) bar.dataset.selectedText = sel;
});

// ── 评分 ──
async function sendJudge(outputId, score) {
    if (isProcessing) return;

    const bar = document.querySelector(`.judge-bar[data-output-id="${outputId}"]`);
    if (!bar) return;

    isProcessing = true;
    const btns = bar.querySelectorAll('.judge-btn');
    btns.forEach(b => b.classList.remove('active'));
    const target = bar.querySelector(`.judge-btn:nth-child(${score + 1})`);
    if (target) target.classList.add('active');

    const selectedText = bar.dataset.selectedText || '';
    const labelMap = {1:'强烈反对',2:'反对',3:'不太赞同',4:'中立',5:'有点赞同',6:'赞同',7:'强烈赞同'};
    const label = labelMap[score] || '未知';
    const annotation = `<AnnotateText>{${selectedText}}</AnnotateText>\n<UserScore>score:${score}, feeling:${label}</UserScore>`;
    console.log(`[MOMOKA] 标注格式:\n${annotation}`);

    let hadError = false;
    try {
        setStatus('thinking', '续猜中...');
        const res = await fetch(`${API_BASE}/judge`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                output_id: outputId,
                score: score,
                context: selectedText,
                continue: true,
            }),
        });

        const data = await res.json();
        const fb = document.getElementById(`feedback-${outputId}`);

        if (!res.ok) {
            if (fb) {
                fb.textContent = data.error || '评分提交失败';
                fb.className = 'judge-feedback score-1';
            }
            throw new Error(data.error || `HTTP ${res.status}`);
        }

        if (fb) {
            fb.textContent = data.analysis;
            fb.className = `judge-feedback score-${score}`;
        }

        console.log(`[MOMOKA] 评分: ${score}/7 — ${data.label} — ${data.analysis}`);

        if (data.next_tool_calls && data.next_tool_calls.length > 0) {
            for (const tc of data.next_tool_calls) {
                addToolLog(tc.tool, tc.args, tc.result);
            }
        }

        if (data.next_response) {
            addMessage('agent', data.next_response, data.next_output_id, true);
        }

        if (data.next_skill_reasons) {
            updateSkillTags(data.next_skill_reasons);
        }
    } catch (err) {
        hadError = true;
        console.error('评分提交失败:', err);
        setStatus('error', '错误');
    } finally {
        isProcessing = false;
        if (!hadError) setStatus('idle', '就绪');
    }
}

// ── 工具日志 ──
function addToolLog(toolName, args, result) {
    const container = document.getElementById('toolLogs');
    const placeholder = container.querySelector('.tool-log-empty');
    if (placeholder) placeholder.remove();

    const card = document.createElement('div');
    card.className = 'tool-card';
    card.innerHTML = `
        <div class="tool-card-header" onclick="this.nextElementSibling.classList.toggle('collapsed')">
            <span class="tool-card-name">[TOOL] ${escapeHtml(toolName)}</span>
            <span class="tool-card-time">${formatTime()}</span>
        </div>
        <div class="tool-card-body">
            <div class="tool-card-args"><strong>参数:</strong> ${escapeHtml(typeof args === 'string' ? args : JSON.stringify(args))}</div>
            <div class="tool-card-result">${escapeHtml(result || '')}</div>
        </div>
    `;
    container.appendChild(card);
    container.scrollTop = container.scrollHeight;
}

// ── 技能标签 ──
function updateSkillTags(skills) {
    const container = document.getElementById('skillTags');
    const indicator = document.getElementById('skill-indicator');
    if (!skills || skills.length === 0) {
        container.innerHTML = '<span style="color:#999;font-size:11px">暂无</span>';
        if (indicator) indicator.textContent = '';
        return;
    }
    const normalized = typeof skills[0] === 'string'
        ? skills.map(name => ({ name, reasons: [] }))
        : skills;
    container.innerHTML = normalized.map(s => {
        const name = s.name || '';
        const reasons = (s.reasons || []).slice(0, 3).join(' · ');
        const score = typeof s.score === 'number' ? `score:${s.score}` : '';
        const title = [reasons, score].filter(Boolean).join(' | ');
        return `<span class="skill-tag" title="${escapeHtml(title)}">${escapeHtml(name)}</span>`;
    }).join('');
    if (indicator) {
        indicator.textContent = `技能: ${normalized.map(s => s.name).join(', ')}`;
    }
}

// ── 状态指示 ──
function setStatus(state, text) {
    const indicator = document.getElementById('status-indicator');
    if (!indicator) return;
    const dots = { idle: 'idle', thinking: 'thinking', error: 'error' };
    indicator.innerHTML = `<span class="status-dot ${dots[state] || 'idle'}"></span>${text}`;
}

// ── 错误页 ──
function showPageError(msg) {
    const container = document.getElementById('chatMessages') || document.querySelector('.chat-main');
    if (container) {
        container.innerHTML = `<div style="padding:40px;text-align:center;color:#c33">${escapeHtml(msg)}</div>`;
    }
}

// ── 快捷操作 ──
function goBack() {
    window.location.href = 'index.html';
}

function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

// ── 清空会话（仅清空界面显示，不删除历史） ──
function clearChatDisplay() {
    const container = document.getElementById('chatMessages');
    container.innerHTML = `
        <div class="chat-message agent" data-msg-id="welcome">
            <div class="msg-label">MOMOKA</div>
            <div class="msg-bubble">已清空显示。历史消息保留。继续对话？</div>
        </div>
    `;
    document.getElementById('toolLogs').innerHTML = '<div class="tool-log-empty">等待工具调用...</div>';
    updateSkillTags([]);
}
