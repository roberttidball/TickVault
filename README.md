# TickVault

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**TickVault** is a high-performance Python library for downloading, storing, and accessing financial tick data from Dukascopy Bank's historical datafeed. Built for quantitative researchers and algorithmic traders who need reliable access to high-resolution market data.

## ✨ Features

- **Concurrent Downloads**: Multi-worker architecture with proxy support for fast, parallel data fetching
- **Resumable Operations**: Intelligent metadata tracking allows interrupted downloads to resume seamlessly
- **Efficient Storage**: Maintains compressed binary format on disk, decompressing only when needed
- **Data Integrity**: Built-in gap detection ensures continuous, reliable datasets
- **Simple API**: Download and read data with just a few lines of code
- **Configurable**: Extensive configuration options via environment variables or `.env` files
- **Production Ready**: Comprehensive error handling, logging, and retry logic with exponential backoff

## 📊 Supported Assets

- **Forex Majors**: EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, NZDUSD
- **Precious Metals**: XAUUSD (Gold), XAGUSD (Silver)
- **Cryptocurrencies**: BTCUSD, ETHUSD
- **Custom Symbols**: Easily extend with your own symbol configurations

## 🚀 Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Basic Usage

```python
from datetime import datetime
from tick_vault import download_range, read_tick_data

# Download historical data
await download_range(
    symbol='XAUUSD',
    start=datetime(2024, 1, 1),
    end=datetime(2024, 2, 1)
)

# Read data into pandas DataFrame
df = read_tick_data(
    symbol='XAUUSD',
    start=datetime(2024, 1, 1),
    end=datetime(2024, 1, 2)
)

print(df.head())
#                         time      ask      bid  ask_volume  bid_volume
# 0 2024-01-01 00:00:01.234  2045.50  2045.45     1500000     2000000
# 1 2024-01-01 00:00:01.567  2045.51  2045.46     1200000     1800000
```

### With Proxy Support

```python
await download_range(
    symbol='EURUSD',
    start=datetime(2024, 1, 1),
    end=datetime(2024, 2, 1),
    proxies=[
        'http://proxy1.example.com:8080',
        'http://proxy2.example.com:8080'
    ]
)
```

## 🏗️ Architecture

TickVault uses a queue-based concurrent architecture:

```
┌──────────────┐
│ Orchestrator │
└──────┬───────┘
       │
       ├──────────────┐
       │              │
   ┌───▼────┐    ┌───▼────┐
   │Download│    │Download│
   │Worker 1│    │Worker 2│
   └───┬────┘    └───┬────┘
       │              │
       └──────┬───────┘
              │
        ┌─────▼─────┐
        │ Metadata  │
        │  Worker   │
        └─────┬─────┘
              │
        ┌─────▼─────┐
        │  SQLite   │
        │ Database  │
        └───────────┘
```

- **Download Workers**: Fetch data concurrently with automatic retry and rate limiting
- **Metadata Worker**: Tracks download status in SQLite for resumability
- **Filesystem Storage**: Mirrors Dukascopy's structure for efficient organization

## ⚙️ Configuration

Configure TickVault via environment variables or a `.env` file:

```bash
# Core directories
TICK_VAULT_BASE_DIRECTORY=./tick_vault_data

# Download behavior
TICK_VAULT_WORKER_PER_PROXY=10
TICK_VAULT_FETCH_MAX_RETRY_ATTEMPTS=3
TICK_VAULT_FETCH_BASE_RETRY_DELAY=1.0

# Metadata batching
TICK_VAULT_METADATA_UPDATE_BATCH_SIZE=100
TICK_VAULT_METADATA_UPDATE_BATCH_TIMEOUT=1.0

# Logging
TICK_VAULT_BASE_LOG_LEVEL=DEBUG
TICK_VAULT_CONSOLE_LOG_LEVEL=INFO
```

Or configure programmatically:

```python
from tick_vault import reload_config

reload_config(
    base_directory='./custom_data',
    worker_per_proxy=15,
    fetch_max_retry_attempts=5
)
```

## 📁 Project Structure

```
TickVault/
├── tick_vault/
│   ├── __init__.py          # Public API
│   ├── chunk.py             # TickChunk data model
│   ├── config.py            # Configuration management
│   ├── constants.py         # Symbol registry and constants
│   ├── decoder.py           # Binary data decoder
│   ├── download_worker.py   # Concurrent download worker
│   ├── downloader.py        # Main orchestrator
│   ├── fetcher.py           # HTTP fetching with retry logic
│   ├── logger.py            # Centralized logging
│   ├── metadata.py          # SQLite metadata database
│   ├── metadata_worker.py   # Metadata batch processor
│   ├── reader.py            # Data loading and decoding
│   └── utils.py             # Utility functions
├── .env.example             # Example configuration
├── .gitignore
├── LICENSE
├── README.md
├── requirements.txt
└── pyproject.toml
```

## 📈 Data Format

Downloaded data is stored as LZMA-compressed binary files:

```
tick_vault_data/
├── downloads/
│   └── XAUUSD/
│       └── 2024/
│           └── 00/          # January (0-indexed)
│               └── 01/
│                   ├── 00h_ticks.bi5
│                   ├── 01h_ticks.bi5
│                   └── ...
├── metadata.db              # SQLite tracking database
└── logs.log                 # Application logs
```

Each `.bi5` file contains one hour of tick data. The decoded format includes:

- **time**: Tick timestamp with millisecond precision
- **ask**: Ask price
- **bid**: Bid price
- **ask_volume**: Ask volume (scaled)
- **bid_volume**: Bid volume (scaled)

## 🛡️ Error Handling

TickVault includes comprehensive error handling:

- **Network Errors**: Automatic retry with exponential backoff
- **Rate Limiting**: Respects `Retry-After` headers and implements backoff
- **Data Integrity**: Verifies data continuity before reading
- **Graceful Shutdown**: Properly handles interruptions and cleanup

## 🔧 Advanced Usage

### Resume Interrupted Downloads

Simply call `download_range` again with the same parameters. TickVault automatically detects and downloads only missing chunks:

```python
# Initial download (interrupted)
await download_range('XAUUSD', datetime(2024, 1, 1), datetime(2024, 12, 31))

# Resume - only downloads what's missing
await download_range('XAUUSD', datetime(2024, 1, 1), datetime(2024, 12, 31))
```

### Custom Symbol Configuration

Add your own symbols to `tick_vault/constants.py`:

```python
PIPET_SIZE_REGISTRY: dict[str, float] = {
    # Your custom symbol
    "CUSTOM": 1e-5,
    # ... existing symbols
}
```

### Check Data Integrity

```python
from tick_vault.metadata import MetadataDB

with MetadataDB() as db:
    # Raises RuntimeError if gaps exist
    db.check_for_gaps('XAUUSD')
```

## 🧪 Testing

Comprehensive test suite coming soon with pytest.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📮 Support

For issues, questions, or contributions, please open an issue on GitHub.

## 🙏 Acknowledgments

- Data provided by [Dukascopy Bank](https://www.dukascopy.com/)
- Built for the quantitative finance community

## ⚠️ Disclaimer

This software is provided for research and educational purposes. Users are responsible for complying with Dukascopy's terms of service and any applicable data usage policies. The authors assume no liability for any misuse or violations.

---

**Happy Trading! 📊✨**