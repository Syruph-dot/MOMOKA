/**
 * MOMOKA 文件助手 — 前端交互逻辑
 * 核心交互: 自然语言输入 + Likert 7 点评分反馈
 */

const API_BASE = '/api';
let isProcessing = false;
let lastOutputId = '';

// --- 工具函数 ---
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function uid() {
    return 'out_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
}

function formatTime() {
    const now = new Date();
    return now.toLocaleTimeString('zh-CN', { hour12: false });
}

// --- 对话 ---
function addMessage(role, text, outputId) {
    const container = document.getElementById('chatMessages');
    const oid = outputId || (role === 'agent' ? uid() : '');
    lastOutputId = oid;

    const div = document.createElement('div');
    div.className = `chat-message ${role}`;
    div.setAttribute('data-output-id', oid);

    const label = role === 'user' ? '你' : 'MOMOKA';

    let html = `<div class="msg-label">${label}</div>`;
    html += `<div class="msg-bubble">${escapeHtml(text).replace(/\n/g, '<br>')}</div>`;

    // Agent 消息后附加 Likert 7 点评分栏
    if (role === 'agent') {
        html += renderJudgeBar(oid);
    }

    div.innerHTML = html;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function renderJudgeBar(outputId) {
    const labels = [
        { score: 1, cls: '', title: '强烈反对' },
        { score: 2, cls: '', title: '反对' },
        { score: 3, cls: '', title: '不太赞同' },
        { score: 4, cls: 'neutral', title: '中立' },
        { score: 5, cls: '', title: '有点赞同' },
        { score: 6, cls: '', title: '赞同' },
        { score: 7, cls: '', title: '强烈赞同' },
    ];

    let html = '<div class="judge-bar">';
    html += '<span class="judge-label">评分:</span>';
    for (const l of labels) {
        html += `<button class="judge-btn ${l.cls}" onclick="sendJudge('${outputId}',${l.score})" title="${l.title}">${l.score}</button>`;
    }
    html += `<span class="judge-feedback" id="feedback-${outputId}"></span>`;
    html += '</div>';
    return html;
}

// --- 文本划选: 捕获用户在 Agent 回复中选中的文本 ---
document.addEventListener('mouseup', function(e) {
    const bubble = e.target.closest('.chat-message.agent .msg-bubble');
    if (!bubble) return;
    const sel = window.getSelection().toString().trim();
    if (!sel) return;
    const bar = bubble.closest('.chat-message').querySelector('.judge-bar');
    if (bar) bar.dataset.selectedText = sel;
});

// --- 批注判断 (MOMOKA_PRD 核心交互) ---
async function sendJudge(outputId, score) {
    // 高亮当前评分
    const bar = document.querySelector(`.judge-bar[data-output-id="${outputId}"]`);
    if (!bar) return;
    const btns = bar.querySelectorAll('.judge-btn');
    btns.forEach(b => b.classList.remove('active'));
    const target = bar.querySelector(`.judge-btn:nth-child(${score + 1})`);
    if (target) target.classList.add('active');

    // 获取用户划选的文本（若无划选则用空字符串兜底）
    const selectedText = bar.dataset.selectedText || '';

    // 记录标注格式到控制台（可观测性）
    const labelMap = {1:'强烈反对',2:'反对',3:'不太赞同',4:'中立',5:'有点赞同',6:'赞同',7:'强烈赞同'};
    const label = labelMap[score] || '未知';
    const annotation = `<AnnotateText>{${selectedText}}</AnnotateText>\n<UserScore>score:${score}, feeling:${label}</UserScore>`;
    console.log(`[MOMOKA] 标注格式:\n${annotation}`);

    // 发送评分到后端
    try {
        const res = await fetch(`${API_BASE}/judge`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                output_id: outputId,
                score: score,
                context: selectedText,
            }),
        });

        if (res.ok) {
            const data = await res.json();
            const fb = document.getElementById(`feedback-${outputId}`);
            if (fb) {
                fb.textContent = data.analysis;
                fb.className = `judge-feedback score-${score}`;
            }

            // 记录到日记忆（轻量版本）
            console.log(`[MOMOKA] 评分: ${score}/7 — ${data.label} — ${data.analysis}`);
            if (data.annotated_text) {
                console.log(`[MOMOKA] 标注文本: "${data.annotated_text}"`);
            }
        }
    } catch (err) {
        console.error('评分提交失败:', err);
    }
}

// --- 工具日志 ---
function addToolLog(toolName, args, result) {
    const container = document.getElementById('toolLogs');
    const placeholder = container.querySelector('div[style]');
    if (placeholder) placeholder.remove();

    const card = document.createElement('div');
    card.className = 'tool-card';
    const ts = formatTime();
    card.innerHTML = `
        <div class="tool-card-header" onclick="this.nextElementSibling.classList.toggle('collapsed')">
            <span class="tool-card-name">[TOOL] ${escapeHtml(toolName)}</span>
            <span class="tool-card-time">${ts}</span>
        </div>
        <div class="tool-card-body">
            <div class="tool-card-args"><strong>参数:</strong> ${escapeHtml(args)}</div>
            <div class="tool-card-result">${escapeHtml(result)}</div>
        </div>
    `;
    container.appendChild(card);
    container.scrollTop = container.scrollHeight;
}

function clearToolLogs() {
    const container = document.getElementById('toolLogs');
    container.innerHTML = '<div style="color:#999;font-size:12px;padding:8px">等待工具调用...</div>';
}

function updateSkillTags(skills) {
    const container = document.getElementById('skillTags');
    if (!skills || skills.length === 0) {
        container.innerHTML = '<span style="color:#999;font-size:11px">暂无</span>';
        return;
    }
    container.innerHTML = skills.map(s =>
        `<span class="skill-tag">${escapeHtml(s)}</span>`
    ).join('');
}

// --- 发送消息 ---
async function sendMessage() {
    if (isProcessing) return;

    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message) return;

    isProcessing = true;
    input.value = '';
    input.disabled = true;
    const sendBtn = document.getElementById('sendBtn');
    sendBtn.disabled = true;

    setStatus('thinking', '思考中...');
    addMessage('user', message);
    clearToolLogs();

    // 显示用户输入关键词
    const skillInd = document.getElementById('skill-indicator');
    skillInd.textContent = '分析中...';

    const outputId = uid();

    try {
        const res = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, output_id: outputId }),
        });

        if (!res.ok) {
            const data = await res.json();
            throw new Error(data.error || data.detail || `HTTP ${res.status}`);
        }

        const data = await res.json();

        // 显示匹配的技能
        if (data.matched_skills) {
            updateSkillTags(data.matched_skills);
            skillInd.textContent = data.matched_skills.length > 0
                ? `技能: ${data.matched_skills.join(', ')}`
                : '';
        }

        // 显示工具调用
        if (data.tool_calls && data.tool_calls.length > 0) {
            for (const tc of data.tool_calls) {
                addToolLog(tc.tool, tc.args, tc.result);
            }
        }

        // 显示 Agent 回复 (带评分栏)
        addMessage('agent', data.response, data.output_id || outputId);
        setStatus('idle', '就绪');

    } catch (err) {
        addMessage('agent', `错误: ${err.message}`);
        setStatus('error', '错误');
    } finally {
        isProcessing = false;
        input.disabled = false;
        sendBtn.disabled = false;
        input.focus();
    }
}

function setStatus(state, text) {
    const indicator = document.getElementById('status-indicator');
    const dots = { idle: 'idle', thinking: 'thinking', error: 'error' };
    indicator.innerHTML = `<span class="status-dot ${dots[state] || 'idle'}"></span>${text}`;
}

function clearChat() {
    const container = document.getElementById('chatMessages');
    container.innerHTML = `
        <div class="chat-message agent" data-output-id="welcome">
            <div class="msg-label">MOMOKA</div>
            <div class="msg-bubble">已清空对话。有什么需要帮助的？</div>
            ${renderJudgeBar('welcome')}
        </div>
    `;
    clearToolLogs();
    updateSkillTags([]);
    document.getElementById('skill-indicator').textContent = '';
}
