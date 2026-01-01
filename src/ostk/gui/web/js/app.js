/**
 * OSTK Frontend Application
 * Communicates with Python backend via window.pywebview.api
 */

// Wait for pywebview to be ready
window.addEventListener('pywebviewready', init);

// State
let currentFilters = {};
let queryPreviewShown = false;
let executionPollInterval = null;

// DOM Elements
const elements = {};

function init() {
    console.log('PyWebView ready, initializing app...');
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

    // Query page
    elements.filterChips.forEach(chip => {
        chip.addEventListener('click', () => showFilterModal(chip.dataset.filter));
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
    document.getElementById('fetch-groq-models').addEventListener('click', fetchGroqModels);

    // Modal
    elements.modalCancel.addEventListener('click', hideModal);
    elements.modalConfirm.addEventListener('click', confirmFilter);
    elements.modalInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') confirmFilter();
        if (e.key === 'Escape') hideModal();
    });
}

// ========== Tab Navigation ==========

function switchTab(page) {
    elements.tabs.forEach(t => t.classList.toggle('active', t.dataset.page === page));
    elements.pages.forEach(p => p.classList.toggle('active', p.id === `${page}-page`));
}

// ========== Query Page ==========

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
    await pywebview.api.set_query_param(filter, value);

    renderActiveFilters();
    hideModal();
    resetQueryState();
}

async function applyPreset(preset) {
    const times = await pywebview.api.get_quick_time_preset(preset);
    if (times.start) {
        currentFilters.start = times.start;
        await pywebview.api.set_query_param('start', times.start);
    }
    if (times.stop) {
        currentFilters.stop = times.stop;
        await pywebview.api.set_query_param('stop', times.stop);
    }
    renderActiveFilters();
    resetQueryState();
}

async function clearFilters() {
    currentFilters = {};
    await pywebview.api.clear_query_params();
    renderActiveFilters();
    resetQueryState();
}

function renderActiveFilters() {
    elements.activeFilters.innerHTML = '';

    for (const [key, value] of Object.entries(currentFilters)) {
        const item = document.createElement('div');
        item.className = 'filter-item';
        item.innerHTML = `
            <span class="label">${filterLabels[key]}:</span>
            <span class="value">${value}</span>
            <button class="remove" data-filter="${key}">&times;</button>
        `;
        elements.activeFilters.appendChild(item);
    }

    // Add remove listeners
    elements.activeFilters.querySelectorAll('.remove').forEach(btn => {
        btn.addEventListener('click', async () => {
            const filter = btn.dataset.filter;
            delete currentFilters[filter];
            await pywebview.api.set_query_param(filter, null);
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

    const preview = await pywebview.api.build_query_preview();
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

    // Invalidate any existing export buttons from both tabs
    invalidateAllExportButtons();

    // Show execution panel
    elements.executionPanel.classList.remove('hidden', 'complete', 'error', 'downloading');
    elements.executionStatusText.textContent = 'Connecting...';
    elements.executionLog.textContent = '';
    elements.cancelBtn.classList.add('hidden');  // Hidden until query ID received
    elements.cancelBtn.disabled = false;  // Re-enable for new query
    elements.executeBtn.disabled = true;

    try {
        // Start async execution
        const startResult = await pywebview.api.execute_query_async(null);

        if (startResult.error) {
            showExecutionError(startResult.error);
            return;
        }

        // Start polling for status
        startExecutionPolling();

    } catch (e) {
        showExecutionError(e.message);
    }
}

function startExecutionPolling() {
    // Clear any existing interval
    if (executionPollInterval) {
        clearInterval(executionPollInterval);
    }

    executionPollInterval = setInterval(async () => {
        try {
            const status = await pywebview.api.get_execution_status();

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
    elements.executeBtn.disabled = false;

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
    elements.executeBtn.disabled = false;

    // Add error to log
    const currentLog = elements.executionLog.textContent;
    elements.executionLog.textContent = currentLog + '\n[ERROR] ' + error;

    showToast(error, 'error');
}

async function cancelQuery() {
    elements.cancelBtn.disabled = true;
    elements.executionStatusText.textContent = 'Cancelling...';

    try {
        await pywebview.api.cancel_query();
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
        el.innerHTML = '<span style="color: var(--text-muted); font-size: 0.75rem;">⚠️ Data replaced by new query</span>';
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
        let result;
        if (format === 'csv') {
            result = await pywebview.api.export_csv('');
        } else {
            result = await pywebview.api.export_parquet('');
        }

        if (result.cancelled) {
            // User cancelled the dialog
            return;
        }

        if (result.error) {
            showToast(result.error, 'error');
        } else if (result.success) {
            showToast(`Exported to ${result.filepath}`, 'success');
        }
    } catch (e) {
        showToast('Export failed: ' + e.message, 'error');
    }
}

// ========== Chat Page ==========

async function updateAgentStatus() {
    const status = await pywebview.api.get_agent_status();

    if (status.configured) {
        elements.agentStatus.textContent = `Using ${status.provider} (${status.model})`;
        elements.agentStatus.className = 'agent-status configured';
    } else {
        elements.agentStatus.textContent = status.error || 'LLM not configured. Go to Settings to set up.';
        elements.agentStatus.className = 'agent-status error';
    }
}

async function sendMessage() {
    const message = elements.chatInput.value.trim();
    if (!message) return;

    // Add user message
    addChatMessage('user', message);
    elements.chatInput.value = '';

    showLoading('Thinking...');

    try {
        const result = await pywebview.api.send_message(message);

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
        addChatMessage('assistant', 'Error: ' + e.message, 'error');
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
                <button class="btn btn-primary execute-btn" onclick="executeCodeFromChat('${msgId}')">Execute</button>
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
}

function formatMessage(content) {
    // Simple markdown formatting
    return content
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

let chatExecutionInterval = null;

async function executeCodeFromChat(codeBlockId) {
    const codeBlock = document.getElementById(codeBlockId);
    const btn = codeBlock.querySelector('.execute-btn');

    // Disable button
    btn.disabled = true;
    btn.textContent = 'Running...';

    // Invalidate any existing export buttons from both tabs
    invalidateAllExportButtons();

    // Remove any existing execution panel in this code block
    const existingPanel = codeBlock.querySelector('.chat-execution');
    if (existingPanel) existingPanel.remove();

    // Create inline execution panel
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
        <pre class="execution-log"></pre>
    `;
    codeBlock.appendChild(execPanel);

    const statusText = execPanel.querySelector('.status-text');
    const logEl = execPanel.querySelector('.execution-log');
    const cancelBtn = execPanel.querySelector('.cancel-btn');
    const spinner = execPanel.querySelector('.spinner-small');

    // Scroll to show panel
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;

    try {
        // Start async execution
        const startResult = await pywebview.api.execute_query_async(null);

        if (startResult.error) {
            execPanel.classList.add('error');
            statusText.textContent = 'Error';
            logEl.textContent = startResult.error;
            btn.textContent = 'Execute';
            btn.disabled = false;
            spinner.style.display = 'none';
            return;
        }

        // Poll for status
        chatExecutionInterval = setInterval(async () => {
            try {
                const status = await pywebview.api.get_execution_status();

                statusText.textContent = status.status;

                if (status.logs && status.logs.length > 0) {
                    logEl.textContent = status.logs.join('\n');
                    logEl.scrollTop = logEl.scrollHeight;
                    // Keep execution panel visible in chat
                    execPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }

                // Show/hide cancel button and spinner
                if (status.can_cancel) {
                    cancelBtn.classList.remove('hidden');
                    spinner.style.display = 'block';
                } else {
                    cancelBtn.classList.add('hidden');
                    spinner.style.display = 'none';
                }

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

        // Cancel button handler
        cancelBtn.onclick = async () => {
            cancelBtn.disabled = true;
            statusText.textContent = 'Cancelling...';
            await pywebview.api.cancel_query();
        };

    } catch (e) {
        execPanel.classList.add('error');
        statusText.textContent = 'Error';
        logEl.textContent = e.message;
        btn.textContent = 'Execute';
        btn.disabled = false;
        spinner.style.display = 'none';
    }
}

function handleChatExecutionResult(execPanel, result) {
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

        // Add export buttons
        const exportDiv = document.createElement('div');
        exportDiv.className = 'export-buttons';
        exportDiv.innerHTML = `
            <button class="btn btn-primary" onclick="exportData('csv')">Save as CSV</button>
            <button class="btn btn-secondary" onclick="exportData('parquet')">Save as Parquet</button>
        `;
        execPanel.appendChild(exportDiv);
    }
}

// Make functions globally accessible
window.executeCodeFromChat = executeCodeFromChat;
window.togglePassword = togglePassword;

function togglePassword(inputId, btn) {
    const input = document.getElementById(inputId);
    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '🙈';
    } else {
        input.type = 'password';
        btn.textContent = '👁';
    }
}

// ========== Settings Page ==========

async function loadSettings() {
    // Load LLM config
    const llmConfig = await pywebview.api.get_llm_config();

    if (llmConfig.provider) {
        elements.llmProvider.value = llmConfig.provider;
        toggleProviderSettings();
    }

    document.getElementById('groq-api-key').value = llmConfig.groq_api_key || '';
    document.getElementById('groq-model').value = llmConfig.groq_model || 'openai/gpt-oss-120b';
    document.getElementById('openai-api-key').value = llmConfig.openai_api_key || '';
    document.getElementById('openai-model').value = llmConfig.openai_model || 'gpt-4o';
    document.getElementById('ollama-url').value = llmConfig.ollama_base_url || 'http://localhost:11434';
    document.getElementById('ollama-model').value = llmConfig.ollama_model || 'llama3.1:8b';

    // Load OpenSky config
    const openskyConfig = await pywebview.api.get_pyopensky_config();
    document.getElementById('opensky-username').value = openskyConfig.username || '';
    document.getElementById('opensky-password').value = openskyConfig.password || '';
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
    let baseUrl = '';

    if (provider === 'groq') {
        apiKey = document.getElementById('groq-api-key').value;
        model = document.getElementById('groq-model').value;
    } else if (provider === 'openai') {
        apiKey = document.getElementById('openai-api-key').value;
        model = document.getElementById('openai-model').value;
    } else if (provider === 'ollama') {
        baseUrl = document.getElementById('ollama-url').value;
        model = document.getElementById('ollama-model').value;
    }

    showLoading('Saving LLM settings...');

    try {
        const result = await pywebview.api.save_llm_config(provider, model, apiKey, baseUrl);

        if (result.error) {
            showToast(result.error, 'error');
        } else {
            showToast(`Configured ${result.provider}`, 'success');
            updateAgentStatus();
        }
    } finally {
        hideLoading();
    }
}

async function saveOpenskySettings() {
    const username = document.getElementById('opensky-username').value;
    const password = document.getElementById('opensky-password').value;

    showLoading('Saving OpenSky settings...');

    try {
        const result = await pywebview.api.save_pyopensky_config(username, password, '', '', '90 days');

        if (result.error) {
            showToast(result.error, 'error');
        } else {
            showToast('OpenSky settings saved', 'success');
        }
    } finally {
        hideLoading();
    }
}

async function fetchGroqModels() {
    const apiKey = document.getElementById('groq-api-key').value;

    if (!apiKey) {
        showToast('Please enter your Groq API key first', 'error');
        return;
    }

    const fetchBtn = document.getElementById('fetch-groq-models');
    fetchBtn.disabled = true;
    fetchBtn.textContent = '...';

    try {
        const result = await pywebview.api.fetch_groq_models(apiKey);

        if (result.error) {
            showToast(result.error, 'error');
            return;
        }

        if (result.models && result.models.length > 0) {
            const select = document.getElementById('groq-model');
            const currentValue = select.value;

            // Clear and repopulate
            select.innerHTML = '';
            result.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                // Mark default model
                if (model === result.default) {
                    option.textContent = model + ' (default)';
                } else {
                    option.textContent = model;
                }
                select.appendChild(option);
            });

            // Restore selection if still available, otherwise use default
            if (result.models.includes(currentValue)) {
                select.value = currentValue;
            } else if (result.default) {
                select.value = result.default;
            }

            showToast(`Found ${result.models.length} models with tool calling`, 'success');
        }
    } catch (e) {
        showToast('Failed to fetch models: ' + e.message, 'error');
    } finally {
        fetchBtn.disabled = false;
        fetchBtn.textContent = 'Fetch';
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
