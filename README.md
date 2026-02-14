# package-version-check-mcp

A MCP server that returns the latest stable versions of packages you use as dependencies in a variety of ecosystems, such as Python, NPM, Go, or GitHub Actions.

It also supports looking up the latest versions of almost 1000 tools, such as **development runtimes** like `python`, `node`, `dotnet`, **development tools** like `gradle`, and various **DevOps tools** like `kubectl` or `terraform`, via the [mise-en-place](https://mise.jdx.dev/) tool.

## Why do I need this?

Whenever an AI coding agents generates files that pin dependency versions, they insert **outdated versions** because their training happened weeks or months ago, and new dependency versions have been released since then. As a developer, it is annoying having to manually fix these outdated versions.

This MCP fixes this problem. Use it together with an MCP such as [Context7](https://context7.com/) to avoid that your AI agent produces outdated code.

## Features

Supported ecosystems / tools:
- Developer ecosystems:
  - **NPM** - Node.js packages from registry.npmjs.org
  - **PyPI** - Python packages from PyPI
  - **NuGet** - .NET packages from NuGet
  - **Maven / Gradle** - Java/Kotlin/Scala packages from Maven repositories (Maven Central, Google Maven, etc.)
  - **Go** - Go modules from proxy.golang.org
  - **PHP** - PHP packages from Packagist (used by Composer)
  - **Ruby** - Ruby gems from rubygems.org
  - **Rust** - Rust crates from crates.io
  - **Swift** - Swift packages from GitHub repositories
  - **Dart** - Dart packages from pub.dev
- DevOps ecosystems:
  - **Docker** - Docker container images from Docker registries
  - **Helm** - Helm charts from ChartMuseum repositories and OCI registries
  - **GitHub Actions** - Actions hosted on GitHub.com, returning their current version, their inputs and outputs, and (optionally) their entire README with usage examples
  - **Terraform _Providers_ and _Modules_** - Providers & Modules from Terraform Registry, OpenTofu Registry, or custom registries
  - Various _tools_ such as `kubectl`, `terraform`, `gradle`, `maven`, etc. supported by mise-en-place

## Usage

### Adding the MCP to Your Agent

There are three ways to make this MCP available to your AI coding agent:

#### Option 1: Use the Hosted Service (Easiest)

Point your agent to the free hosted service:
```
https://package-version-check-mcp.onrender.com/mcp
```
in (streamable) HTTP mode.

This is the quickest way to get started. Note that the hosted service may have rate limits from the underlying package registries.

#### Option 2: Run with uvx (for local use)

Use `uvx` to run the MCP server locally:
```bash
uvx package-version-check-mcp --mode=stdio
```

This automatically installs and runs the latest version from PyPI.

**Requirements:**
- You need the `mise` binary on PATH if you want to call the tools `get_supported_tools` or `get_latest_tool_versions`

**Optional but recommended:** Set the `GITHUB_PAT` environment variable to a GitHub Personal Access Token (no scopes required) to avoid GitHub API rate limits.

#### Option 3: Run with Docker (for local use)

Use the pre-built Docker image:
```bash
docker run --pull=always --rm -i ghcr.io/mshekow/package-version-check-mcp:latest --mode=stdio
```

**Optional but recommended:** Pass the `GITHUB_PAT` environment variable using `-e GITHUB_PAT=your_token_here` to avoid GitHub API rate limits.

### Caching Configuration

To improve performance and reduce API calls to package registries, you can enable caching:

- `PACKAGE_VERSION_CACHE_ENABLED`: Set to `true` to enable caching (disabled by default)
- `PACKAGE_VERSION_CACHE_TTL_SECONDS`: Cache duration in seconds (default: 3600 / 1 hour)
- `PACKAGE_VERSION_CACHE_MAX_SIZE_MB`: Maximum cache size in MB (default: 64)

The cache is an in-memory TTL (Time-To-Live) cache. It resets when the MCP server restarts.

### Configuring Your Agent

Once you've added the MCP server, you need to:

1. **Enable the MCP tools** in your agent's configuration. The available tools are documented below

2. **Nudge the agent to use the MCP** in your prompts. Most LLMs don't automatically invoke this MCP's tools without explicit guidance. Include instructions like:
   - "Use MCP to get latest versions"
   - "Check the latest package versions using the MCP tools"
   - "Use get_latest_package_versions to find the current version"

In case you forgot to add this prompt and your agent generated code with _outdated_ versions, you can just ask your agent to update the versions afterwards (e.g., "Update the dependencies you just added to the latest version via MCP").

### Available Tools

#### `get_latest_package_versions`

Fetches the latest versions of packages from various ecosystems.

**Input:**
- `packages`: Array of package specifications, where each item contains:
  - `ecosystem` (required): Either "npm", "pypi", "nuget", "maven_gradle", "go", "php", "rubygems", "rust", "swift", "dart", "docker", "helm", "terraform_provider", or "terraform_module"
  - `package_name` (required): The name of the package
    - For npm: package name (e.g., "express")
    - For pypi: package name (e.g., "requests")
    - For nuget: package name (e.g., "Newtonsoft.Json")
    - For maven_gradle: "[registry:]<groupId>:<artifactId>" format (e.g., "org.springframework:spring-core"). If registry is omitted, Maven Central is assumed.
    - For go: Absolute module identifier (e.g., "github.com/gin-gonic/gin")
    - For php: Package name in "vendor/package" format (e.g., "monolog/monolog", "laravel/framework")
    - For rubygems: Gem name (e.g., "rails", "devise")
    - For rust: Crate name (e.g., "serde", "tokio")
    - For swift: GitHub URL (e.g., "https://github.com/Alamofire/Alamofire.git" or "github.com/owner/repo.git"). Only github.com is supported.
    - For dart: Package name from pub.dev (e.g., "http", "flutter")
    - For docker: fully qualified image name including registry and namespace (e.g., "index.docker.io/library/busybox")
    - For helm: Either ChartMuseum URL ("https://host/path/chart-name") or OCI reference ("oci://host/path/chart-name")
    - For terraform_provider: "[registry/]<namespace>/<type>" format (e.g., "hashicorp/aws" or "registry.terraform.io/hashicorp/aws"). If registry is omitted, registry.terraform.io is assumed. Supports alternative registries like registry.opentofu.org.
    - For terraform_module: "[registry/]<namespace>/<name>/<provider>" format (e.g., "terraform-aws-modules/vpc/aws" or "registry.terraform.io/terraform-aws-modules/vpc/aws"). If registry is omitted, registry.terraform.io is assumed. Supports alternative registries like registry.opentofu.org.
  - `version_hint` (optional):
    - For docker: tag compatibility hint (e.g., "1.36-alpine") to find the latest tag matching the same suffix pattern. If omitted, returns the latest semantic version tag.
    - For helm (OCI only): tag compatibility hint similar to Docker
    - For npm/pypi/nuget/maven_gradle/go/php/rubygems/rust/swift/dart/helm (ChartMuseum)/terraform_provider/terraform_module: not currently used

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

#### `get_supported_tools`

Returns a list of all tool names supported by the `get_latest_tool_versions` MCP tool.

This tool queries the `mise` registry to retrieve all available tool names that can be managed by mise.

**Input:**
- No parameters required

**Output:**
- Array of tool short names (e.g., ["1password", "act", "node", "python", ...])

#### `get_latest_tool_versions`

Fetches the latest stable versions of development and DevOps tools supported by mise-en-place.

This tool is for tools that are NOT part of language ecosystems like PyPI or NPM. For language ecosystem packages (including Terraform providers and modules), use `get_latest_package_versions` instead.

**Use cases:**
- **gradle** or **maven**: Pin the Gradle or Maven version in the `distributionUrl` in `gradle-wrapper.properties` or `maven-wrapper.properties`
  - Example: `distributionUrl=https://services.gradle.org/distributions/gradle-8.5-bin.zip`
  - Example: `distributionUrl=https://repo.maven.apache.org/.../apache-maven-3.9.6-bin.zip`
- **terraform**: Pin `terraform.required_version` in a file like `version.tf` or `versions.tf`
  - Example: `terraform { required_version = "~> 1.6.0" }`
- **kubectl** or **azure**: Pin the version in a download URL called with `curl` or `wget`, e.g., in a Dockerfile
  - Example: `RUN curl -LO https://dl.k8s.io/release/v1.28.0/bin/linux/amd64/kubectl`

To see all available tools, use the `get_supported_tools` tool.

**Input:**
- `tool_names` (required): Array of tool names (e.g., ["terraform", "gradle", "kubectl"])

**Output:**
- `result`: Array of successful lookups with:
  - `tool_name`: The tool name (as provided)
  - `latest_version`: The latest stable version number (e.g., "1.6.5")
- `lookup_errors`: Array of errors with:
  - `tool_name`: The tool name (as provided)
  - `error`: Description of the error

## Why build yet another MCP

This MCP is certainly not the first one to tackle the "outdated dependency" problem. However, we feel that it has various advantages over other MCPs:

- We offer (far) better ecosystem coverage than other MCPs
- There is full test coverage, with automated dependency updates (powered by Renovate) and regular, automated release builds. In contrast, other projects are often vibe coded, have poor (or no) tests, and are already abandoned, because the authors were just messing around
- This MCP provides _several_ alternatives for how to run it locally (uvx or docker), or you can just use the free hosted offering (which other MCPs do not have)
- This MCP uses a **minimal** Docker/OCI image, hardened for security. SBOMs you generate with tools like Trivy are known to be correct, and the image is signed with Cosign (which allows you to verify its authenticity in case you want to self-host the MCP)

## Development

### Prerequisites

#### mise-en-place

The MCP server depends on the `mise-en-place` package for looking up tool versions. See https://mise.jdx.dev/installing-mise.html for installation instructions.

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

<!-- mcp-name: io.github.MShekow/package-version-check-mcp -->
