/**
 * WorkbenchForm — handles parameter + field collection and job start from workbench.
 */
class WorkbenchForm {
    constructor(config) {
        this.agentSlug = config.agentSlug;
        this.startUrl = config.startUrl || `/admin/agents/${config.agentSlug}/workbench/start`;
        this.stopUrl = config.stopUrl || `/admin/agents/${config.agentSlug}/workbench/stop`;
        this.monitorUrl = config.monitorUrl || `/admin/agents/${config.agentSlug}/workbench/jobs/`;
        this.monitorContainerId = config.monitorContainerId || 'monitor-container';
        this.errorsContainerId = config.errorsContainerId || 'workbench-errors';
        this.basePath = `/admin/agents/${config.agentSlug}/workbench`;
        this.activeJobId = null;

        // Optional callback overrides for param/field collection and API key
        this._getApiKey = config.getApiKey || (() => sessionStorage.getItem('admin_api_key') || '');
        this._getParams = config.getParams || null;
        this._getFields = config.getFields || null;
        if (config.onJobStarted) this.onJobStarted = config.onJobStarted;
        if (config.onError) this.onError = config.onError;
        this._ws = null;
    }

    getApiKey() {
        return this._getApiKey();
    }

    collectParameters() {
        if (this._getParams) return this._getParams();
        const params = {};
        document.querySelectorAll('#parameters-form input, #parameters-form select').forEach(el => {
            if (el.name) {
                params[el.name] = el.type === 'checkbox' ? el.checked : el.value;
            }
        });
        return params;
    }

    collectFields() {
        if (this._getFields) return this._getFields();
        const fields = {};
        document.querySelectorAll('#fields-form input, #fields-form select, #fields-form textarea').forEach(el => {
            if (el.name) {
                if (el.type === 'checkbox') {
                    fields[el.name] = el.checked;
                } else if (el.type === 'select-multiple') {
                    fields[el.name] = Array.from(el.selectedOptions).map(o => o.value);
                } else if (el.type === 'number') {
                    fields[el.name] = el.value ? Number(el.value) : null;
                } else {
                    fields[el.name] = el.value;
                }
            }
        });
        return fields;
    }

    validateRequired() {
        let valid = true;
        const selector = '#parameters-form [required], #fields-form [required]';
        const elements = document.querySelectorAll(selector);
        elements.forEach(el => {
            const value = el.type === 'checkbox' ? el.checked : (el.value || '').toString().trim();
            // Skip validation for env-set fields — backend will fill them
            const envSet = el.dataset.envSet === 'true';
            if (el.type === 'checkbox' ? !value : (value === '' && !envSet)) {
                el.classList.add('border-red-500');
                valid = false;
            } else {
                el.classList.remove('border-red-500');
            }
        });
        return valid;
    }

    async startJob() {
        if (!this.validateRequired()) {
            this.onError('Please fill in all required fields.');
            const el = document.getElementById(this.errorsContainerId);
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            return;
        }

        const parameters = this.collectParameters();
        const fields = this.collectFields();

        const btn = document.getElementById('btn-start');
        if (btn) btn.disabled = true;
        try {
            const response = await fetch(this.startUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': this.getApiKey(),
                },
                body: JSON.stringify({ parameters, fields }),
            });
            let result;
            try {
                result = await response.json();
            } catch (_) {
                const text = await response.text();
                this.onError(response.ok ? 'Invalid response from server' : (text.slice(0, 200) || `HTTP ${response.status}`));
                return;
            }
            if (response.ok) {
                if (!result || result.id == null) {
                    this.onError('Invalid response: missing job id');
                    return;
                }
                this.activeJobId = result.id;
                this.onError(''); // clear previous errors
                this.onJobStarted(result);
            } else {
                const detail = Array.isArray(result.detail) ? result.detail.map(d => d.msg || JSON.stringify(d)).join('; ') : (result.detail || 'Failed to start job');
                this.onError(detail);
            }
        } catch (e) {
            this.onError(`Network error: ${e.message}`);
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    async stopJob(jobId) {
        const targetJobId = jobId || this.activeJobId;
        if (!targetJobId) return;

        try {
            const response = await fetch(`${this.basePath}/jobs/${targetJobId}/stop`, {
                method: 'POST',
                headers: { 'X-API-Key': this.getApiKey() },
            });
            const result = await response.json();
            if (!response.ok) {
                this.onError(result.detail || 'Failed to stop job');
            } else {
                // Refresh monitor to show updated state
                this.refreshMonitor();
            }
        } catch (e) {
            this.onError(`Network error: ${e.message}`);
        }
    }

    async getStatus() {
        if (!this.activeJobId) return;

        try {
            const response = await fetch(`${this.basePath}/jobs/${this.activeJobId}/status`, {
                headers: { 'X-API-Key': this.getApiKey() },
            });
            return await response.json();
        } catch (e) {
            this.onError(`Network error: ${e.message}`);
            return null;
        }
    }

    /** Shared POST to /cases/{caseId}/answer endpoint. */
    async _postAnswer(caseId, answerPayload) {
        if (!this.activeJobId) return null;
        try {
            const response = await fetch(
                `${this.basePath}/jobs/${this.activeJobId}/cases/${caseId}/answer`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': this.getApiKey(),
                    },
                    body: JSON.stringify({ answer: answerPayload }),
                },
            );
            const result = await response.json();
            if (!response.ok) {
                this.onError(result.detail || result.message || 'Failed to submit answer');
                return null;
            }
            this.onError('');
            this.refreshMonitor(true);
            return result;
        } catch (e) {
            this.onError(`Network error: ${e.message}`);
            return null;
        }
    }

    async submitHitlAnswer(caseId, formElement) {
        const answer = {};
        new FormData(formElement).forEach((value, key) => {
            answer[key] = value;
        });
        // Handle checkboxes that aren't in FormData when unchecked
        formElement.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            if (!(cb.name in answer)) {
                answer[cb.name] = false;
            } else {
                answer[cb.name] = true;
            }
        });

        const result = await this._postAnswer(caseId, answer);
        if (result) {
            formElement.remove();
        }
    }

    async submitDialogMessage(caseId, message) {
        if (!message) return;
        await this._postAnswer(caseId, { action: 'message', text: message });
    }

    async confirmDialog(caseId) {
        await this._postAnswer(caseId, { action: 'confirm' });
    }

    /** Show/hide Stop and Status buttons based on active job. */
    _updateButtons(terminal) {
        const stop = document.getElementById('btn-stop');
        const status = document.getElementById('btn-status');
        if (this.activeJobId && !terminal) {
            if (stop) stop.classList.remove('hidden');
            if (status) status.classList.remove('hidden');
        } else {
            if (stop) stop.classList.add('hidden');
            if (status) status.classList.remove('hidden');
        }
    }

    /** True when a HITL dialog or form is visible in the monitor. */
    _hasActiveHitl() {
        const container = document.getElementById(this.monitorContainerId);
        if (!container) return false;
        return !!(
            container.querySelector('form[id^="hitl-form-"]') ||
            container.querySelector('[id^="hitl-dialog-"]')
        );
    }

    /** Fetch and render the monitor partial for the active job.
     *  @param {boolean} force - bypass HITL guard (used after dialog submit/confirm)
     */
    refreshMonitor(force) {
        if (!this.activeJobId) return;
        const container = document.getElementById(this.monitorContainerId);
        if (!container) return;
        // Don't overwrite while user interacts with HITL (unless forced)
        if (!force && this._hasActiveHitl()) return;
        const url = `${this.basePath}/jobs/${this.activeJobId}`;
        const apiKey = this.getApiKey();
        const headers = apiKey ? { 'X-API-Key': apiKey } : {};
        const self = this;
        fetch(url, { headers })
            .then(r => r.text())
            .then(html => {
                container.innerHTML = html;
                if (typeof Alpine !== 'undefined') {
                    Alpine.initTree(container);
                }
                // Disconnect WebSocket when job reaches terminal state
                const partial = container.querySelector('#workbench-monitor-partial');
                if (partial && partial.dataset.jobTerminal === 'true') {
                    self.disconnectWebSocket();
                    self._updateButtons(true);
                }
            })
            .catch(() => {});
    }

    /** Check if the monitor shows a terminal job state. */
    _isJobTerminal() {
        var container = document.getElementById(this.monitorContainerId);
        if (!container) return false;
        var partial = container.querySelector('#workbench-monitor-partial');
        return partial && partial.dataset.jobTerminal === 'true';
    }

    /** Connect a WebSocket that pushes typed signals when state changes. */
    connectWebSocket(jobId) {
        // Don't connect for terminal jobs
        if (this._isJobTerminal()) return;
        this.disconnectWebSocket();
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${location.host}${this.basePath}/jobs/${jobId}/ws`;
        this._ws = new WebSocket(wsUrl);
        const self = this;
        this._ws.onmessage = (event) => {
            const msg = event.data;
            if (msg === 'terminal') {
                self.refreshMonitor(true);
                self._refreshConsole();
                self._refreshJobsList();
                self.disconnectWebSocket();
                self._updateButtons(true);
            } else if (msg === 'monitor' || msg === 'refresh') {
                self.refreshMonitor();
            } else if (msg === 'console') {
                self._refreshConsole();
            } else if (msg === 'jobs') {
                self._refreshJobsList();
            } else if (msg === 'ping') {
                self._ws.send('pong');
            }
        };
        this._ws.onclose = () => {
            // Only reconnect if job is still active and we didn't intentionally disconnect
            if (self.activeJobId && self._ws && !self._isJobTerminal()) {
                self._ws = null;
                setTimeout(() => {
                    if (self.activeJobId && !self._isJobTerminal()) {
                        self.connectWebSocket(jobId);
                    }
                }, 3000);
            }
        };
        this._ws.onerror = () => {};
    }

    /** Fetch and swap console log entries. */
    _refreshConsole() {
        var el = document.getElementById('console-log-container');
        if (!el) return;
        var url = el.dataset.url;
        if (!url) return;
        fetch(url).then(r => r.text()).then(html => {
            el.innerHTML = html;
            el.scrollTop = el.scrollHeight;
            if (typeof applyConsoleFilter === 'function') applyConsoleFilter();
        }).catch(() => {});
    }

    /** Fetch and swap job history list. */
    _refreshJobsList() {
        var el = document.getElementById('jobs-list-container');
        if (!el) return;
        var url = el.dataset.url;
        if (!url) return;
        fetch(url).then(r => r.text()).then(html => {
            el.innerHTML = html;
        }).catch(() => {});
    }

    /** Close the WebSocket connection. */
    disconnectWebSocket() {
        if (this._ws) {
            const ws = this._ws;
            this._ws = null;
            ws.close();
        }
    }

    /** Load monitor partial and connect WebSocket for live updates. */
    onJobStarted(result) {
        const container = document.getElementById(this.monitorContainerId);
        if (!container) return;
        this._updateButtons(false);
        // Initial load
        this.refreshMonitor();
        this._refreshConsole();
        this._refreshJobsList();
        // Connect WebSocket — pushes monitor, console, and jobs updates
        this.connectWebSocket(result.id);
    }

    /** Show error in errors container. Override in template if needed. */
    onError(message) {
        const el = document.getElementById(this.errorsContainerId);
        if (el) {
            if (message) {
                el.classList.remove('hidden');
                const inner = el.querySelector('div');
                if (inner) inner.textContent = message;
            } else {
                el.classList.add('hidden');
                const inner = el.querySelector('div');
                if (inner) inner.textContent = '';
            }
        }
    }
}

if (typeof window !== 'undefined') {
    window.WorkbenchForm = WorkbenchForm;
}
