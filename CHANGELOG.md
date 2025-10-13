# Changelog

All notable changes to TickVault will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-10-13

### Added
- Initial release of TickVault
- Concurrent download functionality with multi-worker architecture
- Resume capability with SQLite metadata tracking
- Proxy support for distributed downloading
- Comprehensive retry logic with exponential backoff
- Data reading and decoding to pandas DataFrames
- Gap detection and data integrity verification
- Support for Forex majors, precious metals, and cryptocurrencies
- Configuration management via environment variables and .env files
- Structured logging with file and console handlers
- Progress bars for download and read operations

[0.1.0]: https://github.com/keyhankamyar/TickVault/releases/tag/v0.1.0