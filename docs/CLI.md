# SUPERVAIZER CLI

SUPERVAIZER includes a command-line interface to simplify setup and operation:

```bash
# Install Supervaizer
pip install supervaizer

# Get Help
supervaizer --help

# Create a supervaizer_control.py file in your current directory
supervaizer scaffold


# Start the server using the configuration file
supervaizer start

# To get all the start options
supervaizer start --help
```

## CLI Commands

### install

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

## Environment Variables

All CLI options can also be configured through environment variables:

| Environment Variable      | Description                      | Default Value                |
| ------------------------- | -------------------------------- | ---------------------------- |
| SUPERVAIZER_PUBLIC_URL    | Url used for inbound connections | defaults to http://host:port |
| SUPERVAIZER_HOST          | Host to bind the server to       | 0.0.0.0                      |
| SUPERVAIZER_PORT          | Port to bind the server to       | 8000                         |
| SUPERVAIZER_ENVIRONMENT   | Environment name                 | dev                          |
| SUPERVAIZER_LOG_LEVEL     | Log level (DEBUG, INFO, etc.)    | INFO                         |
| SUPERVAIZER_DEBUG         | Enable debug mode (true/false)   | false                        |
| SUPERVAIZER_RELOAD        | Enable auto-reload (true/false)  | false                        |
| SUPERVAIZER_SCRIPT_PATH   | Path to configuration script     | -                            |
| SUPERVAIZER_OUTPUT_PATH   | Path for install command output  | supervaizer_control.py       |
| SUPERVAIZER_FORCE_INSTALL | Force overwrite existing file    | false                        |
