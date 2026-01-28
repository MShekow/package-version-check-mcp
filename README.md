# package-version-check-mcp
A MCP server that returns the current, up-to-date version of packages you use as dependencies in a variety of ecosystems, such as Python, NPM, Go, or GitHub Actions

## Features

Currently supported ecosystems:
- **npm** - Node.js packages from the npm registry
- **pypi** - Python packages from PyPI
- **docker** - Docker container images from Docker registries
- **GitHub Actions** - Actions hosted on GitHub

## Usage

### Adding the MCP to Your Agent

There are three ways to make this MCP available to your AI coding agent:

#### Option 1: Use the Hosted Service (Easiest)

Point your agent to the free hosted service:
```
https://package-version-check-mcp.onrender.com/mcp
```

This is the quickest way to get started. Note that the hosted service may have rate limits from the underlying package registries.

#### Option 2: Run with uvx (for local use)

Use `uvx` to run the MCP server locally:
```bash
uvx package-version-check-mcp --mode=stdio
```

This automatically installs and runs the latest version from PyPI.

**Optional but recommended:** Set the `GITHUB_PAT` environment variable to a GitHub Personal Access Token (no scopes required) to avoid GitHub API rate limits.

#### Option 3: Run with Docker (for local use)

Use the pre-built Docker image:
```bash
docker run --rm -i ghcr.io/mshekow/package-version-check-mcp:latest --mode=stdio
```

**Optional but recommended:** Pass the `GITHUB_PAT` environment variable using `-e GITHUB_PAT=your_token_here` to avoid GitHub API rate limits.

### Configuring Your Agent

Once you've added the MCP server, you need to:

1. **Enable the MCP tools** in your agent's configuration. The available tools are documented below

2. **Nudge the agent to use the MCP** in your prompts. Most LLMs don't automatically invoke this MCP's tools without explicit guidance. Include instructions like:
   - "Use MCP to get latest versions"
   - "Check the latest package versions using the MCP tools"
   - "Use get_latest_versions to find the current version"

In case you forgot to add this prompt and your agent generated code with _outdated_ versions, you can just ask your agent to update the versions afterwards (e.g., "Update the dependencies you just added to the latest version via MCP").

### Available Tools

#### `get_latest_versions`

Fetches the latest versions of packages from various ecosystems.

**Input:**
- `packages`: Array of package specifications, where each item contains:
  - `ecosystem` (required): Either "npm", "pypi", or "docker"
  - `package_name` (required): The name of the package
    - For npm: package name (e.g., "express")
    - For pypi: package name (e.g., "requests")
    - For docker: fully qualified image name including registry and namespace (e.g., "index.docker.io/library/busybox")
  - `version` (optional):
    - For docker: tag compatibility hint (e.g., "1.36-alpine") to find the latest tag matching the same suffix pattern. If omitted, returns the latest semantic version tag.
    - For npm/pypi: not currently used

**Output:**
- `result`: Array of successful lookups with:
  - `ecosystem`: The package ecosystem (as provided)
  - `package_name`: The package name (as provided)
  - `latest_version`: The latest version number (e.g., "1.2.4") or Docker tag
  - `digest`: (optional) Package digest/hash if available. For Docker, this is the manifest digest (sha256).
  - `published_on`: (optional) Publication date if available (not available for Docker)
- `lookup_errors`: Array of errors with:
  - `ecosystem`: The package ecosystem (as provided)
  - `package_name`: The package name (as provided)
  - `error`: Description of the error

**Example:**
```json
{
  "packages": [
    {"ecosystem": "npm", "package_name": "express"},
    {"ecosystem": "pypi", "package_name": "requests"},
    {"ecosystem": "docker", "package_name": "index.docker.io/library/alpine", "version": "3.19-alpine"}
  ]
}
```

#### `get_github_action_versions_and_args`

Fetches the latest versions and metadata for GitHub Actions hosted on github.com.

**Input:**
- `action_names` (required): Array of action names in "owner/repo" format (e.g., ["actions/checkout", "docker/login-action"])
- `include_readme` (optional): Boolean (default: false), whether to include the action's README.md with usage instructions

**Output:**
- `result`: Array of successful lookups with:
  - `name`: The action name (as provided)
  - `latest_version`: The most recent Git tag (e.g., "v3.2.4")
  - `metadata`: The action.yml metadata as an object with fields:
    - `inputs`: Action input parameters
    - `outputs`: Action outputs
    - `runs`: Execution configuration
  - `readme`: (optional) The action's README content if `include_readme` was true
- `lookup_errors`: Array of errors with:
  - `name`: The action name (as provided)
  - `error`: Description of the error

**Example:**
```json
{
  "action_names": ["actions/checkout", "actions/setup-python"],
  "include_readme": false
}
```

## Development

### Running the Server Manually (For Development)

If you're developing or testing the MCP server locally, you can run it directly.

First, **follow the Package management with Poetry -> Setup instructions** to configure your virtual environments.

Next:

```bash
.poetry/bin/poetry run python -m package_version_check_mcp.main
```

Or if you have the `.venv` activated:

```bash
python src/package_version_check_mcp/main.py
```

### Package management with Poetry

#### Setup

On a new machine, create a venv for Poetry (in path `<project-root>/.poetry`), and one for the project itself (in path `<project-root>/.venv`), e.g. via `C:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe -m venv <path>`.
This separation is necessary to avoid dependency _conflicts_ between the project and Poetry.

Using the `pip` of the Poetry venv, install Poetry via `pip install -r requirements-poetry.txt`

Then, run `poetry sync --all-extras`, but make sure that either no venv is active, or the `.venv` one, but **not** the `.poetry` one (otherwise Poetry would stupidly install the dependencies into that one, unless you previously ran `poetry config virtualenvs.in-project true`). The `--all-extras` flag is required to install _development_ dependencies, such as pytest.

#### Updating dependencies

- When dependencies changed **from the outside**, e.g. because Renovate updated the `pyproject.toml` and `poetry.lock` file, run `poetry sync --all-extras` to update your local environment. This removes any obsolete dependencies from your `.venv` venv.
- If **you** updated a dependency in `pyproject.toml`, run `poetry update && poetry sync --all-extras` to update the lock file and install the updated dependencies including extras.
- To only update the **transitive** dependencies (keeping the ones in `pyproject.toml` the same), run `poetry update && poetry sync --all-extras`, which updates the lock file and installs the updates into the active venv.

Make sure that either no venv is active (or the `.venv` venv is active) while running any of the above `poetry` commands.
