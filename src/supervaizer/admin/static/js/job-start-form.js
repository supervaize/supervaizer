/**
 * JobStartForm - Handles job parameter validation and submission
 *
 * This class provides methods to validate agent parameters and method fields
 * before starting a job, using the new validation endpoints.
 */

class JobStartForm {
    constructor(agentPath) {
        this.agentPath = agentPath;
        this.form = null;
        this.errorContainer = null;
        this.initialize();
    }

    initialize() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupForm());
        } else {
            this.setupForm();
        }
    }

    setupForm() {
        // Find the form and error container
        this.form = document.querySelector('form[data-job-start]');
        this.errorContainer = document.getElementById('validation-errors');

        if (!this.form) {
            console.warn('JobStartForm: No form found with data-job-start attribute');
            return;
        }

        if (!this.errorContainer) {
            console.warn('JobStartForm: No validation-errors container found');
            return;
        }

        // Add submit handler
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));

        // Add validation on field change
        this.form.addEventListener('change', () => this.clearErrors());

        console.log('JobStartForm initialized for', this.agentPath);
    }

    async handleSubmit(event) {
        event.preventDefault();

        // Clear previous errors
        this.clearErrors();

        // Validate both agent parameters and method fields
        const [agentParamsValid, methodFieldsValid] = await Promise.all([
            this.validateAgentParameters(),
            this.validateMethodFields()
        ]);

        if (agentParamsValid && methodFieldsValid) {
            // All validation passed, submit the form
            this.submitForm();
        }
    }

    async validateAgentParameters() {
        const encryptedParams = this.getEncryptedAgentParameters();

        if (!encryptedParams) {
            return true; // No agent parameters to validate
        }

        try {
            const response = await fetch(
                `${this.agentPath}/validate-agent-parameters`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': this.getApiKey()
                    },
                    body: JSON.stringify({
                        encrypted_agent_parameters: encryptedParams,
                    }),
                }
            );

            const result = await response.json();

            if (!result.valid) {
                this.displayAgentParameterErrors(result);
                return false;
            }

            return true;
        } catch (error) {
            console.error('Agent parameter validation failed:', error);
            this.displayError('Agent parameter validation failed due to network error');
            return false;
        }
    }

    async validateMethodFields() {
        const formData = this.getFormData();

        try {
            const response = await fetch(
                `${this.agentPath}/validate-method-fields`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': this.getApiKey()
                    },
                    body: JSON.stringify({
                        method_name: 'job_start',
                        job_fields: formData,
                    }),
                }
            );

            const result = await response.json();

            if (!result.valid) {
                this.displayMethodFieldErrors(result);
                return false;
            }

            return true;
        } catch (error) {
            console.error('Method field validation failed:', error);
            this.displayError('Method field validation failed due to network error');
            return false;
        }
    }

    getFormData() {
        const formData = {};
        const formElements = this.form.elements;

        for (let element of formElements) {
            if (element.name && element.type !== 'submit') {
                if (element.type === 'checkbox') {
                    formData[element.name] = element.checked;
                } else if (element.type === 'radio') {
                    if (element.checked) {
                        formData[element.name] = element.value;
                    }
                } else if (element.type === 'select-multiple') {
                    formData[element.name] = Array.from(element.selectedOptions).map(option => option.value);
                } else {
                    formData[element.name] = element.value;
                }
            }
        }

        return formData;
    }

    getEncryptedAgentParameters() {
        // Look for encrypted agent parameters in hidden fields or data attributes
        const encryptedField = this.form.querySelector('[name="encrypted_agent_parameters"]');
        if (encryptedField) {
            return encryptedField.value;
        }

        // Check if agent parameters are stored in data attributes
        const agentParamsData = this.form.dataset.agentParameters;
        if (agentParamsData) {
            try {
                return JSON.parse(agentParamsData);
            } catch (e) {
                console.warn('Failed to parse agent parameters from data attribute');
            }
        }

        return null;
    }

    getApiKey() {
        // Get API key from form data, meta tag, or global variable
        const apiKeyField = this.form.querySelector('[name="api_key"]');
        if (apiKeyField) {
            return apiKeyField.value;
        }

        const metaApiKey = document.querySelector('meta[name="api-key"]');
        if (metaApiKey) {
            return metaApiKey.content;
        }

        // Check for global variable
        if (typeof window.SUPERVAIZER_API_KEY !== 'undefined') {
            return window.SUPERVAIZER_API_KEY;
        }

        return '';
    }

    displayAgentParameterErrors(validationResult) {
        const errorSection = document.getElementById('agent-parameter-errors');
        if (!errorSection) {
            // Create error section if it doesn't exist
            const section = document.createElement('div');
            section.id = 'agent-parameter-errors';
            section.className = 'mb-4';
            this.errorContainer.appendChild(section);
        }

        const section = document.getElementById('agent-parameter-errors');
        section.innerHTML = `
            <div class="alert alert-warning">
                <strong>Agent Configuration Issues:</strong> ${validationResult.message
            }
                <ul>
                    ${validationResult.errors
                .map((error) => `<li>${error}</li>`)
                .join('')}
                </ul>
            </div>
        `;
    }

    displayMethodFieldErrors(validationResult) {
        // Clear any existing field-specific errors
        this.form.querySelectorAll('.is-invalid').forEach((field) => {
            field.classList.remove('is-invalid');
        });

        // Display general error message
        this.displayError(validationResult.message);

        // Mark invalid fields and show specific error messages
        Object.entries(validationResult.invalid_fields).forEach(([fieldName, errorMessage]) => {
            const field = this.form.querySelector(`[name="${fieldName}"]`);
            if (field) {
                field.classList.add('is-invalid');

                // Add error message below the field
                let errorElement = field.parentNode.querySelector('.invalid-feedback');
                if (!errorElement) {
                    errorElement = document.createElement('div');
                    errorElement.className = 'invalid-feedback';
                    field.parentNode.appendChild(errorElement);
                }
                errorElement.textContent = errorMessage;
            }
        });
    }

    displayError(message) {
        this.errorContainer.innerHTML = `
            <div class="alert alert-danger">
                <strong>Validation Error:</strong> ${message}
            </div>
        `;
    }

    clearErrors() {
        this.errorContainer.innerHTML = '';

        // Clear agent parameter errors
        const agentErrorSection = document.getElementById('agent-parameter-errors');
        if (agentErrorSection) {
            agentErrorSection.innerHTML = '';
        }

        // Clear field errors
        this.form.querySelectorAll('.is-invalid').forEach((field) => {
            field.classList.remove('is-invalid');
        });

        // Clear invalid feedback messages
        this.form.querySelectorAll('.invalid-feedback').forEach((feedback) => {
            feedback.remove();
        });
    }

    async submitForm() {
        try {
            const formData = this.getFormData();
            const encryptedParams = this.getEncryptedAgentParameters();

            const requestBody = {
                job_context: {
                    // Add any job context data here
                },
                job_fields: formData
            };

            if (encryptedParams) {
                requestBody.encrypted_agent_parameters = encryptedParams;
            }

            const response = await fetch(`${this.agentPath}/jobs`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': this.getApiKey()
                },
                body: JSON.stringify(requestBody)
            });

            if (response.ok) {
                const result = await response.json();
                this.handleJobStarted(result);
            } else {
                const error = await response.json();
                this.handleJobError(error);
            }
        } catch (error) {
            console.error('Job submission failed:', error);
            this.displayError('Failed to submit job due to network error');
        }
    }

    handleJobStarted(jobData) {
        // Clear form and show success message
        this.form.reset();
        this.clearErrors();

        this.errorContainer.innerHTML = `
            <div class="alert alert-success">
                <strong>Job Started Successfully!</strong><br>
                Job ID: ${jobData.id || 'Unknown'}<br>
                Status: ${jobData.status || 'Unknown'}
            </div>
        `;

        // Trigger any success callbacks
        if (typeof this.onJobStarted === 'function') {
            this.onJobStarted(jobData);
        }
    }

    handleJobError(error) {
        this.displayError(`Job submission failed: ${error.detail || error.message || 'Unknown error'}`);

        // Trigger any error callbacks
        if (typeof this.onJobError === 'function') {
            this.onJobError(error);
        }
    }

    // Public methods for external use
    setOnJobStarted(callback) {
        this.onJobStarted = callback;
    }

    setOnJobError(callback) {
        this.onJobError = callback;
    }

    // Method to manually trigger validation
    async validate() {
        const [agentParamsValid, methodFieldsValid] = await Promise.all([
            this.validateAgentParameters(),
            this.validateMethodFields()
        ]);
        return agentParamsValid && methodFieldsValid;
    }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = JobStartForm;
}

// Make available globally
if (typeof window !== 'undefined') {
    window.JobStartForm = JobStartForm;
}
