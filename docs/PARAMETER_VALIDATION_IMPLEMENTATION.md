# Parameter Validation Implementation Guide

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

The parameter validation system primarily validates **agent parameters** to ensure they are provided as strings, while **job field validation** is handled separately in the job creation process.

## New API Endpoints

### 1. Parameter Validation Endpoint

**Endpoint**: `POST /{agent_path}/validate-parameters`

**Purpose**: Validate job parameters before starting a job to provide immediate feedback to users.

**Request Body**:

```json
{
  "job_fields": {
    "company_name": "Google",
    "max_results": 10,
    "subscribe_updates": true
  },
  "encrypted_agent_parameters": "encrypted_string_here"
}
```

**Response**:

```json
{
  "valid": true,
  "message": "Parameters validated successfully",
  "errors": [],
  "invalid_parameters": {}
}
```

**Error Response Example**:

```json
{
  "valid": false,
  "message": "Parameter validation failed",
  "errors": [
    "Parameter 'company_name' must be a string, got integer",
    "Parameter 'max_results' must be an integer, got string"
  ],
  "invalid_parameters": {
    "company_name": "Parameter 'company_name' must be a string, got integer",
    "max_results": "Parameter 'max_results' must be an integer, got string"
  }
}
```

### 2. Enhanced Job Start Endpoints

The existing job start endpoints now include parameter validation:

- `POST /{agent_path}/jobs` - Main job start endpoint
- `POST /{agent_path}/custom/{method_name}` - Custom method endpoints

These endpoints now return HTTP 400 with validation errors instead of failing during job execution.

## Implementation in Supervaize Web Application

### 1. Frontend Form Validation

Implement real-time parameter validation in job creation forms:

```javascript
// Example implementation for job start form
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
      this.debounce(this.validateParameters.bind(this), 500)
    );

    // Validate before submit
    this.form.addEventListener("submit", this.handleSubmit.bind(this));
  }

  async validateParameters() {
    const formData = this.getFormData();

    try {
      const response = await fetch(
        `/api/${this.agentPath}/validate-parameters`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${this.getAuthToken()}`,
          },
          body: JSON.stringify(formData),
        }
      );

      const result = await response.json();

      if (result.valid) {
        this.clearErrors();
        this.enableSubmit();
      } else {
        this.displayValidationErrors(result);
        this.disableSubmit();
      }
    } catch (error) {
      console.error("Validation error:", error);
    }
  }

  displayValidationErrors(validationResult) {
    this.errorContainer.innerHTML = "";

    // Display general error message
    const errorMessage = document.createElement("div");
    errorMessage.className = "alert alert-danger";
    errorMessage.textContent = validationResult.message;
    this.errorContainer.appendChild(errorMessage);

    // Display specific field errors
    Object.entries(validationResult.invalid_parameters).forEach(
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
    await this.validateParameters();

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

Ensure your backend properly handles the validation responses:

```python
# Example backend integration (Python/FastAPI)
from fastapi import HTTPException
from typing import Dict, Any

async def start_job_with_validation(agent_path: str, job_data: Dict[str, Any]):
    """
    Start a job with parameter validation
    """
    # First validate parameters
    validation_response = await validate_job_parameters(agent_path, job_data)

    if not validation_response.get("valid", False):
        # Return validation errors
        raise HTTPException(
            status_code=400,
            detail={
                "valid": False,
                "message": "Parameter validation failed",
                "errors": validation_response.get("errors", []),
                "invalid_parameters": validation_response.get("invalid_parameters", {})
            }
        )

    # If validation passes, start the job
    return await start_job(agent_path, job_data)

async def validate_job_parameters(agent_path: str, job_data: Dict[str, Any]):
    """
    Call the Supervaizer validation endpoint
    """
    # Implementation depends on your HTTP client
    # This is a pseudo-code example
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{SUPERVAIZER_BASE_URL}/{agent_path}/validate-parameters",
            json=job_data,
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

Test the validation system thoroughly:

```javascript
// Example test cases
describe("Parameter Validation", () => {
  test("should validate required parameters", async () => {
    const form = new JobStartForm("/test-agent");
    const result = await form.validateParameters({
      job_fields: {},
      encrypted_agent_parameters: null,
    });

    expect(result.valid).toBe(false);
    expect(result.errors).toContain(
      "Required parameter 'company_name' is missing"
    );
  });

  test("should validate parameter types", async () => {
    const form = new JobStartForm("/test-agent");
    const result = await form.validateParameters({
      job_fields: {
        company_name: 123, // Should be string
        max_results: "not_a_number", // Should be integer
      },
      encrypted_agent_parameters: null,
    });

    expect(result.valid).toBe(false);
    expect(result.invalid_parameters.company_name).toContain(
      "must be a string"
    );
    expect(result.invalid_parameters.max_results).toContain(
      "must be an integer"
    );
  });

  test("should accept valid parameters", async () => {
    const form = new JobStartForm("/test-agent");
    const result = await form.validateParameters({
      job_fields: {
        company_name: "Google",
        max_results: 10,
      },
      encrypted_agent_parameters: null,
    });

    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });
});
```

## Migration Guide

### For Existing Applications

1. **Update API Calls**: Ensure your job start API calls handle the new 400 responses for validation errors
2. **Add Validation Endpoint**: Implement the new validation endpoint in your routing
3. **Update Error Handling**: Modify error handling to display validation errors appropriately
4. **Test Thoroughly**: Test with various parameter combinations to ensure validation works correctly

### Breaking Changes

- Job start endpoints now return HTTP 400 instead of 500 for parameter validation failures
- Error response format has changed to include structured validation information
- New validation endpoint is required for optimal user experience

## Benefits

1. **Better User Experience**: Users get immediate feedback about parameter issues
2. **Reduced Job Failures**: Jobs won't start with invalid parameters
3. **Clearer Error Messages**: Specific error messages help users fix issues quickly
4. **Improved Debugging**: Developers can easily identify parameter problems
5. **Consistent Validation**: Centralized validation logic across all endpoints

## Support

For questions or issues with the parameter validation system, please refer to:

- API documentation
- Test cases in the codebase
- GitHub issues for known problems
- Community discussions for implementation help
