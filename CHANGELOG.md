# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Note:** There is an automatic release GitHub workflow which regularly pushes new _patch-level_ (x.y.**z**) releases to PyPI and GHCR, whenever there are updates for the underlying dependencies used by this MCP. These patch versions do _not_ appear in this changelog!

## [1.2.0] - 2026-02-14

### Changed
- **GitHub tags handling**: The routine that determines the latest version of GitHub.com tags now looks at _all_ tags. It no longer relies on the order returned by the API, assuming that the first entry is the latest one. This fixes getting the latest version for actions such as `anothrNick/github-tag-action` where `1.75.0` is correct, not `v1`

## [1.1.0] - 2026-02-07

### Changed
- **Caching now optional**: The caching layer introduced in v1.0.0 is now optional

## [1.0.0] - 2026-02-06

### Added
- **Swift ecosystem support**: `get_latest_package_versions` supports fetching latest Swift package versions from GitHub.com repositories
- **Dart ecosystem support**: `get_latest_package_versions` supports fetching latest Dart package versions from pub.dev
- **Caching layer**: Added in-memory cache for `get_latest_package_versions` with configurable TTL and max size, to improve performance and reduce load on external APIs

### Changed
- Parsing of Helm charts in ChartMuseum repositories is now more memory-efficient and no longer requires yq. This improves performance for repositories with a large numbers of charts (e.g., Bitnami).
- Removed `version_hint` support for PHP
- Introduced new version parser class (borrowed from Python's packaging library) to handle complex version strings across ecosystems more robustly. This should improve handling of pre-releases and non-standard "variant" version formats.

## [0.0.6] - 2026-02-02

### Added
- **Ruby ecosystem support**: `get_latest_package_versions` supports fetching latest Ruby gem versions from rubygems.org
- **Rust ecosystem support**: `get_latest_package_versions` supports fetching latest Rust crate versions from crates.io

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
