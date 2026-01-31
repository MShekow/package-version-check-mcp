# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.5] - 2026-01-31

### Added
- **get_supported_tools MCP tool**: New tool to query available tool managers and their installation methods
- **get_latest_tool_versions MCP tool**: Fetch latest versions of development tools like Node.js, Python, Go, etc. via mise-en-place

### Changed
- **Renamed tool**: `get_latest_versions` to `get_latest_package_versions`

## [0.0.4] - 2026-01-31

### Added
- **Terraform ecosystem support**: `get_latest_package_versions` supports fetching latest versions from Terraform providers and modules
- **PHP ecosystem support**: `get_latest_package_versions` supports fetching latest versions from Packagist (PHP packages)
- **Go ecosystem support**: `get_latest_package_versions` supports fetching latest versions from Go modules via proxy.golang.org

## [0.0.3] - 2026-01-30

### Added
- **NuGet ecosystem support**: `get_latest_package_versions` supports fetching latest versions from NuGet packages
- **Maven/Gradle ecosystem support**: `get_latest_package_versions` supports fetching latest versions from Maven Central and Gradle Plugin Portal
- **Helm charts support**: `get_latest_package_versions` supports fetching latest versions from Helm chart repositories

## [0.0.2] - 2026-01-28

### Added
- **Docker ecosystem support**: `get_latest_package_versions` supports fetching latest versions from Docker registries
  - Fully qualified image names (e.g., `index.docker.io/library/busybox`)
  - Optional tag compatibility hints to find latest matching suffixes (e.g., `"3.19-alpine"`)
  - Returns manifest digest (sha256) for Docker images


## [0.0.1] - 2026-01-27

### Added
- **Initial release** with basic functionality: support for NPM and PyPI ecosystems via tool `get_latest_package_versions` and for GitHub Actions via tool `get_github_action_versions_and_args`
