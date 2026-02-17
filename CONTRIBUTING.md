# Contributing to Mem OS

Thanks for your interest in contributing to Mem OS.

## Development Setup

```bash
git clone https://github.com/star-ga/mem-os.git
cd mem-os
pip install -e ".[all]"
```

This installs mem-os in editable mode with all optional dependencies (FastMCP for the MCP server, sentence-transformers for embedding re-rank).

For core development only (no optional deps):

```bash
pip install -e .
```

## Running Tests

```bash
# Unit tests
python3 -m pytest tests/ -v

# Structural validation (74+ checks)
bash maintenance/validate.sh /path/to/workspace
# or cross-platform:
python3 maintenance/validate_py.py /path/to/workspace

# End-to-end smoke test
bash scripts/smoke_test.sh
```

## Setting Up the MCP Server Locally

1. Install the MCP dependency:

```bash
pip install "fastmcp>=2.0"
```

2. Initialize a test workspace:

```bash
python3 scripts/init_workspace.py /tmp/test-ws
```

3. Run the server:

```bash
# stdio transport (for Claude Code / Claude Desktop)
MEM_OS_WORKSPACE=/tmp/test-ws python3 mcp_server.py

# HTTP transport (for multi-client / remote)
MEM_OS_WORKSPACE=/tmp/test-ws python3 mcp_server.py --transport http --port 8765
```

4. Add to Claude Desktop config (`~/.claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "mem-os": {
      "command": "python3",
      "args": ["/path/to/mem-os/mcp_server.py"],
      "env": {"MEM_OS_WORKSPACE": "/path/to/workspace"}
    }
  }
}
```

## Submitting to modelcontextprotocol/servers

1. Fork `modelcontextprotocol/servers` on GitHub.
2. Add an entry to the community servers section following the existing format.
3. Include: server name, short description, install command, and link to this repo.
4. Open a pull request with the addition.
5. See `mcp-listing.md` in this repo for the prepared listing template.

## Guidelines

- Keep zero-dependency policy for core modules (stdlib only).
- All mutations to source of truth must go through the apply engine.
- Add tests for new functionality in `tests/`.
- Run `python3 -m pytest tests/ -v` before submitting a PR.
- Follow existing code style (120 char line length, type hints where practical).
- No auto-write to source of truth (decisions/tasks) without going through the proposal pipeline.
- No features that require a daemon or background process.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
