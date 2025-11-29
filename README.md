# KhazadDum

**A secure Text-to-SQL framework with automated schema extraction, LLM-based foreign key inference, and persistent chat management.**

## Installation

```sh
git clone https://github.com/tripathysagar/KhazadDum
cd KhazadDum
pip install -e .
```

## Features

- 🔒 **Safe Query Execution** - Only SELECT queries allowed with built-in validation
- 🤖 **LLM-Powered** - Uses LiteLLM for multi-provider LLM support
- 📊 **Auto Schema Extraction** - Automatically extracts database metadata
- 🔗 **FK Inference** - LLM-based foreign key relationship detection
- 💾 **Chat Persistence** - SQLite-based conversation history
- 🎨 **Web UI** - FastHTML-based interactive chat interface

## Quick Start

### 1. Configure Environment

Create a `.env` file with your credentials:

```bash
# Snowflake credentials
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_ACCOUNT=your_account
SNOWFLAKE_WAREHOUSE=your_warehouse
SNOWFLAKE_DB=your_database
SNOWFLAKE_SCHEMA=your_schema

# LLM configuration
MODEL_NAME=gpt-4o-mini
```

### 2. Run the Web Server

```bash
# Run with defaults from .env
python UI/server.py

# Override schema and database
python UI/server.py --schema SALES --db-name ANALYTICS

# Override model
python UI/server.py --model-name gpt-4

# Custom port
python UI/server.py --port 8080
```

### 3. Use in Code

```python
from KhazadDum.SnowflakeCore import SnowflakeAgent, DBMetadata

# Initialize agent
agent = SnowflakeAgent()

# Extract metadata with caching
metadata = DBMetadata(agent, "AIRLINES", "AIRLINES")
metadata()  # Extracts and caches schema

# Execute safe queries
result = agent.execute_query("SELECT * FROM flights LIMIT 10")
print(result.data)  # Returns list of dicts
```

## Architecture

- **Core Layer** (`core.py`) - Abstract base classes for database agents
- **Database Layer** (`SnowflakeCore.py`) - Snowflake integration with metadata extraction
- **Agent Layer** (`AgentV1.py`) - LLM prompt formatting and tool result parsing
- **Chat Layer** (`ChatDB.py`, `Chatloop.py`) - Conversation management and persistence
- **UI Layer** (`UI/server.py`) - FastHTML web interface

## Documentation

Full documentation available at: [https://tripathysagar.github.io/KhazadDum/](https://tripathysagar.github.io/KhazadDum/)

## Development

```sh
# Install in development mode
pip install -e .

```

## License

Apache 2.0
