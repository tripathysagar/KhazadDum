# Server Configuration Documentation

## Updated Environment Variables (`.env`)

```bash
# Snowflake credentials
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_WAREHOUSE=your_warehouse
SNOWFLAKE_DB=your_database          # Database name (default for server.py)
SNOWFLAKE_SCHEMA=your_schema        # Schema name (default for server.py)

# LLM configuration
MODEL_NAME=gpt-4o-mini              # Default model for server.py
LM_STUDIO_MODEL_NAME=lm_studio/openai/gpt-oss-20b
LM_STUDIO_API_BASE=http://localhost:1234/v1

# Server configuration
SERVER_HOST=0.0.0.0                 # Web server host
SERVER_PORT=8000                    # Web server port

# Chat configuration
MAX_STEPS=10                        # Max LLM iterations per query
MAX_CHAT_HIST=15                    # Context window size
```

## Running the Web Server

The `server.py` script has been refactored to accept command-line arguments that override `.env` defaults.

### Basic Usage

```bash
# Run with defaults from .env
python UI/server.py

# Override schema and database
python UI/server.py --schema SALES --db-name ANALYTICS

# Override model and port
python UI/server.py --model-name gpt-4 --port 8080

# Full override
python UI/server.py --schema SALES --db-name ANALYTICS --model-name claude-3-opus --host localhost --port 8080

# View all options
python UI/server.py --help
```

### Available Command-Line Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--schema` | str | `SNOWFLAKE_SCHEMA` or "AIRLINES" | Snowflake schema name |
| `--db-name` | str | `SNOWFLAKE_DB` or "AIRLINES" | Snowflake database name |
| `--model-name` | str | `MODEL_NAME` or "gpt-4o-mini" | LLM model identifier |
| `--host` | str | `SERVER_HOST` or "0.0.0.0" | Server host address |
| `--port` | int | `SERVER_PORT` or 8000 | Server port number |

### How It Works

1. **Priority Order**: Command-line arguments > Environment variables > Hardcoded defaults
2. **Dynamic Initialization**: The `initialize_chat()` function is called with the resolved parameters
3. **Startup Logging**: Server prints the active configuration on startup

### Example Output

```
Initializing chat with:
  Schema: SALES
  Database: ANALYTICS
  Model: gpt-4o-mini
Starting server on 0.0.0.0:8000
```

## Server Architecture Changes

### Before

```python
# Hardcoded values
agent = SnowflakeAgent()
M1 = DBMetadata(agent, "AIRLINES", "AIRLINES", model_name = model_name)
# ... rest of initialization
```

### After

```python
def initialize_chat(schema: str, db_name: str, model_name: str):
    """Initialize the chat components with specified parameters"""
    global agent, M1, SYSTEM_PROMPT, loop
    
    agent = SnowflakeAgent()
    M1 = DBMetadata(agent, schema, db_name, model_name=model_name)
    # ... rest of initialization
    return agent, M1, SYSTEM_PROMPT, loop

if __name__ == "__main__":
    load_dotenv()
    
    parser = argparse.ArgumentParser(description='Run the Snowflake Chat Server')
    # ... argument definitions
    
    args = parser.parse_args()
    initialize_chat(args.schema, args.db_name, args.model_name)
    serve(host=args.host, port=args.port, reload=True)
```

## Benefits

1. **Flexibility**: Switch between schemas/databases without editing code
2. **Multi-environment**: Easy to configure for dev/staging/prod
3. **Testing**: Run multiple instances with different configurations
4. **Documentation**: Self-documenting via `--help` flag
5. **Backward Compatible**: Works with existing `.env` configurations
