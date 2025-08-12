# Parameter Validation Guide

This document provides instructions for implementing parameter validation in the Supervaize web application to leverage the new parameter validation system.

## Overview

The Supervaizer now includes a comprehensive parameter validation system that:

- Validates job parameters before starting jobs
- Provides clean error messages for invalid parameters
- Prevents jobs from starting with incorrect parameters
- Supports both job fields and encrypted agent parameters

### Important Note: Parameter Types

There are two different types of parameters in the Supervaizer system:

1. **Agent Parameters** (`Parameter` class): These are configuration parameters for agents (like API keys, URLs, etc.) and are always stored as strings. The validation system ensures that these parameters are provided as strings.

2. **Job Fields** (`AgentMethod.fields`): These are the input fields for job execution and can have different types (str, int, bool, list, etc.). The validation system validates these against their expected types.

The parameter validation system now provides **separate endpoints** for each type of validation:

- **Agent Parameters**: Validated through `/validate-agent-parameters` endpoint
- **Method Fields**: Validated through `/validate-method-fields` endpoint

## New API Endpoints

### 1. Agent Parameters Validation Endpoint

**Endpoint**: `POST /{agent_path}/validate-agent-parameters`

**Purpose**: Validate agent configuration parameters (secrets, API keys, etc.) before starting a job.

**Request Body**:

```json
{
  "encrypted_agent_parameters": "encrypted_string_here"
}
```

**Response**:

```json
{
  "valid": true,
  "message": "Agent parameters validated successfully",
  "errors": [],
  "invalid_parameters": {}
}
```

**Error Response Example**:

```json
{
  "valid": false,
  "message": "Agent parameter validation failed",
  "errors": [
    "Required parameter 'API_KEY' is missing",
    "Parameter 'MAX_RETRIES' must be a string, got integer"
  ],
  "invalid_parameters": {
    "API_KEY": "Required parameter 'API_KEY' is missing",
    "MAX_RETRIES": "Parameter 'MAX_RETRIES' must be a string, got integer"
  }
}
```

### 2. Method Fields Validation Endpoint

**Endpoint**: `POST /{agent_path}/validate-method-fields`

**Purpose**: Validate job input fields against the method's field definitions before starting a job.

**Request Body**:

```json
{
  "method_name": "job_start",
  "job_fields": {
    "company_name": "Google",
    "max_results": 10,
    "subscribe_updates": true
  }
}
```

**Response**:

```json
{
  "valid": true,
  "message": "Method fields validated successfully",
  "errors": [],
  "invalid_fields": {}
}
```

**Error Response Example**:

```json
{
  "valid": false,
  "message": "Method field validation failed",
  "errors": [
    "Required field 'company_name' is missing",
    "Field 'max_results' must be an integer, got string"
  ],
  "invalid_fields": {
    "company_name": "Required field 'company_name' is missing",
    "max_results": "Field 'max_results' must be an integer, got string"
  }
}
```

### 4. Enhanced Job Start Endpoints

The existing job start endpoints now focus on job execution without redundant validation:

- `POST /{agent_path}/jobs` - Main job start endpoint
- `POST /{agent_path}/custom/{method_name}` - Custom method endpoints

These endpoints no longer perform validation, as it should be done separately using the dedicated validation endpoints.

## Implementation in Supervaize Web Application

### 1. Frontend Form Validation

Implement real-time parameter validation in job creation forms using the separate validation endpoints:

```javascript
// Example implementation for job start form with separate validation
class JobStartForm {
  constructor(agentPath) {
    this.agentPath = agentPath;
    this.form = document.getElementById("job-start-form");
    this.submitButton = document.getElementById("submit-button");
    this.errorContainer = document.getElementById("error-container");

    this.setupValidation();
  }

  setupValidation() {
    // Validate on form change
    this.form.addEventListener(
      "input",
      this.debounce(this.validateAllParameters.bind(this), 500)
    );

    // Validate before submit
    this.form.addEventListener("submit", this.handleSubmit.bind(this));
  }

  async validateAllParameters() {
    // Validate both agent parameters and method fields
    const [agentParamsValid, methodFieldsValid] = await Promise.all([
      this.validateAgentParameters(),
      this.validateMethodFields(),
    ]);

    if (agentParamsValid && methodFieldsValid) {
      this.clearErrors();
      this.enableSubmit();
    } else {
      this.disableSubmit();
    }
  }

  async validateAgentParameters() {
    const encryptedParams = this.getEncryptedParameters();
    if (!encryptedParams) {
      return true; // No agent parameters to validate
    }

    try {
      const response = await fetch(
        `/api/${this.agentPath}/validate-agent-parameters`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${this.getAuthToken()}`,
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
      console.error("Agent parameter validation error:", error);
      return false;
    }
  }

  async validateMethodFields() {
    const formData = this.getFormData();

    try {
      const response = await fetch(
        `/api/${this.agentPath}/validate-method-fields`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${this.getAuthToken()}`,
          },
          body: JSON.stringify({
            method_name: "job_start",
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
      console.error("Method field validation error:", error);
      return false;
    }
  }

  displayAgentParameterErrors(validationResult) {
    // Display agent parameter errors in a separate section
    const agentErrorSection = document.getElementById("agent-parameter-errors");
    if (agentErrorSection) {
      agentErrorSection.innerHTML = `
        <div class="alert alert-warning">
          <strong>Agent Configuration Issues:</strong> ${
            validationResult.message
          }
          <ul>
            ${validationResult.errors
              .map((error) => `<li>${error}</li>`)
              .join("")}
          </ul>
        </div>
      `;
    }
  }

  displayMethodFieldErrors(validationResult) {
    this.errorContainer.innerHTML = "";

    // Display general error message
    const errorMessage = document.createElement("div");
    errorMessage.className = "alert alert-danger";
    errorMessage.textContent = validationResult.message;
    this.errorContainer.appendChild(errorMessage);

    // Display specific field errors
    Object.entries(validationResult.invalid_fields).forEach(
      ([fieldName, errorMsg]) => {
        const field = this.form.querySelector(`[name="${fieldName}"]`);
        if (field) {
          // Add error class to field
          field.classList.add("is-invalid");

          // Create error message below field
          const fieldError = document.createElement("div");
          fieldError.className = "invalid-feedback";
          fieldError.textContent = errorMsg;
          field.parentNode.appendChild(fieldError);
        }
      }
    );
  }

  clearErrors() {
    this.errorContainer.innerHTML = "";

    // Clear agent parameter errors
    const agentErrorSection = document.getElementById("agent-parameter-errors");
    if (agentErrorSection) {
      agentErrorSection.innerHTML = "";
    }

    // Clear field errors
    this.form.querySelectorAll(".is-invalid").forEach((field) => {
      field.classList.remove("is-invalid");
    });
    this.form.querySelectorAll(".invalid-feedback").forEach((error) => {
      error.remove();
    });
  }

  enableSubmit() {
    this.submitButton.disabled = false;
    this.submitButton.textContent = "Start Job";
  }

  disableSubmit() {
    this.submitButton.disabled = true;
    this.submitButton.textContent = "Fix Errors First";
  }

  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  getFormData() {
    const formData = new FormData(this.form);
    const data = {};

    for (let [key, value] of formData.entries()) {
      // Handle different input types
      if (this.form.querySelector(`[name="${key}"]`).type === "checkbox") {
        data[key] = value === "on";
      } else if (this.form.querySelector(`[name="${key}"]`).type === "number") {
        data[key] = parseInt(value) || value;
      } else {
        data[key] = value;
      }
    }

    return {
      job_fields: data,
      encrypted_agent_parameters: this.getEncryptedParameters(),
    };
  }

  getEncryptedParameters() {
    // Implementation depends on how encrypted parameters are handled
    return null;
  }

  getAuthToken() {
    // Implementation depends on authentication system
    return localStorage.getItem("auth_token");
  }

  async handleSubmit(event) {
    event.preventDefault();

    // Final validation before submit
    await this.validateAllParameters();

    if (this.form.checkValidity()) {
      this.submitJob();
    }
  }

  async submitJob() {
    try {
      this.submitButton.disabled = true;
      this.submitButton.textContent = "Starting Job...";

      const formData = this.getFormData();
      const response = await fetch(`/api/${this.agentPath}/jobs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.getAuthToken()}`,
        },
        body: JSON.stringify(formData),
      });

      if (response.ok) {
        const job = await response.json();
        this.onJobStarted(job);
      } else {
        const error = await response.json();
        this.displayValidationErrors(error);
      }
    } catch (error) {
      console.error("Job start error:", error);
      this.displayError("Failed to start job. Please try again.");
    } finally {
      this.submitButton.disabled = false;
      this.submitButton.textContent = "Start Job";
    }
  }

  onJobStarted(job) {
    // Handle successful job start
    this.showSuccessMessage(`Job ${job.id} started successfully!`);
    this.form.reset();
    this.clearErrors();

    // Redirect to job status page or show job details
    window.location.href = `/jobs/${job.id}`;
  }

  showSuccessMessage(message) {
    // Implementation depends on UI framework
    alert(message); // Replace with proper notification system
  }

  displayError(message) {
    this.errorContainer.innerHTML = `
      <div class="alert alert-danger">
        ${message}
      </div>
    `;
  }
}

// Usage
document.addEventListener("DOMContentLoaded", () => {
  const agentPath = document.getElementById("job-start-form").dataset.agentPath;
  new JobStartForm(agentPath);
});
```

### 2. Backend Integration

Ensure your backend properly handles the validation responses using the separate endpoints:

```python
# Example backend integration (Python/FastAPI)
from fastapi import HTTPException
from typing import Dict, Any

async def start_job_with_validation(agent_path: str, job_data: Dict[str, Any]):
    """
    Start a job with separate parameter validation
    """
    # First validate agent parameters
    agent_params_valid = await validate_agent_parameters(agent_path, job_data)
    if not agent_params_valid.get("valid", False):
        raise HTTPException(
            status_code=400,
            detail={
                "valid": False,
                "message": "Agent parameter validation failed",
                "errors": agent_params_valid.get("errors", []),
                "invalid_parameters": agent_params_valid.get("invalid_parameters", {})
            }
        )

    # Then validate method fields
    method_fields_valid = await validate_method_fields(agent_path, job_data)
    if not method_fields_valid.get("valid", False):
        raise HTTPException(
            status_code=400,
            detail={
                "valid": False,
                "message": "Method field validation failed",
                "errors": method_fields_valid.get("errors", []),
                "invalid_fields": method_fields_valid.get("invalid_fields", {})
            }
        )

    # If both validations pass, start the job
    return await start_job(agent_path, job_data)

async def validate_agent_parameters(agent_path: str, job_data: Dict[str, Any]):
    """
    Call the Supervaizer agent parameter validation endpoint
    """
    # Implementation depends on your HTTP client
    # This is a pseudo-code example
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SUPERVAIZER_BASE_URL}/{agent_path}/validate-agent-parameters",
            json={
                "encrypted_agent_parameters": job_data.get("encrypted_agent_parameters")
            },
            headers={"Authorization": f"Bearer {SUPERVAIZER_API_KEY}"}
        )
        return response.json()

async def validate_method_fields(agent_path: str, job_data: Dict[str, Any]):
    """
    Call the Supervaizer method field validation endpoint
    """
    # Implementation depends on your HTTP client
    # This is a pseudo-code example
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SUPERVAIZER_BASE_URL}/{agent_path}/validate-method-fields",
            json={
                "method_name": job_data.get("method_name", "job_start"),
                "job_fields": job_data.get("job_fields", {})
            },
            headers={"Authorization": f"Bearer {SUPERVAIZER_API_KEY}"}
        )
        return response.json()


```

### 3. Error Handling

Implement proper error handling for validation failures:

```javascript
// Enhanced error handling
class ValidationErrorHandler {
  static handleValidationError(error, form) {
    if (
      error.status === 400 &&
      error.detail &&
      error.detail.invalid_parameters
    ) {
      // This is a validation error
      this.displayFieldErrors(error.detail.invalid_parameters, form);
      this.displayGeneralError(error.detail.message);
    } else {
      // This is a different type of error
      this.displayGeneralError(
        "An unexpected error occurred. Please try again."
      );
    }
  }

  static displayFieldErrors(invalidParameters, form) {
    Object.entries(invalidParameters).forEach(([fieldName, errorMessage]) => {
      const field = form.querySelector(`[name="${fieldName}"]`);
      if (field) {
        // Add error styling
        field.classList.add("is-invalid");

        // Remove existing error message
        const existingError =
          field.parentNode.querySelector(".invalid-feedback");
        if (existingError) {
          existingError.remove();
        }

        // Add new error message
        const errorDiv = document.createElement("div");
        errorDiv.className = "invalid-feedback";
        errorDiv.textContent = errorMessage;
        field.parentNode.appendChild(errorDiv);
      }
    });
  }

  static displayGeneralError(message) {
    // Display general error message (implementation depends on UI framework)
    console.error(message);
  }

  static clearFieldErrors(form) {
    form.querySelectorAll(".is-invalid").forEach((field) => {
      field.classList.remove("is-invalid");
    });

    form.querySelectorAll(".invalid-feedback").forEach((error) => {
      error.remove();
    });
  }
}
```

### 4. UI/UX Improvements

Consider these UI/UX improvements:

1. **Real-time Validation**: Validate parameters as users type (with debouncing)
2. **Inline Error Messages**: Show errors below or next to form fields
3. **Visual Feedback**: Use color coding and icons to indicate validation status
4. **Progressive Disclosure**: Show validation errors progressively as users interact with the form
5. **Help Text**: Provide examples and guidance for each parameter type

### 5. Testing

Test the validation system thoroughly using the separate endpoints:

```javascript
// Example test cases for separate validation endpoints
describe("Parameter Validation", () => {
  describe("Agent Parameters Validation", () => {
    test("should validate required agent parameters", async () => {
      const form = new JobStartForm("/test-agent");
      const result = await form.validateAgentParameters({
        encrypted_agent_parameters: "encrypted_string",
      });

      expect(result.valid).toBe(false);
      expect(result.errors).toContain(
        "Required parameter 'API_KEY' is missing"
      );
    });

    test("should validate agent parameter types", async () => {
      const form = new JobStartForm("/test-agent");
      const result = await form.validateAgentParameters({
        encrypted_agent_parameters: "encrypted_string",
      });

      expect(result.valid).toBe(false);
      expect(result.invalid_parameters.MAX_RETRIES).toContain(
        "must be a string"
      );
    });

    test("should accept valid agent parameters", async () => {
      const form = new JobStartForm("/test-agent");
      const result = await form.validateAgentParameters({
        encrypted_agent_parameters: "encrypted_string",
      });

      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });
  });

  describe("Method Fields Validation", () => {
    test("should validate required method fields", async () => {
      const form = new JobStartForm("/test-agent");
      const result = await form.validateMethodFields({
        method_name: "job_start",
        job_fields: {},
      });

      expect(result.valid).toBe(false);
      expect(result.errors).toContain(
        "Required field 'company_name' is missing"
      );
    });

    test("should validate method field types", async () => {
      const form = new JobStartForm("/test-agent");
      const result = await form.validateMethodFields({
        method_name: "job_start",
        job_fields: {
          company_name: 123, // Should be string
          max_results: "not_a_number", // Should be integer
        },
      });

      expect(result.valid).toBe(false);
      expect(result.invalid_fields.company_name).toContain("must be a string");
      expect(result.invalid_fields.max_results).toContain("must be an integer");
    });

    test("should accept valid method fields", async () => {
      const form = new JobStartForm("/test-agent");
      const result = await form.validateMethodFields({
        method_name: "job_start",
        job_fields: {
          company_name: "Google",
          max_results: 10,
        },
      });

      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });
  });
});
```

## Migration Guide

### For Existing Applications

1. **Update API Calls**: Ensure your job start API calls handle the new 400 responses for validation errors
2. **Add Validation Endpoints**: Implement the new separate validation endpoints in your routing:
   - `/validate-agent-parameters` for agent configuration validation
   - `/validate-method-fields` for job input validation
3. **Update Error Handling**: Modify error handling to display validation errors appropriately for each type
4. **Test Thoroughly**: Test with various parameter combinations to ensure validation works correctly

### Breaking Changes

- Job start endpoints no longer perform validation (removed redundant validation code)
- New separate validation endpoints are required for optimal user experience
- Error response format has changed to include structured validation information
- Legacy `/validate-parameters` endpoint has been removed for cleaner architecture

### Recommended Migration Path

1. **Phase 1**: Implement the new separate validation endpoints
2. **Phase 2**: Update frontend to use separate validation for better user experience
3. **Phase 3**: Clean up any remaining references to the old validation approach

## Benefits

1. **Better User Experience**: Users get immediate feedback about parameter issues with clear separation of concerns
2. **Reduced Job Failures**: Jobs won't start with invalid parameters
3. **Clearer Error Messages**: Specific error messages help users fix issues quickly
4. **Improved Debugging**: Developers can easily identify parameter problems by type
5. **Consistent Validation**: Centralized validation logic across all endpoints
6. **Separation of Concerns**: Agent configuration validation vs. job input validation are now distinct operations
7. **Code Maintainability**: Eliminated redundant validation code and improved code organization
8. **Flexible Validation**: Can validate agent parameters and method fields independently or together

## Support

For questions or issues with the parameter validation system, please refer to:

- API documentation
- Test cases in the codebase
- GitHub issues for known problems
- Community discussions for implementation help
