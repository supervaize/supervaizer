/**
 * WorkbenchForm — handles parameter + field collection and job start from workbench.
 */
class WorkbenchForm {
    constructor(agentSlug) {
        this.agentSlug = agentSlug;
        this.basePath = `/admin/agents/${agentSlug}/workbench`;
        this.activeJobId = null;
    }

    getApiKey() {
        return sessionStorage.getItem('admin_api_key') || '';
    }

    collectParameters() {
        const params = {};
        document.querySelectorAll('#parameters-form input, #parameters-form select').forEach(el => {
            if (el.name) {
                params[el.name] = el.type === 'checkbox' ? el.checked : el.value;
            }
        });
        return params;
    }

    collectFields() {
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
        document.querySelectorAll('#parameters-form [required], #fields-form [required]').forEach(el => {
            if (!el.value) {
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
            return;
        }

        const parameters = this.collectParameters();
        const fields = this.collectFields();

        try {
            const response = await fetch(`${this.basePath}/start`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': this.getApiKey(),
                },
                body: JSON.stringify({ parameters, fields }),
            });

            const result = await response.json();
            if (response.ok) {
                this.activeJobId = result.id;
                this.onJobStarted(result);
            } else {
                this.onError(result.detail || 'Failed to start job');
            }
        } catch (e) {
            this.onError(`Network error: ${e.message}`);
        }
    }

    async stopJob() {
        if (!this.activeJobId) return;

        try {
            const response = await fetch(`${this.basePath}/jobs/${this.activeJobId}/stop`, {
                method: 'POST',
                headers: { 'X-API-Key': this.getApiKey() },
            });
            const result = await response.json();
            if (!response.ok) {
                this.onError(result.detail || 'Failed to stop job');
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
            }
        } catch (e) {
            this.onError(`Network error: ${e.message}`);
        }
    }

    // Override these in the template
    onJobStarted(result) {}
    onError(message) {}
}

if (typeof window !== 'undefined') {
    window.WorkbenchForm = WorkbenchForm;
}
