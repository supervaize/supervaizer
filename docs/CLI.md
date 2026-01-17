# SUPERVAIZER CLI

SUPERVAIZER includes a command-line interface to simplify setup, operation, and deployment:

```bash
# Install Supervaizer
pip install supervaizer

# For deployment features, install with deploy extras
pip install supervaizer[deploy]

# Get Help
supervaizer --help

# Create a supervaizer_control.py file in your current directory
supervaizer scaffold

# Start the server using the configuration file
supervaizer start

# Deploy to cloud platforms
supervaizer deploy --help
```

## CLI Commands

### scaffold

Creates a starter configuration file (supervaizer_control.py)

```bash
# Basic usage (creates supervaizer_control.py in current directory)
supervaizer scaffold

# Specify a custom output path
supervaizer scaffold --output-path=my_config.py

# Force overwrite if file already exists
supervaizer scaffold --force
```

### start

Starts the Supervaizer server

```bash
# Basic usage (loads supervaizer_control.py from current directory)
supervaizer start

# Specify a custom configuration file
supervaizer start my_config.py

# Configure server options
supervaizer start --host=0.0.0.0 --port=8080 --environment=production

# Enable debug mode and auto-reload
supervaizer start --debug --reload

# Set log level
supervaizer start --log-level=DEBUG
```

### deploy

Automated deployment to cloud platforms. Requires installation with deploy extras: `pip install supervaizer[deploy]`

#### deploy local

Test your deployment locally using Docker and docker-compose

```bash
# Basic local testing
supervaizer deploy local

# With generated secrets
supervaizer deploy local --generate-api-key --generate-rsa

# Custom port
supervaizer deploy local --port 8080

# With verbose output
supervaizer deploy local --verbose
```

**Options:**
- `--name TEXT` - Service name (default: current directory name)
- `--env [dev|staging|prod]` - Environment (default: dev)
- `--port INTEGER` - Local port to expose (default: 8000)
- `--generate-api-key` - Generate secure API key
- `--generate-rsa` - Generate RSA private key
- `--timeout INTEGER` - Service startup timeout in seconds (default: 300)
- `--verbose` - Show detailed output

#### deploy plan

Preview deployment actions before applying changes

```bash
# Plan deployment to Google Cloud Run
supervaizer deploy plan --platform cloud-run --region us-central1

# Plan deployment to AWS App Runner
supervaizer deploy plan --platform aws-app-runner --region us-east-1

# Plan deployment to DigitalOcean
supervaizer deploy plan --platform do-app-platform --region nyc
```

**Options:**
- `--platform [cloud-run|aws-app-runner|do-app-platform]` - Cloud platform (required)
- `--name TEXT` - Service name (default: current directory name)
- `--env [dev|staging|prod]` - Environment (default: dev)
- `--region TEXT` - Cloud provider region
- `--project-id TEXT` - GCP project / AWS account / DO project ID
- `--verbose` - Show detailed output

#### deploy up

Deploy to cloud platform with automated build, push, and verification

```bash
# Deploy to Google Cloud Run
supervaizer deploy up --platform cloud-run --region us-central1

# Deploy to AWS App Runner
supervaizer deploy up --platform aws-app-runner --region us-east-1

# Deploy to DigitalOcean App Platform
supervaizer deploy up --platform do-app-platform --region nyc

# Deploy with generated secrets
supervaizer deploy up --platform cloud-run --region us-central1 \
  --generate-api-key --generate-rsa

# Non-interactive deployment
supervaizer deploy up --platform cloud-run --region us-central1 --yes
```

**Options:**
- `--platform [cloud-run|aws-app-runner|do-app-platform]` - Cloud platform (required)
- `--name TEXT` - Service name (default: current directory name)
- `--env [dev|staging|prod]` - Environment (default: dev)
- `--region TEXT` - Cloud provider region (required)
- `--project-id TEXT` - GCP project / AWS account / DO project ID
- `--image TEXT` - Container image (default: auto-generated from git SHA)
- `--port INTEGER` - Container port (default: 8000)
- `--generate-api-key` - Generate secure API key
- `--generate-rsa` - Generate RSA private key
- `--rsa-key-path PATH` - Path to existing RSA private key PEM file
- `--yes` - Non-interactive mode (skip confirmations)
- `--no-rollback` - Keep failed revision (don't rollback on failure)
- `--timeout INTEGER` - Deployment timeout in seconds
- `--verbose` - Show detailed output

#### deploy down

Tear down deployment and clean up resources

```bash
# Remove deployment from Google Cloud Run
supervaizer deploy down --platform cloud-run

# Remove deployment from AWS App Runner
supervaizer deploy down --platform aws-app-runner

# Non-interactive removal
supervaizer deploy down --platform cloud-run --yes
```

**Options:**
- `--platform [cloud-run|aws-app-runner|do-app-platform]` - Cloud platform (required)
- `--name TEXT` - Service name (default: current directory name)
- `--env [dev|staging|prod]` - Environment (default: dev)
- `--region TEXT` - Cloud provider region
- `--yes` - Non-interactive mode (skip confirmations)
- `--verbose` - Show detailed output

#### deploy status

Check deployment status and health

```bash
# Check status on Google Cloud Run
supervaizer deploy status --platform cloud-run

# Check status on AWS App Runner
supervaizer deploy status --platform aws-app-runner

# Verbose status with detailed information
supervaizer deploy status --platform cloud-run --verbose
```

**Options:**
- `--platform [cloud-run|aws-app-runner|do-app-platform]` - Cloud platform (required)
- `--name TEXT` - Service name (default: current directory name)
- `--env [dev|staging|prod]` - Environment (default: dev)
- `--region TEXT` - Cloud provider region
- `--verbose` - Show detailed output

#### deploy clean

Clean up deployment artifacts and state files

```bash
# Clean deployment artifacts
supervaizer deploy clean

# Clean with confirmation prompts
supervaizer deploy clean --verbose
```

**Options:**
- `--yes` - Non-interactive mode (skip confirmations)
- `--verbose` - Show detailed output

### Deployment Documentation

For detailed deployment documentation, see:
- [RFC-001: Cloud Deployment CLI](rfc/001-cloud-deployment-cli.md) - Complete specification
- [Local Testing Guide](LOCAL_TESTING.md) - Docker testing documentation

## Environment Variables

All CLI options can also be configured through environment variables:

### Server Configuration

| Environment Variable      | Description                      | Default Value                |
| ------------------------- | -------------------------------- | ---------------------------- |
| SUPERVAIZER_PUBLIC_URL    | Url used for inbound connections | defaults to scheme+host+port |
| SUPERVAIZER_HOST          | Host to bind the server to      | 0.0.0.0                      |
| SUPERVAIZER_PORT          | Port to bind the server to      | 8000                         |
| SUPERVAIZER_ENVIRONMENT   | Environment name                 | dev                          |
| SUPERVAIZER_LOG_LEVEL     | Log level (DEBUG, INFO, etc.)    | INFO                         |
| SUPERVAIZER_DEBUG         | Enable debug mode (true/false)   | false                        |
| SUPERVAIZER_RELOAD        | Enable auto-reload (true/false)  | false                        |
| SUPERVAIZER_SCRIPT_PATH   | Path to configuration script     | -                            |
| SUPERVAIZER_OUTPUT_PATH   | Path for install command output  | supervaizer_control.py       |
| SUPERVAIZER_FORCE_INSTALL | Force overwrite existing file    | false                        |

### Deployment Configuration

These environment variables are used during cloud deployment:

| Environment Variable           | Description                                    | Default Value |
| ------------------------------ | ---------------------------------------------- | ------------- |
| SUPERVAIZER_API_KEY            | API key for authentication                     | -             |
| SV_RSA_PRIVATE_KEY             | RSA private key (inline value)                 | -             |
| SV_RSA_PRIVATE_KEY_PATH        | Path to RSA private key PEM file               | -             |
| SV_LOG_LEVEL                   | Log level for deployed service                 | INFO          |
| SUPERVAIZE_API_KEY             | Supervaize platform API key                    | -             |
| SUPERVAIZE_WORKSPACE_ID        | Supervaize workspace identifier                | -             |
| SUPERVAIZE_API_URL             | Supervaize API endpoint URL                    | -             |

**Note:** Deployment secrets (API keys, RSA keys) are securely stored in cloud provider secret stores and not exposed in environment variables or logs.
