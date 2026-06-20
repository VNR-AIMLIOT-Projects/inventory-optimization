# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Observability**: Added Prometheus + Thanos + Grafana monitoring stack.
- **Monitoring**: Generic scrape-config to collect annotations and configured Thanos DO Spaces integration.
- **Security**: Added Prometheus scrape NetworkPolicies for `preprod` and `prod` namespaces.
- **Documentation**: Added observability architecture diagram and extensive documentation.

### Fixed
- **Observability**: Bumped `prometheus-fastapi-instrumentator` to 7.1.0 and patched `_IncludedRouter` bug preventing metrics scraping.
- **UI & Backend**: Fixed UI button clickability, DQN model load issues, and improved websocket config.
- **Infra**: Configured sticky sessions for Socket.io across multiple pods and forced websocket transport.
- **Training**: Fixed undefined variable `overallProgressPercent` and supported stopped runs by fixing the progress sum.
- **Webhook**: Removed duplicated code block.
- **Deps**: Synced `package-lock.json` for `prom-client`.

### Changed
- **Monitoring**: Updated Grafana dashboards and fixed Prometheus scrapers.
- **Docs**: Fixed mermaid styling syntax in `README.md`.

## [1.0.0] - Initial Stable Release
- Baseline project scaffolding, consisting of FastAPI backend, React Next.js frontend, RabbitMQ broker, and RL worker models.
