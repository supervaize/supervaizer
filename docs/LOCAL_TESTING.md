# Local Docker Testing

This document describes how to test Supervaizer deployments locally using Docker before deploying to cloud platforms.

## Overview

The local testing functionality allows you to:

- Build and test Docker images locally
- Run services using Docker Compose
- Perform health checks and validation
- Test API endpoints and documentation
- Validate environment configuration

## Quick Start

### 1. Basic Local Test

```bash
# Test with default settings
supervaizer deploy local

# Test with custom port and generated secrets
supervaizer deploy local --port 8080 --generate-api-key --generate-rsa
```

### 2. Using the Test Script

```bash
# Make the script executable
chmod +x test_local.py

# Run the test script
./test_local.py
```

## Command Options

The `supervaizer deploy local` command supports the following options:

| Option               | Description                       | Default                |
| -------------------- | --------------------------------- | ---------------------- |
| `--name`             | Service name                      | Current directory name |
| `--env`              | Environment (dev/staging/prod)    | dev                    |
| `--port`             | Local port to expose              | 8000                   |
| `--generate-api-key` | Generate secure API key           | false                  |
| `--generate-rsa`     | Generate RSA private key          | false                  |
| `--timeout`          | Service startup timeout (seconds) | 300                    |
| `--verbose`          | Show detailed output              | false                  |

## What It Does

### 1. Pre-flight Checks

- ✅ Verifies Docker is running
- ✅ Checks Docker Compose availability
- ✅ Validates project structure

### 2. File Generation

- ✅ Generates `Dockerfile` in `.deployment/`
- ✅ Creates `.dockerignore` file
- ✅ Generates `docker-compose.yml` for local testing

### 3. Secret Management

- ✅ Generates test API keys (if requested)
- ✅ Creates RSA keys (if requested)
- ✅ Sets up environment variables

### 4. Environment Variables

The local testing automatically includes environment variables from your host environment:

- **SUPERVAIZE_API_KEY**: Your Supervaize API key
- **SUPERVAIZE_WORKSPACE_ID**: Your workspace identifier
- **SUPERVAIZE_API_URL**: Supervaize API endpoint URL
- **SUPERVAIZER_PUBLIC_URL**: Public URL for your service

These variables are securely passed as build arguments to the Docker image and are not stored in the image layers.

### 5. Docker Operations

- ✅ Builds Docker image with local tag
- ✅ Starts services using Docker Compose
- ✅ Waits for service to be ready

### 6. Health Validation

- ✅ Tests `/.well-known/health` endpoint
- ✅ Validates API health endpoint (with API key)
- ✅ Checks API documentation availability
- ✅ Measures response times

### 7. Service Information

- ✅ Displays service URL and port
- ✅ Shows API documentation links
- ✅ Reports health check results
- ✅ Provides cleanup instructions

## Generated Files

The local command creates the following files in `.deployment/`:

```
.deployment/
├── Dockerfile              # Docker image definition
├── .dockerignore          # Docker ignore rules
├── docker-compose.yml     # Local testing configuration
└── logs/                  # Deployment logs (if any)
```

## Example Output

```
🐳 Local Docker Testing
═══════════════════════════════════════════════════════════

Testing service: my-agent-dev
Environment: dev
Port: 8000

Step 1: Checking Docker availability...
✓ Docker is available

Step 2: Generating deployment files...
✓ Deployment files generated

Step 3: Setting up secrets...
✓ Test secrets configured

Step 4: Building Docker image...
✓ Image built: my-agent-dev:local-test

Step 5: Starting services...
✓ Services started

Step 6: Waiting for service to be ready...
✓ Service is ready

Step 7: Running health checks...
┌─────────────────────┬────────┬───────────────┬─────────┐
│ Endpoint            │ Status │ Response Time │ Details │
├─────────────────────┼────────┼───────────────┼─────────┤
│ Health Endpoint     │ 200    │ 0.123s        │ ✓ OK    │
│ Api Health Endpoint │ 200    │ 0.156s        │ ✓ OK    │
│ Api Docs            │ 200    │ 0.089s        │ ✓ OK    │
└─────────────────────┴────────┴───────────────┴─────────┘

Step 8: Service Information
┌─────────────────┬─────────────────────────────┐
│ Property        │ Value                       │
├─────────────────┼─────────────────────────────┤
│ Service Name    │ my-agent-dev                 │
│ URL             │ http://localhost:8000       │
│ Port            │ 8000                         │
│ API Key         │ test-api-...                │
│ Environment     │ dev                          │
└─────────────────┴─────────────────────────────┘

✓ Local testing completed successfully!

Service URL: http://localhost:8000
API Documentation: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc

To stop the test services:
docker-compose -f .deployment/docker-compose.yml down

To debug environment variables:
docker-compose -f .deployment/docker-compose.yml run --rm <service-name> python debug_env.py

To clean up all deployment files:
supervaizer deploy clean
```

## Troubleshooting

### Common Issues

#### Environment Variable Issues

```
❌ ValidationError: workspace_id, api_key, api_url are None
```

**Solution**: Check if environment variables are properly set:

1. **Debug environment variables**:

   ```bash
   docker-compose -f .deployment/docker-compose.yml run --rm <service-name> python debug_env.py
   ```

2. **Set required environment variables**:

   ```bash
   export SUPERVAIZE_API_KEY="your-api-key"
   export SUPERVAIZE_WORKSPACE_ID="your-workspace-id"
   export SUPERVAIZE_API_URL="https://api.supervaize.com"
   export SUPERVAIZER_PUBLIC_URL="https://your-app.com"
   ```

3. **Regenerate deployment files**:

   ```bash
   supervaizer deploy local --docker-files-only
   ```

4. **Check generated docker-compose.yml**:
   ```bash
   cat .deployment/docker-compose.yml
   ```

#### Docker Not Available

```
❌ Error: Docker is not available or not running
```

**Solution**: Install Docker and ensure it's running:

```bash
# macOS with Homebrew
brew install docker

# Start Docker Desktop
open -a Docker
```

#### Port Already in Use

```
❌ Error: Port 8000 is already in use
```

**Solution**: Use a different port:

```bash
supervaizer deploy local --port 8080
```

#### Service Startup Timeout

```
❌ Error: Service failed to start within timeout
```

**Solution**:

1. Check service logs:
   ```bash
   docker-compose -f .deployment/docker-compose.yml logs
   ```
2. Increase timeout:
   ```bash
   supervaizer deploy local --timeout 600
   ```

#### Missing supervaizer_control.py

```
❌ Error: supervaizer_control.py not found
```

**Solution**: Ensure you're running from a Supervaizer project directory with a valid control file.

### Debug Mode

Use `--verbose` flag for detailed output:

```bash
supervaizer deploy local --verbose
```

This will show:

- Docker build logs
- Docker Compose output
- Detailed error messages

## Cleanup

### Stop Services

```bash
docker-compose -f .deployment/docker-compose.yml down
```

### Remove Images

```bash
docker rmi my-agent-dev:local-test
```

### Clean Everything

```bash
docker-compose -f .deployment/docker-compose.yml down --volumes --rmi all
```

## Integration with CI/CD

The local testing can be integrated into CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Test Local Deployment
  run: |
    supervaizer deploy local --generate-api-key --timeout 300
    docker-compose -f .deployment/docker-compose.yml down
```

## Best Practices

1. **Always test locally** before deploying to cloud platforms
2. **Use generated secrets** for testing (`--generate-api-key --generate-rsa`)
3. **Check health endpoints** to ensure service is working correctly
4. **Clean up resources** after testing to avoid port conflicts
5. **Use verbose mode** when debugging issues
6. **Test with different ports** if default port is in use

## Next Steps

After successful local testing:

1. Deploy to cloud platform: `supervaizer deploy up --platform cloud-run`
2. Check deployment status: `supervaizer deploy status --platform cloud-run`
3. Monitor service health and logs
4. Clean up when done: `supervaizer deploy down --platform cloud-run`
