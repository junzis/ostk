/**
 * OSTK Frontend Application
 * Communicates with Rust backend via Tauri invoke
 */

// Tauri API helpers
const { invoke } = window.__TAURI__.core;
const { save } = window.__TAURI__.dialog;
const { open: openExternal } = window.__TAURI__.shell;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', init);

// State
let currentFilters = {};
let currentQueryType = 'flights';  // Default query type
let queryPreviewShown = false;
let executionPollInterval = null;
let isExecuting = false;  // Global lock to prevent concurrent executions

// DOM Elements
const elements = {};

async function init() {
    console.log('OSTK initializing...');
    cacheElements();
    setupEventListeners();
    loadSettings();
    updateAgentStatus();
    // Set initial filter visibility and sync query type to backend
    updateFilterVisibility(currentQueryType);
    await invoke('set_query_type', { queryType: currentQueryType });
}

function cacheElements() {
    // Tabs
    elements.tabs = document.querySelectorAll('.tab');
    elements.pages = document.querySelectorAll('.page');

    // Query page - query type selector
    elements.queryTypeBtns = document.querySelectorAll('.query-type-btn');

    // Query page - filters
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

    // Map Modal
    elements.mapModal = document.getElementById('map-modal');
    elements.boundsMap = document.getElementById('bounds-map');
    elements.boundsText = document.getElementById('bounds-text');
    elements.mapCancel = document.getElementById('map-cancel');
    elements.mapClear = document.getElementById('map-clear');
    elements.mapConfirm = document.getElementById('map-confirm');
    elements.modePan = document.getElementById('mode-pan');
    elements.modeDraw = document.getElementById('mode-draw');

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

    // Query page - query type selector
    elements.queryTypeBtns.forEach(btn => {
        btn.addEventListener('click', () => selectQueryType(btn.dataset.type));
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

    // Map Modal
    elements.mapCancel.addEventListener('click', hideMapModal);
    elements.mapClear.addEventListener('click', clearMapSelection);
    elements.mapConfirm.addEventListener('click', confirmMapSelection);
    elements.modePan.addEventListener('click', () => setMapMode('pan'));
    elements.modeDraw.addEventListener('click', () => setMapMode('draw'));

    // External links - use Tauri shell.open() to open in default browser
    document.querySelectorAll('.external-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const url = link.dataset.url;
            if (url) {
                openExternal(url);
            }
        });
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

// ========== Query Type Selection ==========

async function selectQueryType(queryType) {
    currentQueryType = queryType;

    // Update button states
    elements.queryTypeBtns.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.type === queryType);
    });

    // Update filter chip visibility based on query type
    updateFilterVisibility(queryType);

    // Send to backend
    await invoke('set_query_type', { queryType: queryType });

    // Clear any filters that are now hidden
    clearHiddenFilters();

    // Reset query state
    resetQueryState();
}

function updateFilterVisibility(queryType) {
    // Show/hide filter chips based on query type
    elements.filterChips.forEach(chip => {
        const allowedTypes = chip.dataset.queryTypes;
        if (allowedTypes) {
            // Chip has specific query type restrictions
            const isVisible = allowedTypes.split(',').includes(queryType);
            chip.classList.toggle('filter-hidden', !isVisible);
        } else {
            // Chip is available for all query types
            chip.classList.remove('filter-hidden');
        }
    });
}

function clearHiddenFilters() {
    // Remove any active filters that are now hidden
    const hiddenFilterTypes = [];
    elements.filterChips.forEach(chip => {
        if (chip.classList.contains('filter-hidden')) {
            hiddenFilterTypes.push(chip.dataset.filter);
        }
    });

    hiddenFilterTypes.forEach(async (filter) => {
        if (currentFilters[filter] !== undefined) {
            delete currentFilters[filter];
            await invoke('set_query_param', { key: filter, value: null });
        }
    });

    renderActiveFilters();
}

// ========== Query Page ==========

function addFilterInline(filter) {
    // Handle bounds filter specially - show map modal
    if (filter === 'bounds') {
        showMapModal();
        return;
    }

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
    bounds: 'Region',
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

        // Handle bounds specially - it's an object, not a string
        if (key === 'bounds' && typeof value === 'object') {
            const boundsStr = `(${value.west}, ${value.south}, ${value.east}, ${value.north})`;
            item.innerHTML = `
                <span class="label">${filterLabels[key]}</span>
                <span class="value bounds-value" data-filter="${key}">${boundsStr}</span>
                <button class="remove" data-filter="${key}">&times;</button>
            `;
        } else {
            const displayValue = value === '' ? '' : value;
            const placeholder = getPlaceholder(key);
            item.innerHTML = `
                <span class="label">${filterLabels[key]}</span>
                <span class="value ${value === '' ? 'empty' : ''}" data-filter="${key}">${displayValue || placeholder}</span>
                <input class="value-input hidden" data-filter="${key}" type="text" value="${displayValue}" placeholder="${placeholder}">
                <button class="remove" data-filter="${key}">&times;</button>
            `;
        }
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

            // Bounds opens map modal instead of inline edit
            if (filter === 'bounds') {
                showMapModal();
                return;
            }

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
        // Convert bounds object {west, south, east, north} to array format for backend
        if (key === 'bounds' && value && typeof value === 'object') {
            await invoke('set_query_param', {
                key,
                value: [value.west, value.south, value.east, value.north]
            });
        } else {
            await invoke('set_query_param', { key, value });
        }
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
    elements.executionLog.innerHTML = '';
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
                elements.executionLog.innerHTML = renderLogLines(status.logs);
                attachLogLinkHandlers(elements.executionLog);
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
    const currentLog = elements.executionLog.innerHTML;
    elements.executionLog.innerHTML = currentLog + '\n[ERROR] ' + escapeHtml(error);

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
                addChatMessage('assistant', msg.content, msg.type, msg.hint);
            }
        });

    } catch (e) {
        addChatMessage('assistant', 'Error: ' + (e.message || e), 'error');
    } finally {
        hideLoading();
    }
}

function addChatMessage(role, content, type = 'text', hint = null) {
    const msg = document.createElement('div');
    msg.className = `message ${role}`;
    if (type === 'error') msg.classList.add('error');

    let html = '<div class="message-content">';

    if (type === 'code') {
        const msgId = 'code-' + Date.now();
        html += `
            <div class="code-block" id="${msgId}">
                <pre><code>${escapeHtml(content)}</code></pre>
                ${hint ? `<div class="query-hint">${escapeHtml(hint)}</div>` : ''}
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

// Convert URLs in log text to clickable links
function linkifyLogText(text) {
    const urlPattern = /(https?:\/\/[^\s<]+)/g;
    return escapeHtml(text).replace(urlPattern, (url) => {
        return `<a href="#" class="log-link" data-url="${escapeHtml(url)}">${escapeHtml(url)}</a>`;
    });
}

// Render log lines with clickable URLs
function renderLogLines(logs) {
    return logs.map(line => linkifyLogText(line)).join('\n');
}

// Attach click handlers to log links (for opening URLs externally)
// Uses event delegation on the container for reliability
function attachLogLinkHandlers(container) {
    // Use event delegation - attach once to container
    if (!container.dataset.linkHandlerAttached) {
        container.dataset.linkHandlerAttached = 'true';
        container.addEventListener('click', (e) => {
            const link = e.target.closest('.log-link');
            if (link) {
                e.preventDefault();
                e.stopPropagation();
                const url = link.dataset.url;
                if (url) {
                    console.log('Opening URL:', url);
                    openExternal(url);
                }
            }
        });
    }
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
            logEl.innerHTML = escapeHtml(startResult.error);
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
                    logEl.innerHTML = renderLogLines(status.logs);
                    attachLogLinkHandlers(logEl);
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
        logEl.innerHTML = escapeHtml(e.message || e);
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
        logEl.innerHTML += '\n[ERROR] ' + escapeHtml(result.error);
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

// ========== Map Modal for Bounds Selection ==========

let boundsMap = null;
let currentRectangle = null;
let cornerMarkers = [];  // [SW, NW, NE, SE] corner handles
let mapMode = 'pan';  // 'pan' or 'draw'
let isDrawing = false;
let isDragging = false;
let isResizing = false;
let resizeCorner = null;  // Which corner is being dragged
let drawStartLatLng = null;
let dragStartLatLng = null;
let dragStartBounds = null;
let selectedBounds = null;

function showMapModal() {
    elements.mapModal.classList.remove('hidden');

    // Initialize map if not already done
    if (!boundsMap) {
        boundsMap = L.map('bounds-map').setView([50, 10], 4);  // Center on Europe

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 18,
        }).addTo(boundsMap);

        // Add mouse event handlers for drawing/dragging
        boundsMap.on('mousedown', onMapMouseDown);
        boundsMap.on('mousemove', onMapMouseMove);
        boundsMap.on('mouseup', onMapMouseUp);

        // Native DOM mousemove for cursor updates (fires over all layers)
        elements.boundsMap.addEventListener('mousemove', onMapCursorMove);

        // Set initial cursor (grab for panning, Shift+drag to draw)
        elements.boundsMap.style.cursor = 'grab';

        // Handle window resize
        window.addEventListener('resize', onWindowResize);
    }

    // Force map to recalculate size (needed when modal becomes visible)
    setTimeout(() => {
        boundsMap.invalidateSize();

        // If there's an existing bounds filter, show it
        if (currentFilters.bounds) {
            const b = currentFilters.bounds;
            selectedBounds = b;
            showRectangle([[b.south, b.west], [b.north, b.east]]);
            updateBoundsDisplay();
            elements.mapConfirm.disabled = false;
        }
    }, 100);
}

function onWindowResize() {
    // Update map size when window is resized (only if modal is visible)
    if (boundsMap && !elements.mapModal.classList.contains('hidden')) {
        boundsMap.invalidateSize();
    }
}

function hideMapModal() {
    elements.mapModal.classList.add('hidden');
}

function setMapMode(mode) {
    mapMode = mode;
    elements.modePan.classList.toggle('active', mode === 'pan');
    elements.modeDraw.classList.toggle('active', mode === 'draw');
    // Update cursor
    elements.boundsMap.style.cursor = mode === 'draw' ? 'crosshair' : 'grab';
}

function isPointInRectangle(latlng) {
    if (!currentRectangle) return false;
    return currentRectangle.getBounds().contains(latlng);
}

function onMapMouseDown(e) {
    if (e.originalEvent.button !== 0) return;  // Only left click

    // Check if clicking on a corner - start resizing
    const corner = getCornerAtPoint(e.latlng);
    if (corner) {
        isResizing = true;
        resizeCorner = corner;
        dragStartBounds = currentRectangle.getBounds();
        boundsMap.dragging.disable();
        return;
    }

    // Check if clicking on existing rectangle - start dragging rectangle
    if (currentRectangle && isPointInRectangle(e.latlng)) {
        isDragging = true;
        dragStartLatLng = e.latlng;
        dragStartBounds = currentRectangle.getBounds();
        boundsMap.dragging.disable();
        return;
    }

    // Only draw in draw mode, otherwise allow map panning
    if (mapMode !== 'draw') {
        return;  // Let Leaflet handle map panning
    }

    // Start drawing new rectangle
    isDrawing = true;
    drawStartLatLng = e.latlng;

    // Remove existing rectangle when drawing new one
    if (currentRectangle) {
        boundsMap.removeLayer(currentRectangle);
        currentRectangle = null;
        removeCornerMarkers();
    }

    boundsMap.dragging.disable();
}

function onMapMouseMove(e) {
    // Handle resizing from corner
    if (isResizing && resizeCorner && dragStartBounds) {
        const bounds = dragStartBounds;
        let newSouth = bounds.getSouth();
        let newNorth = bounds.getNorth();
        let newWest = bounds.getWest();
        let newEast = bounds.getEast();

        // Update the appropriate edges based on which corner is being dragged
        switch (resizeCorner) {
            case 'sw':
                newSouth = e.latlng.lat;
                newWest = e.latlng.lng;
                break;
            case 'nw':
                newNorth = e.latlng.lat;
                newWest = e.latlng.lng;
                break;
            case 'ne':
                newNorth = e.latlng.lat;
                newEast = e.latlng.lng;
                break;
            case 'se':
                newSouth = e.latlng.lat;
                newEast = e.latlng.lng;
                break;
        }

        // Ensure bounds are valid (south < north, west < east)
        if (newSouth > newNorth) [newSouth, newNorth] = [newNorth, newSouth];
        if (newWest > newEast) [newWest, newEast] = [newEast, newWest];

        const newBounds = L.latLngBounds(
            [newSouth, newWest],
            [newNorth, newEast]
        );

        currentRectangle.setBounds(newBounds);
        updateCornerMarkers();
        return;
    }

    // Handle dragging existing rectangle
    if (isDragging && dragStartLatLng && dragStartBounds) {
        const latDiff = e.latlng.lat - dragStartLatLng.lat;
        const lngDiff = e.latlng.lng - dragStartLatLng.lng;

        const newBounds = L.latLngBounds(
            [dragStartBounds.getSouth() + latDiff, dragStartBounds.getWest() + lngDiff],
            [dragStartBounds.getNorth() + latDiff, dragStartBounds.getEast() + lngDiff]
        );

        currentRectangle.setBounds(newBounds);
        updateCornerMarkers();
        return;
    }

    // Handle drawing new rectangle
    if (isDrawing && drawStartLatLng) {
        const bounds = L.latLngBounds(drawStartLatLng, e.latlng);

        if (currentRectangle) {
            currentRectangle.setBounds(bounds);
        } else {
            currentRectangle = L.rectangle(bounds, {
                color: '#3b82f6',
                weight: 2,
                fillOpacity: 0.15,
                className: 'bounds-rectangle'
            }).addTo(boundsMap);
        }
        return;
    }

    // Update cursor based on what's under the mouse (only when not actively drawing/dragging)
    updateMapCursor(e.latlng);
}

// Native DOM event handler for cursor updates (works over all Leaflet layers)
function onMapCursorMove(e) {
    // Don't update cursor during active operations
    if (isDrawing || isDragging || isResizing) return;

    // Convert pixel coordinates to lat/lng
    const rect = elements.boundsMap.getBoundingClientRect();
    const point = L.point(e.clientX - rect.left, e.clientY - rect.top);
    const latlng = boundsMap.containerPointToLatLng(point);

    updateMapCursor(latlng);
}

function updateMapCursor(latlng) {
    const mapContainer = elements.boundsMap;

    // Check if over the rectangle (includes corners)
    if (currentRectangle && isPointInRectangle(latlng)) {
        mapContainer.style.cursor = 'move';
        return;
    }

    // Cursor based on current mode
    mapContainer.style.cursor = mapMode === 'draw' ? 'crosshair' : 'grab';
}

function onMapMouseUp(e) {
    // Finish resizing
    if (isResizing) {
        isResizing = false;
        resizeCorner = null;
        dragStartBounds = null;
        boundsMap.dragging.enable();

        if (currentRectangle) {
            updateSelectedBoundsFromRectangle();
            updateCornerMarkers();
        }
        return;
    }

    // Finish dragging
    if (isDragging) {
        isDragging = false;
        dragStartLatLng = null;
        dragStartBounds = null;
        boundsMap.dragging.enable();

        if (currentRectangle) {
            updateSelectedBoundsFromRectangle();
            updateCornerMarkers();
        }
        return;
    }

    // Finish drawing
    if (!isDrawing) return;

    isDrawing = false;
    boundsMap.dragging.enable();

    if (drawStartLatLng && currentRectangle) {
        updateSelectedBoundsFromRectangle();
        createCornerMarkers();
    }

    drawStartLatLng = null;
}

function updateSelectedBoundsFromRectangle() {
    const bounds = currentRectangle.getBounds();
    selectedBounds = {
        west: Math.round(bounds.getWest() * 100) / 100,
        south: Math.round(bounds.getSouth() * 100) / 100,
        east: Math.round(bounds.getEast() * 100) / 100,
        north: Math.round(bounds.getNorth() * 100) / 100
    };
    updateBoundsDisplay();
    elements.mapConfirm.disabled = false;
}

function showRectangle(bounds) {
    if (currentRectangle) {
        boundsMap.removeLayer(currentRectangle);
    }
    currentRectangle = L.rectangle(bounds, {
        color: '#3b82f6',
        weight: 2,
        fillOpacity: 0.15
    }).addTo(boundsMap);
    boundsMap.fitBounds(bounds, { padding: [20, 20] });
    updateCornerMarkers();
}

// Corner marker icon
const cornerIcon = L.divIcon({
    className: 'corner-marker',
    iconSize: [16, 16],
    iconAnchor: [8, 8]
});

function createCornerMarkers() {
    // Remove existing markers
    removeCornerMarkers();

    if (!currentRectangle) return;

    const bounds = currentRectangle.getBounds();
    const corners = [
        { pos: bounds.getSouthWest(), name: 'sw' },
        { pos: bounds.getNorthWest(), name: 'nw' },
        { pos: bounds.getNorthEast(), name: 'ne' },
        { pos: bounds.getSouthEast(), name: 'se' }
    ];

    corners.forEach(corner => {
        const marker = L.marker(corner.pos, {
            icon: cornerIcon,
            draggable: false  // We handle dragging manually
        }).addTo(boundsMap);

        marker.cornerName = corner.name;
        cornerMarkers.push(marker);
    });
}

function removeCornerMarkers() {
    cornerMarkers.forEach(marker => {
        boundsMap.removeLayer(marker);
    });
    cornerMarkers = [];
}

function updateCornerMarkers() {
    if (!currentRectangle || cornerMarkers.length === 0) {
        createCornerMarkers();
        return;
    }

    const bounds = currentRectangle.getBounds();
    const positions = [
        bounds.getSouthWest(),
        bounds.getNorthWest(),
        bounds.getNorthEast(),
        bounds.getSouthEast()
    ];

    cornerMarkers.forEach((marker, i) => {
        marker.setLatLng(positions[i]);
    });
}

function getCornerAtPoint(latlng) {
    if (!cornerMarkers || cornerMarkers.length === 0) return null;

    const threshold = 20;  // pixels
    const clickPoint = boundsMap.latLngToContainerPoint(latlng);

    for (const marker of cornerMarkers) {
        const markerPoint = boundsMap.latLngToContainerPoint(marker.getLatLng());
        if (markerPoint.distanceTo(clickPoint) < threshold) {
            return marker.cornerName;
        }
    }
    return null;
}

function updateBoundsDisplay() {
    if (selectedBounds) {
        elements.boundsText.textContent =
            `West: ${selectedBounds.west}°, South: ${selectedBounds.south}°, East: ${selectedBounds.east}°, North: ${selectedBounds.north}°`;
    } else {
        elements.boundsText.textContent = 'No region selected';
    }
}

function clearMapSelection() {
    if (currentRectangle) {
        boundsMap.removeLayer(currentRectangle);
        currentRectangle = null;
    }
    selectedBounds = null;
    updateBoundsDisplay();
    elements.mapConfirm.disabled = true;
}

async function confirmMapSelection() {
    if (!selectedBounds) return;

    // Store bounds in currentFilters
    currentFilters.bounds = selectedBounds;

    // Send to backend
    await invoke('set_query_param', {
        key: 'bounds',
        value: [selectedBounds.west, selectedBounds.south, selectedBounds.east, selectedBounds.north]
    });

    renderActiveFilters();
    hideMapModal();
    resetQueryState();
}
