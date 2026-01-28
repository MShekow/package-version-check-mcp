# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.2] - 2026-01-28

### Added
- **Docker ecosystem support**: Added support for fetching latest versions from Docker registries
  - Fully qualified image names (e.g., `index.docker.io/library/busybox`)
  - Optional tag compatibility hints to find latest matching suffixes (e.g., `"3.19-alpine"`)
  - Returns manifest digest (sha256) for Docker images


## [0.0.1] - 2026-01-27

### Added
- **Initial release** with basic functionality: support for NPM and PyPI ecosystems via tool `get_latest_versions` and for GitHub Actions via tool `get_github_action_versions_and_args`
