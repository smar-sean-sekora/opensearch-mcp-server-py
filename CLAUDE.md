# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an OpenSearch MCP (Model Context Protocol) Server implemented in Python. It provides a bridge between AI assistants and OpenSearch clusters, supporting both stdio and streaming transports (SSE/HTTP streaming).

## Development Commands

### Setup
```bash
# Create & activate virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv sync
```

### Running the Server
**Important**: Server commands must be run from the `src/` directory.

```bash
cd src

# Run stdio server (default)
uv run python -m mcp_server_opensearch

# Run streaming server
uv run python -m mcp_server_opensearch --transport stream

# Run multi-cluster mode with config
uv run python -m mcp_server_opensearch --mode multi --config ../config/dev-clusters.yml

# Run with AWS profile
uv run python -m mcp_server_opensearch --profile my-profile
```

### Testing
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=mcp_server_opensearch

# Run specific test file
uv run pytest tests/test_tools.py

# Run with verbose output
uv run pytest -v
```

### Code Quality
```bash
# Format code (required before commits)
uv run ruff format .

# Check code quality
uv run ruff check .

# Type checking
uv run mypy src/
```

### Dependency Management
```bash
# Add new package
uv add <package-name>

# Add development dependency
uv add --dev <package-name>

# Update dependencies after manual pyproject.toml changes
uv lock
uv sync

# Update all dependencies to latest versions
uv lock --upgrade
uv sync
```

## Architecture

### Core Components

- **Server Layer** (`src/mcp_server_opensearch/`)
  - `stdio_server.py`: Standard input/output transport
  - `streaming_server.py`: SSE and HTTP streaming transport
  - `clusters_information.py`: Multi-cluster configuration management
  - `__main__.py`: Entry point with argument parsing

- **OpenSearch Integration** (`src/opensearch/`)
  - `client.py`: OpenSearch client initialization with authentication
  - `helper.py`: Single REST call functions to OpenSearch API (one function = one API call)

- **Tool System** (`src/tools/`)
  - `tools.py`: Tool definitions and implementations using `TOOL_REGISTRY` dictionary
  - `tool_params.py`: Pydantic models for tool arguments (all extend `baseToolArgs`)
  - `tool_filter.py`: Tool filtering by name, category, or regex pattern
  - `tool_generator.py`: Dynamic tool schema generation
  - `config.py`: YAML configuration parsing for tool filters and customization
  - `utils.py`: Tool compatibility checking based on OpenSearch version
  - `index_filter.py`: Index-level access control with pattern-based filtering

### Server Modes

1. **Single Mode** (default)
   - Connects to one OpenSearch cluster via environment variables
   - Automatically filters tools based on OpenSearch version compatibility
   - Tools do not require `opensearch_cluster_name` parameter

2. **Multi Mode**
   - Supports multiple OpenSearch clusters defined in YAML config
   - All tools available regardless of version (compatibility checked at execution)
   - All tools require `opensearch_cluster_name` parameter
   - Tool filtering not supported

### Authentication Flow

Priority order: No Auth → IAM Role → Basic Auth → AWS Credentials

### Index Security

The server supports index-level access control to restrict which indexes can be accessed:
- **Allowed Patterns**: Whitelist approach using wildcards (`logs-*`) or regex (`regex:^logs-\d{4}$`)
- **Denied Patterns**: Blacklist approach with same pattern types
- **Priority**: Denied patterns checked first and take precedence over allowed patterns
- **Configuration**: Via YAML `index_security` section or environment variables
- **Validation**: Applied before OpenSearch queries in all tools with index parameters
- **Wildcard Bypass**: Index names with wildcards in tool calls bypass validation (OpenSearch expands them)

Example configuration:
```yaml
index_security:
  allowed_index_patterns:
    - "logs-*"
    - "metrics-*"
  denied_index_patterns:
    - "sensitive-*"
    - ".security*"
```

### Tool Architecture

**Key Design Principle**: Each helper function in `opensearch/helper.py` performs a single REST call to OpenSearch. This promotes:
- Clear separation of concerns
- Easy testing and maintenance
- Reusable OpenSearch operations

Tools in `tools/tools.py` orchestrate these helper functions and are registered in the `TOOL_REGISTRY` dictionary with:
- `description`: Tool documentation
- `input_schema`: Pydantic model JSON schema
- `function`: Async tool implementation
- `args_model`: Pydantic model class
- Optional: `min_version`, `max_version` for version compatibility

## Adding New Tools

1. **Create Tool Arguments Model** in `src/tools/tool_params.py`:
   ```python
   class YourToolArgs(baseToolArgs):
       """Arguments for YourTool."""
       param1: str = Field(description="Description")
   ```

2. **Add Helper Function** in `src/opensearch/helper.py`:
   ```python
   def your_helper_function(args: YourToolArgs) -> json:
       """Perform single REST call to OpenSearch."""
       from .client import initialize_client
       client = initialize_client(args)
       response = client.your_api_call()
       return response
   ```

3. **Implement Tool Function** in `src/tools/tools.py`:
   ```python
   async def your_tool_function(args: YourToolArgs) -> list[dict]:
       try:
           check_tool_compatibility('YourToolName', args)
           # Add index validation if tool accepts index parameter
           if hasattr(args, 'index') and args.index:
               validate_index_access(args.index)
           result = your_helper_function(args)
           return [{"type": "text", "text": json.dumps(result, indent=2)}]
       except Exception as e:
           return [{"type": "text", "text": f"Error: {str(e)}"}]
   ```

4. **Register Tool** in `TOOL_REGISTRY` dict in `src/tools/tools.py`:
   ```python
   TOOL_REGISTRY = {
       "YourToolName": {
           "description": "What this tool does",
           "input_schema": YourToolArgs.model_json_schema(),
           "function": your_tool_function,
           "args_model": YourToolArgs,
       }
   }
   ```

## Important Notes

- By default, only **core tools** are enabled (tool filtering only works in single mode)
- Tool filtering supports: exact names, categories, regex patterns, and write operation controls
- Tool customization (display names, descriptions) works in both single and multi modes
- All commands must be run from the `src/` directory
- The server supports both stdio and streaming (SSE/HTTP) transports
- Version compatibility is checked automatically in single mode, at runtime in multi mode
- Ruff line length is set to 99 characters
- Pydocstyle convention: Google
- Quote style: single quotes
