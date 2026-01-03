/**
 * OSTK Frontend Application
 * Communicates with Rust backend via Tauri invoke
 */

// Tauri API helpers
const { invoke } = window.__TAURI__.core;
const { save } = window.__TAURI__.dialog;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', init);

// State
let currentFilters = {};
let queryPreviewShown = false;
let executionPollInterval = null;
let isExecuting = false;  // Global lock to prevent concurrent executions

// DOM Elements
const elements = {};

function init() {
    console.log('OSTK initializing...');
    cacheElements();
    setupEventListeners();
    loadSettings();
    updateAgentStatus();
}

function cacheElements() {
    // Tabs
    elements.tabs = document.querySelectorAll('.tab');
    elements.pages = document.querySelectorAll('.page');

    // Query page
    elements.filterChips = document.querySelectorAll('.chip[data-filter]');
    elements.presetChips = document.querySelectorAll('.chip[data-preset]');
    elements.activeFilters = document.getElementById('active-filters');
    elements.clearFilters = document.getElementById('clear-filters');
    elements.previewBtn = document.getElementById('preview-btn');
    elements.executeBtn = document.getElementById('execute-btn');
    elements.queryPreview = document.getElementById('query-preview');
    elements.queryResults = document.getElementById('query-results');
    elements.rowCount = document.getElementById('row-count');
    elements.exportCsv = document.getElementById('export-csv');
    elements.exportParquet = document.getElementById('export-parquet');

    // Execution panel
    elements.executionPanel = document.getElementById('execution-panel');
    elements.executionStatusText = document.getElementById('execution-status-text');
    elements.executionLog = document.getElementById('execution-log');
    elements.cancelBtn = document.getElementById('cancel-btn');
    elements.logToggle = document.getElementById('log-toggle');

    // Chat page
    elements.chatMessages = document.getElementById('chat-messages');
    elements.chatInput = document.getElementById('chat-input');
    elements.sendBtn = document.getElementById('send-btn');
    elements.agentStatus = document.getElementById('agent-status');

    // Settings page
    elements.llmProvider = document.getElementById('llm-provider');
    elements.providerSettings = document.querySelectorAll('.provider-settings');
    elements.saveLlm = document.getElementById('save-llm');
    elements.saveOpensky = document.getElementById('save-opensky');

    // Modal
    elements.modal = document.getElementById('filter-modal');
    elements.modalTitle = document.getElementById('modal-title');
    elements.modalLabel = document.getElementById('modal-label');
    elements.modalInput = document.getElementById('modal-input');
    elements.modalCancel = document.getElementById('modal-cancel');
    elements.modalConfirm = document.getElementById('modal-confirm');

    // Loading & Toast
    elements.loading = document.getElementById('loading');
    elements.loadingText = document.getElementById('loading-text');
    elements.toast = document.getElementById('toast');
}

function setupEventListeners() {
    // Tab navigation
    elements.tabs.forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.page));
    });

    // Query page - add filter and start inline editing
    elements.filterChips.forEach(chip => {
        chip.addEventListener('click', () => addFilterInline(chip.dataset.filter));
    });

    elements.presetChips.forEach(chip => {
        chip.addEventListener('click', () => applyPreset(chip.dataset.preset));
    });

    elements.clearFilters.addEventListener('click', clearFilters);
    elements.previewBtn.addEventListener('click', previewQuery);
    elements.executeBtn.addEventListener('click', executeQuery);
    elements.exportCsv.addEventListener('click', () => exportData('csv'));
    elements.exportParquet.addEventListener('click', () => exportData('parquet'));
    elements.cancelBtn.addEventListener('click', cancelQuery);
    elements.logToggle.addEventListener('click', toggleLog);

    // Chat page - only button sends, Enter creates newlines
    elements.sendBtn.addEventListener('click', sendMessage);

    // Settings page
    elements.llmProvider.addEventListener('change', toggleProviderSettings);
    elements.saveLlm.addEventListener('click', saveLlmSettings);
    elements.saveOpensky.addEventListener('click', saveOpenskySettings);
    // Fetch Groq models
    document.getElementById('fetch-groq-models').addEventListener('click', fetchGroqModels);

    // Password toggle buttons (CSP-safe)
    document.querySelectorAll('.toggle-visibility').forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.dataset.target;
            const input = document.getElementById(targetId);
            if (input.type === 'password') {
                input.type = 'text';
                btn.textContent = '🙈';
            } else {
                input.type = 'password';
                btn.textContent = '👁';
            }
        });
    });

    // Modal
    elements.modalCancel.addEventListener('click', hideModal);
    elements.modalConfirm.addEventListener('click', confirmFilter);
    elements.modalInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') confirmFilter();
        if (e.key === 'Escape') hideModal();
    });
}

// ========== Global Execution Lock ==========

function setExecutionLock(locked) {
    isExecuting = locked;

    // Disable/enable Query Builder execute button
    if (locked) {
        elements.executeBtn.disabled = true;
    } else {
        // Only enable if query was previewed
        elements.executeBtn.disabled = !queryPreviewShown;
    }

    // Disable/enable Chat send button and input
    elements.sendBtn.disabled = locked;
    elements.chatInput.disabled = locked;

    if (locked) {
        elements.chatInput.placeholder = 'Query in progress...';
    } else {
        elements.chatInput.placeholder = 'Type your query...';
    }
}

// ========== Tab Navigation ==========

function switchTab(page) {
    elements.tabs.forEach(t => t.classList.toggle('active', t.dataset.page === page));
    elements.pages.forEach(p => p.classList.toggle('active', p.id === `${page}-page`));
}

// ========== Query Page ==========

function addFilterInline(filter) {
    // If filter already exists, just focus on it for editing
    if (currentFilters[filter] !== undefined) {
        const existingItem = elements.activeFilters.querySelector(`.filter-item[data-filter="${filter}"]`);
        if (existingItem) {
            const span = existingItem.querySelector('.value');
            span.click();  // Trigger inline edit
        }
        return;
    }

    // Add empty filter placeholder
    currentFilters[filter] = '';
    renderActiveFilters();

    // Immediately trigger inline editing on the new filter
    setTimeout(() => {
        const newItem = elements.activeFilters.querySelector(`.filter-item[data-filter="${filter}"]`);
        if (newItem) {
            const span = newItem.querySelector('.value');
            span.click();  // Trigger inline edit
        }
    }, 0);
}

const filterLabels = {
    start: 'Start Time',
    stop: 'Stop Time',
    icao24: 'ICAO24',
    callsign: 'Callsign',
    departure_airport: 'Departure Airport',
    arrival_airport: 'Arrival Airport',
    airport: 'Airport',
    limit: 'Row Limit'
};

function showFilterModal(filter) {
    elements.modalTitle.textContent = `Add ${filterLabels[filter]}`;
    elements.modalLabel.textContent = filterLabels[filter];
    elements.modalInput.value = currentFilters[filter] || '';
    elements.modalInput.dataset.filter = filter;

    // Set input type
    if (filter === 'limit') {
        elements.modalInput.type = 'number';
        elements.modalInput.placeholder = '10000';
    } else if (filter === 'start' || filter === 'stop') {
        elements.modalInput.type = 'text';
        elements.modalInput.placeholder = 'YYYY-MM-DD HH:MM:SS';
    } else {
        elements.modalInput.type = 'text';
        elements.modalInput.placeholder = '';
    }

    elements.modal.classList.remove('hidden');
    elements.modalInput.focus();
}

function hideModal() {
    elements.modal.classList.add('hidden');
}

async function confirmFilter() {
    const filter = elements.modalInput.dataset.filter;
    let value = elements.modalInput.value.trim();

    if (!value) {
        hideModal();
        return;
    }

    // Auto-uppercase for airport codes
    if (['departure_airport', 'arrival_airport', 'airport'].includes(filter)) {
        value = value.toUpperCase();
    }

    // Parse limit as integer
    if (filter === 'limit') {
        value = parseInt(value, 10);
    }

    currentFilters[filter] = value;
    await invoke('set_query_param', { key: filter, value: value });

    renderActiveFilters();
    hideModal();
    resetQueryState();
}

async function applyPreset(preset) {
    const times = await invoke('get_quick_time_preset', { preset: preset });
    if (times.start) {
        currentFilters.start = times.start;
        await invoke('set_query_param', { key: 'start', value: times.start });
    }
    if (times.stop) {
        currentFilters.stop = times.stop;
        await invoke('set_query_param', { key: 'stop', value: times.stop });
    }
    renderActiveFilters();
    resetQueryState();
}

async function clearFilters() {
    currentFilters = {};
    await invoke('clear_query_params');
    renderActiveFilters();
    resetQueryState();
}

function renderActiveFilters() {
    elements.activeFilters.innerHTML = '';

    for (const [key, value] of Object.entries(currentFilters)) {
        const item = document.createElement('div');
        item.className = 'filter-item';
        item.dataset.filter = key;
        const displayValue = value === '' ? '' : value;
        const placeholder = getPlaceholder(key);
        item.innerHTML = `
            <span class="label">${filterLabels[key]}</span>
            <span class="value ${value === '' ? 'empty' : ''}" data-filter="${key}">${displayValue || placeholder}</span>
            <input class="value-input hidden" data-filter="${key}" type="text" value="${displayValue}" placeholder="${placeholder}">
            <button class="remove" data-filter="${key}">&times;</button>
        `;
        elements.activeFilters.appendChild(item);
    }

    // Setup event listeners after rendering
    setupFilterListeners();
}

function getPlaceholder(filter) {
    const placeholders = {
        start: 'YYYY-MM-DD HH:MM:SS',
        stop: 'YYYY-MM-DD HH:MM:SS',
        icao24: 'e.g. 485a32',
        callsign: 'e.g. KLM1234',
        departure_airport: 'e.g. EHAM',
        arrival_airport: 'e.g. EGLL',
        airport: 'e.g. EHAM',
        limit: 'e.g. 10000'
    };
    return placeholders[filter] || '';
}

function setupFilterListeners() {
    // Add click-to-edit listeners on value spans
    elements.activeFilters.querySelectorAll('.value').forEach(span => {
        span.addEventListener('click', (e) => {
            const filter = span.dataset.filter;
            const item = span.closest('.filter-item');
            const input = item.querySelector('.value-input');

            // Hide span, show input
            span.classList.add('hidden');
            input.classList.remove('hidden');
            input.focus();
            input.select();
        });
    });

    // Add blur and enter key listeners on inputs
    elements.activeFilters.querySelectorAll('.value-input').forEach(input => {
        const saveEdit = async () => {
            const filter = input.dataset.filter;
            const item = input.closest('.filter-item');
            const span = item.querySelector('.value');
            let newValue = input.value.trim();

            if (!newValue) {
                // Empty value - remove the filter
                delete currentFilters[filter];
                await invoke('set_query_param', { key: filter, value: null });
                renderActiveFilters();
                resetQueryState();
                return;
            }

            // Auto-uppercase for airport codes
            if (['departure_airport', 'arrival_airport', 'airport'].includes(filter)) {
                newValue = newValue.toUpperCase();
            }

            // Parse limit as integer
            if (filter === 'limit') {
                newValue = parseInt(newValue, 10);
                if (isNaN(newValue)) {
                    newValue = currentFilters[filter]; // Revert to original
                }
            }

            currentFilters[filter] = newValue;
            await invoke('set_query_param', { key: filter, value: newValue });

            // Update display and switch back to span
            span.textContent = newValue;
            input.value = newValue;
            input.classList.add('hidden');
            span.classList.remove('hidden');
            resetQueryState();
        };

        input.addEventListener('blur', saveEdit);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                input.blur();
            }
            if (e.key === 'Escape') {
                // Revert to original value
                input.value = currentFilters[input.dataset.filter];
                input.blur();
            }
        });
    });

    // Add remove listeners
    elements.activeFilters.querySelectorAll('.remove').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const filter = btn.dataset.filter;
            delete currentFilters[filter];
            await invoke('set_query_param', { key: filter, value: null });
            renderActiveFilters();
            resetQueryState();
        });
    });
}

function resetQueryState() {
    queryPreviewShown = false;
    elements.executeBtn.disabled = true;
    elements.queryPreview.classList.add('hidden');
    elements.queryResults.classList.add('hidden');
    elements.executionPanel.classList.add('hidden');
}

async function previewQuery() {
    if (!currentFilters.start) {
        showToast('Start time is required', 'error');
        return;
    }

    // Clear all backend params first, then set only the ones from Query Builder UI
    await invoke('clear_query_params');
    for (const [key, value] of Object.entries(currentFilters)) {
        await invoke('set_query_param', { key, value });
    }

    const preview = await invoke('build_query_preview_cmd');
    elements.queryPreview.textContent = preview;
    elements.queryPreview.classList.remove('hidden');
    elements.executeBtn.disabled = false;
    queryPreviewShown = true;
}

async function executeQuery() {
    if (!queryPreviewShown) {
        showToast('Please preview the query first', 'error');
        return;
    }

    if (isExecuting) {
        showToast('A query is already running', 'error');
        return;
    }

    // Set global execution lock
    setExecutionLock(true);

    // Invalidate any existing export buttons from both tabs
    invalidateAllExportButtons();

    // Show execution panel
    elements.executionPanel.classList.remove('hidden', 'complete', 'error', 'downloading');
    elements.executionStatusText.textContent = 'Connecting...';
    elements.executionLog.textContent = '';
    elements.cancelBtn.classList.add('hidden');  // Hidden until query ID received
    elements.cancelBtn.disabled = false;  // Re-enable for new query

    try {
        // Start async execution
        const startResult = await invoke('execute_query_async');

        if (startResult.error) {
            showExecutionError(startResult.error);
            return;
        }

        // Start polling for status
        startExecutionPolling();

    } catch (e) {
        showExecutionError(e.message || e);
    }
}

function startExecutionPolling() {
    // Clear any existing interval
    if (executionPollInterval) {
        clearInterval(executionPollInterval);
    }

    executionPollInterval = setInterval(async () => {
        try {
            const status = await invoke('get_execution_status');

            // Update status text
            elements.executionStatusText.textContent = status.status;

            // Update logs and auto-scroll
            if (status.logs && status.logs.length > 0) {
                elements.executionLog.textContent = status.logs.join('\n');
                elements.executionLog.scrollTop = elements.executionLog.scrollHeight;
                // Also scroll the page to keep execution panel visible
                elements.executionPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }

            // Show/hide cancel button and spinner based on download phase
            if (status.can_cancel) {
                elements.cancelBtn.classList.remove('hidden');
                elements.executionPanel.classList.add('downloading');
            } else {
                elements.cancelBtn.classList.add('hidden');
                elements.executionPanel.classList.remove('downloading');
            }

            // Check if complete
            if (status.complete) {
                clearInterval(executionPollInterval);
                executionPollInterval = null;
                elements.cancelBtn.classList.add('hidden');
                elements.executionPanel.classList.remove('downloading');

                if (status.result) {
                    handleExecutionResult(status.result);
                }
            }

        } catch (e) {
            console.error('Polling error:', e);
        }
    }, 500); // Poll every 500ms
}

function handleExecutionResult(result) {
    elements.cancelBtn.classList.add('hidden');

    // Release global execution lock
    setExecutionLock(false);

    if (result.cancelled) {
        elements.executionPanel.classList.add('error');
        elements.executionStatusText.textContent = 'Cancelled';
        showToast('Query cancelled', 'error');
        return;
    }

    if (result.error) {
        showExecutionError(result.error);
        return;
    }

    if (result.success) {
        elements.executionPanel.classList.add('complete');
        elements.executionStatusText.textContent = `Complete - ${result.row_count.toLocaleString()} rows`;
        renderResults(result);
        showToast(`Found ${result.row_count.toLocaleString()} rows`, 'success');
    }
}

function showExecutionError(error) {
    elements.executionPanel.classList.add('error');
    elements.executionStatusText.textContent = 'Error';
    elements.cancelBtn.disabled = true;

    // Release global execution lock
    setExecutionLock(false);

    // Add error to log
    const currentLog = elements.executionLog.textContent;
    elements.executionLog.textContent = currentLog + '\n[ERROR] ' + error;

    showToast(error, 'error');
}

async function cancelQuery() {
    elements.cancelBtn.disabled = true;
    elements.executionStatusText.textContent = 'Cancelling...';

    try {
        await invoke('cancel_query');
    } catch (e) {
        console.error('Cancel error:', e);
    }
}

function toggleLog() {
    const container = elements.logToggle.parentElement;
    container.classList.toggle('log-collapsed');
}

function invalidateAllExportButtons() {
    // Invalidate Chat tab export buttons
    document.querySelectorAll('.chat-execution .export-buttons').forEach(el => {
        el.innerHTML = '<span style="color: var(--text-muted); font-size: 0.75rem;">Data replaced by new query</span>';
    });

    // Hide Query Builder tab results (they have export buttons)
    elements.queryResults.classList.add('hidden');
}

function renderResults(result) {
    elements.rowCount.textContent = `(${result.row_count.toLocaleString()} rows, ${result.columns.length} columns)`;
    elements.queryResults.classList.remove('hidden');
}

async function exportData(format) {
    try {
        // Use native file picker
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
        const defaultName = `ostk_export_${timestamp}.${format}`;

        const filters = format === 'csv'
            ? [{ name: 'CSV Files', extensions: ['csv'] }]
            : [{ name: 'Parquet Files', extensions: ['parquet'] }];

        const filepath = await save({
            defaultPath: defaultName,
            filters: filters,
            title: `Export as ${format.toUpperCase()}`
        });

        if (!filepath) {
            // User cancelled
            return;
        }

        let result;
        if (format === 'csv') {
            result = await invoke('export_csv', { filepath: filepath });
        } else {
            result = await invoke('export_parquet', { filepath: filepath });
        }

        if (result.error) {
            showToast(result.error, 'error');
        } else if (result.success) {
            showToast(`Exported to ${result.filepath}`, 'success');
        }
    } catch (e) {
        showToast('Export failed: ' + (e.message || e), 'error');
    }
}

// ========== Chat Page ==========

async function updateAgentStatus() {
    try {
        const status = await invoke('get_agent_status');

        if (status.configured) {
            elements.agentStatus.textContent = `Using ${status.provider} (${status.model})`;
            elements.agentStatus.className = 'agent-status configured';
        } else {
            elements.agentStatus.textContent = status.error || 'LLM not configured. Go to Settings to set up.';
            elements.agentStatus.className = 'agent-status error';
        }
    } catch (e) {
        elements.agentStatus.textContent = 'LLM not configured. Go to Settings to set up.';
        elements.agentStatus.className = 'agent-status error';
    }
}

async function sendMessage() {
    const message = elements.chatInput.value.trim();
    if (!message) return;

    if (isExecuting) {
        showToast('A query is already running', 'error');
        return;
    }

    // Add user message
    addChatMessage('user', message);
    elements.chatInput.value = '';

    showLoading('Thinking...');

    try {
        const result = await invoke('send_message', { userMessage: message });

        if (result.error && !result.messages) {
            addChatMessage('assistant', result.error, 'error');
            return;
        }

        // Render new messages (skip already displayed)
        const existingCount = elements.chatMessages.querySelectorAll('.message').length;
        const newMessages = result.messages.slice(existingCount - 1); // -1 for welcome message

        newMessages.forEach(msg => {
            if (msg.role === 'assistant') {
                addChatMessage('assistant', msg.content, msg.type);
            }
        });

    } catch (e) {
        addChatMessage('assistant', 'Error: ' + (e.message || e), 'error');
    } finally {
        hideLoading();
    }
}

function addChatMessage(role, content, type = 'text') {
    const msg = document.createElement('div');
    msg.className = `message ${role}`;
    if (type === 'error') msg.classList.add('error');

    let html = '<div class="message-content">';

    if (type === 'code') {
        const msgId = 'code-' + Date.now();
        html += `
            <div class="code-block" id="${msgId}">
                <pre><code>${escapeHtml(content)}</code></pre>
                <button class="btn btn-primary execute-btn" data-code-id="${msgId}">Execute</button>
            </div>
        `;
    } else {
        // Simple markdown-like rendering
        html += formatMessage(content);
    }

    html += '</div>';
    msg.innerHTML = html;

    elements.chatMessages.appendChild(msg);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;

    // Attach event listener to execute button (CSP-safe, no inline onclick)
    if (type === 'code') {
        const executeBtn = msg.querySelector('.execute-btn');
        if (executeBtn) {
            executeBtn.addEventListener('click', () => {
                const codeId = executeBtn.dataset.codeId;
                executeCodeFromChat(codeId);
            });
        }
    }
}

function formatMessage(content) {
    // Handle code blocks first
    let formatted = content.replace(/```(\w*)\n?([\s\S]*?)```/g, (match, lang, code) => {
        return `<pre class="code-block"><code>${escapeHtml(code.trim())}</code></pre>`;
    });

    // Simple markdown formatting
    formatted = formatted
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br>');

    return formatted;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

let chatExecutionInterval = null;

async function executeCodeFromChat(codeBlockId) {
    const codeBlock = document.getElementById(codeBlockId);
    if (!codeBlock) {
        console.error('Code block not found:', codeBlockId);
        return;
    }

    if (isExecuting) {
        showToast('A query is already running', 'error');
        return;
    }

    const btn = codeBlock.querySelector('.execute-btn');

    // Set global execution lock
    setExecutionLock(true);

    // Clear any existing intervals (both chat and query builder)
    if (chatExecutionInterval) {
        clearInterval(chatExecutionInterval);
        chatExecutionInterval = null;
    }
    if (executionPollInterval) {
        clearInterval(executionPollInterval);
        executionPollInterval = null;
    }

    // Disable button
    btn.disabled = true;
    btn.textContent = 'Running...';

    // Invalidate any existing export buttons from both tabs
    invalidateAllExportButtons();

    // Remove any existing execution panel in this code block
    const existingPanel = codeBlock.querySelector('.chat-execution');
    if (existingPanel) existingPanel.remove();

    // Create inline execution panel (same structure as Query Builder)
    const execPanel = document.createElement('div');
    execPanel.className = 'chat-execution';
    execPanel.innerHTML = `
        <div class="execution-header">
            <div class="execution-status">
                <div class="spinner-small"></div>
                <span class="status-text">Connecting...</span>
            </div>
            <button class="btn btn-small btn-danger cancel-btn hidden">Cancel</button>
        </div>
        <div class="execution-log-container">
            <pre class="execution-log"></pre>
        </div>
    `;
    codeBlock.appendChild(execPanel);

    const statusText = execPanel.querySelector('.status-text');
    const logEl = execPanel.querySelector('.execution-log');
    const cancelBtn = execPanel.querySelector('.cancel-btn');
    const spinner = execPanel.querySelector('.spinner-small');

    // Show spinner immediately
    spinner.style.display = 'block';

    // Scroll to show panel
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;

    // Cancel button handler
    cancelBtn.onclick = async () => {
        cancelBtn.disabled = true;
        statusText.textContent = 'Cancelling...';
        await invoke('cancel_query');
    };

    try {
        // Small delay to ensure state is ready
        await new Promise(resolve => setTimeout(resolve, 100));

        // Start async execution
        const startResult = await invoke('execute_query_async');

        if (startResult.error) {
            execPanel.classList.add('error');
            statusText.textContent = 'Error';
            logEl.textContent = startResult.error;
            btn.textContent = 'Execute';
            btn.disabled = false;
            spinner.style.display = 'none';
            setExecutionLock(false);
            return;
        }

        // Poll for status
        chatExecutionInterval = setInterval(async () => {
            try {
                const status = await invoke('get_execution_status');

                // Update status text
                statusText.textContent = status.status;

                // Update log
                if (status.logs && status.logs.length > 0) {
                    logEl.textContent = status.logs.join('\n');
                    logEl.scrollTop = logEl.scrollHeight;
                }

                // Show/hide cancel button
                if (status.can_cancel) {
                    cancelBtn.classList.remove('hidden');
                    spinner.style.display = 'block';
                } else if (!status.complete) {
                    spinner.style.display = 'block';
                }

                // Handle completion
                if (status.complete) {
                    clearInterval(chatExecutionInterval);
                    chatExecutionInterval = null;
                    cancelBtn.classList.add('hidden');
                    spinner.style.display = 'none';
                    btn.textContent = 'Execute';
                    btn.disabled = false;

                    if (status.result) {
                        handleChatExecutionResult(execPanel, status.result);
                    }
                }
            } catch (e) {
                console.error('Chat polling error:', e);
            }
        }, 500);

    } catch (e) {
        execPanel.classList.add('error');
        statusText.textContent = 'Error';
        logEl.textContent = e.message || e;
        btn.textContent = 'Execute';
        btn.disabled = false;
        spinner.style.display = 'none';
        setExecutionLock(false);
    }
}

function handleChatExecutionResult(execPanel, result) {
    // Release global execution lock
    setExecutionLock(false);

    if (result.cancelled) {
        execPanel.classList.add('error');
        execPanel.querySelector('.status-text').textContent = 'Cancelled';
        return;
    }

    if (result.error) {
        execPanel.classList.add('error');
        execPanel.querySelector('.status-text').textContent = 'Error';
        const logEl = execPanel.querySelector('.execution-log');
        logEl.textContent += '\n[ERROR] ' + result.error;
        return;
    }

    if (result.success) {
        execPanel.classList.add('complete');
        execPanel.querySelector('.status-text').textContent = `Complete - ${result.row_count.toLocaleString()} rows`;

        // Add export buttons (CSP-safe, no inline onclick)
        const exportDiv = document.createElement('div');
        exportDiv.className = 'export-buttons';
        exportDiv.innerHTML = `
            <button class="btn btn-primary export-csv-btn">Save as CSV</button>
            <button class="btn btn-secondary export-parquet-btn">Save as Parquet</button>
        `;
        execPanel.appendChild(exportDiv);

        // Attach event listeners
        exportDiv.querySelector('.export-csv-btn').addEventListener('click', () => exportData('csv'));
        exportDiv.querySelector('.export-parquet-btn').addEventListener('click', () => exportData('parquet'));
    }
}

// Make functions globally accessible
window.executeCodeFromChat = executeCodeFromChat;
window.exportData = exportData;
window.togglePassword = togglePassword;

function togglePassword(inputId, btn) {
    const input = document.getElementById(inputId);
    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '';
    } else {
        input.type = 'password';
        btn.textContent = '';
    }
}

// ========== Settings Page ==========

async function loadSettings() {
    try {
        // Load LLM config
        const llmConfig = await invoke('get_llm_config');

        if (llmConfig.provider) {
            elements.llmProvider.value = llmConfig.provider;
            toggleProviderSettings();
        }

        // Groq settings
        if (llmConfig.has_groq_key) {
            document.getElementById('groq-api-key').value = llmConfig.groq_api_key || '';
            document.getElementById('groq-api-key').placeholder = '(API key saved)';
        }
        if (llmConfig.groq_model) {
            // Add the model to select if not present
            const groqSelect = document.getElementById('groq-model');
            if (!Array.from(groqSelect.options).find(o => o.value === llmConfig.groq_model)) {
                const opt = document.createElement('option');
                opt.value = llmConfig.groq_model;
                opt.textContent = llmConfig.groq_model;
                groqSelect.insertBefore(opt, groqSelect.firstChild);
            }
            groqSelect.value = llmConfig.groq_model;
        }

        // OpenAI settings
        if (llmConfig.has_openai_key) {
            document.getElementById('openai-api-key').value = llmConfig.openai_api_key || '';
            document.getElementById('openai-api-key').placeholder = '(API key saved)';
        }
        if (llmConfig.openai_model) {
            document.getElementById('openai-model').value = llmConfig.openai_model;
        }

        // Ollama settings
        if (llmConfig.ollama_base_url) {
            document.getElementById('ollama-url').value = llmConfig.ollama_base_url;
        }
        if (llmConfig.ollama_model) {
            document.getElementById('ollama-model').value = llmConfig.ollama_model;
        }
    } catch (e) {
        console.log('LLM config not loaded:', e);
    }

    try {
        // Load OpenSky config
        const openskyConfig = await invoke('get_opensky_config');
        document.getElementById('opensky-username').value = openskyConfig.username || '';
        // Password is masked, don't show it
        if (openskyConfig.has_password) {
            document.getElementById('opensky-password').placeholder = '(password saved)';
        }
    } catch (e) {
        console.log('OpenSky config not loaded:', e);
    }
}

function toggleProviderSettings() {
    const provider = elements.llmProvider.value;

    elements.providerSettings.forEach(el => {
        el.classList.add('hidden');
    });

    document.getElementById(`${provider}-settings`).classList.remove('hidden');
}

async function saveLlmSettings() {
    const provider = elements.llmProvider.value;
    let apiKey = '';
    let model = '';

    if (provider === 'groq') {
        apiKey = document.getElementById('groq-api-key').value;
        model = document.getElementById('groq-model').value;
    } else if (provider === 'openai') {
        apiKey = document.getElementById('openai-api-key').value;
        model = document.getElementById('openai-model').value;
    } else if (provider === 'ollama') {
        model = document.getElementById('ollama-model').value;
    }

    showLoading('Saving LLM settings...');

    try {
        const result = await invoke('save_llm_config', {
            provider: provider,
            model: model,
            apiKey: apiKey
        });

        if (result.error) {
            showToast(result.error, 'error');
        } else {
            showToast(`Configured ${result.provider || provider}`, 'success');
            updateAgentStatus();
        }
    } catch (e) {
        showToast('Failed to save: ' + (e.message || e), 'error');
    } finally {
        hideLoading();
    }
}

async function saveOpenskySettings() {
    const username = document.getElementById('opensky-username').value;
    const password = document.getElementById('opensky-password').value;

    showLoading('Saving OpenSky settings...');

    try {
        const result = await invoke('save_opensky_config', {
            username: username,
            password: password
        });

        if (result.error) {
            showToast(result.error, 'error');
        } else {
            showToast('OpenSky settings saved', 'success');
        }
    } catch (e) {
        showToast('Failed to save: ' + (e.message || e), 'error');
    } finally {
        hideLoading();
    }
}

async function fetchGroqModels() {
    const apiKey = document.getElementById('groq-api-key').value;
    const btn = document.getElementById('fetch-groq-models');
    const select = document.getElementById('groq-model');

    btn.disabled = true;
    btn.textContent = 'Loading...';

    try {
        const result = await invoke('fetch_groq_models', { apiKey: apiKey });

        if (result.error) {
            showToast('Failed to fetch models: ' + result.error, 'error');
        } else if (result.models && result.models.length > 0) {
            // Get current selection
            const currentValue = select.value;

            // Clear and repopulate
            select.innerHTML = '';
            result.models.forEach(model => {
                const opt = document.createElement('option');
                opt.value = model;
                opt.textContent = model;
                select.appendChild(opt);
            });

            // Restore selection if possible
            if (result.models.includes(currentValue)) {
                select.value = currentValue;
            }

            showToast(`Found ${result.models.length} models`, 'success');
        }
    } catch (e) {
        showToast('Failed to fetch models: ' + (e.message || e), 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Fetch';
    }
}

// ========== Utilities ==========

function showLoading(text = 'Loading...') {
    elements.loadingText.textContent = text;
    elements.loading.classList.remove('hidden');
}

function hideLoading() {
    elements.loading.classList.add('hidden');
}

function showToast(message, type = 'info') {
    elements.toast.textContent = message;
    elements.toast.className = `toast ${type}`;
    elements.toast.classList.remove('hidden');

    setTimeout(() => {
        elements.toast.classList.add('hidden');
    }, 3000);
}
