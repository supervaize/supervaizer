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
        this._pollInterval = null;
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
            if (el.type === 'checkbox' ? !value : value === '') {
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

        try {
            const response = await fetch(
                `${this.basePath}/jobs/${this.activeJobId}/cases/${caseId}/answer`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': this.getApiKey(),
                    },
                    body: JSON.stringify({ answer }),
                },
            );
            const result = await response.json();
            if (!response.ok) {
                this.onError(result.detail || result.message || 'Failed to submit answer');
            } else {
                // Remove the form so polling resumes, then refresh immediately
                formElement.remove();
                this.refreshMonitor();
            }
        } catch (e) {
            this.onError(`Network error: ${e.message}`);
        }
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

    /** Fetch and render the monitor partial for the active job. */
    refreshMonitor() {
        if (!this.activeJobId) return;
        const container = document.getElementById(this.monitorContainerId);
        if (!container) return;
        const url = `${this.basePath}/jobs/${this.activeJobId}`;
        const apiKey = this.getApiKey();
        const headers = apiKey ? { 'X-API-Key': apiKey } : {};
        fetch(url, { headers })
            .then(r => r.text())
            .then(html => {
                container.innerHTML = html;
                if (typeof Alpine !== 'undefined') {
                    Alpine.initTree(container);
                }
            })
            .catch(() => {});
    }

    /** Load monitor partial and start polling. Stops when job reaches terminal state. */
    onJobStarted(result) {
        const container = document.getElementById(this.monitorContainerId);
        if (!container) return;
        const url = `${this.basePath}/jobs/${result.id}`;
        const apiKey = this.getApiKey();
        const self = this;
        this._updateButtons(false);
        const loadMonitor = () => {
            // Don't overwrite the monitor while user is filling a HITL form
            if (container.querySelector('form[id^="hitl-form-"]')) return;

            const headers = apiKey ? { 'X-API-Key': apiKey } : {};
            fetch(url, { headers })
                .then(r => r.text())
                .then(html => {
                    container.innerHTML = html;
                    // Re-initialize Alpine on swapped content
                    if (typeof Alpine !== 'undefined') {
                        Alpine.initTree(container);
                    }
                    // Stop polling once job is terminal
                    const partial = container.querySelector('#workbench-monitor-partial');
                    if (partial && partial.dataset.jobTerminal === 'true') {
                        if (self._pollInterval) {
                            clearInterval(self._pollInterval);
                            self._pollInterval = null;
                        }
                        self._updateButtons(true);
                    }
                })
                .catch(() => {});
        };
        loadMonitor();
        if (this._pollInterval) clearInterval(this._pollInterval);
        this._pollInterval = setInterval(loadMonitor, 2000);
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
