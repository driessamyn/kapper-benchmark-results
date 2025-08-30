# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains benchmark results and analysis tools for the Kapper library, comparing its performance against raw JDBC, Hibernate, and Ktorm across different database operations (find100, findById, insertSingleRow, simpleJoin, updateSingleRow) and databases (SQLite, PostgreSQL).

**CURRENT PROJECT STATUS (Dec 28, 2025):**
Completed! All phases of the automated benchmark pipeline are fully implemented with SSH disconnection protection. The system provides complete end-to-end benchmark automation with robust cloud infrastructure.

**COMPLETED ENHANCEMENTS:**
- **🔐 SSH Disconnection Protection**: Complete tmux session management with reconnection capabilities
- **📱 Enhanced Monitoring**: Real-time progress tracking with intelligent session detection  
- **🔄 Automatic Reconnection**: Monitor script with reconnection capability after network interruptions
- **PostgreSQL + Testcontainers Integration**: Full database testing (SQLite + PostgreSQL) with Docker/Podman support
- **Python Virtual Environments**: Isolated dependency management for both cloud and local execution  
- **Dynamic Instance Reuse**: Intelligent cloud instance management with 5-8 minute time savings
- **Multi-Database Support**: Complete testing across SQLite (embedded) and PostgreSQL (containerized)
- **Enhanced Security**: IP-restricted SSH access with automatic socket permission handling

## Automated Benchmark Pipeline

### ✅ Phase 1: Core Infrastructure (COMPLETED)
- **`scripts/release_manager.py`**: Downloads Kapper benchmark suites from GitHub releases
- **`scripts/executor.py`**: Executes JMH benchmarks and collects results (supports both run.sh and run-mapper.sh)
- Created synthetic `kapper-benchmarks-1.5.0.zip` package for version comparisons
- Fixed file copying and path resolution issues

### ✅ Phase 2: Data Processing & Analysis (COMPLETED)
- **`analysis/models.py`**: Data models for benchmark results, version comparisons, and library comparisons
- **`analysis/result_parser.py`**: Parses JMH JSON outputs into structured data (handles different file naming conventions)
- **`analysis/comparator.py`**: Performs two types of comparisons:
  1. Version-to-version comparison (e.g., 1.6.1 vs 1.5.0)
  2. Library comparison (Kapper vs JDBC/Hibernate/Ktorm within same version)
- **`analysis/visualizer.py`**: Generates charts with absolute performance values:
  - Stacked bars showing P50 (solid) and P99 (faded) performance
  - Error bars overlaid on bars
  - Bars sorted by speed (fastest left)
  - Version comparison charts (Kapper operations only)
  - Library comparison charts (Kapper vs competitors)
  - AutoMapper scenario comparison charts

### ✅ Phase 3: Automated Reporting (COMPLETED)
- **`reporting/report_generator.py`**: Generates comprehensive markdown reports with:
  - Executive summary with key performance changes
  - Version comparison analysis (improvements/regressions)  
  - Library competitive analysis (Kapper vs alternatives)
  - AutoMapper scenario performance breakdown
  - System information and detailed results tables
  - Chart references and visualizations section
- **`reporting/llm_prompt_builder.py`**: Creates structured LLM analysis prompts:
  - Performance analysis prompts with context and data
  - Technical investigation prompts for root cause analysis
  - Structured output format requirements for AI analysis
- **`reporting/main.py`**: Complete end-to-end pipeline integration script with:
  - Automated download and benchmark execution (with smart skipping)
  - Version-specific directory organization (/results/<version>/)
  - Report and chart generation
  - LLM prompt creation for AI analysis

### ✅ Phase 4: OCI Cloud Infrastructure (COMPLETED)
- **`oci/setup/setup-prerequisites.sh`**: One-time infrastructure setup across multiple regions
  - Creates VCNs, Internet Gateways, Route Tables, Security Lists, Subnets
  - Multi-region support: us-phoenix-1, ca-toronto-1, uk-london-1
  - Dynamic IP-restricted SSH access for security
  - Automatic region accessibility testing
- **`oci/setup/run-benchmarks.sh`**: Complete cloud benchmark execution pipeline with dynamic instance reuse
  - Runtime ARM capacity detection across regions
  - **Dynamic Instance Management**: Real-time detection and intelligent reuse of running instances
  - **Smart Cleanup**: Automatically terminates multiple instances to prevent resource waste
  - **Robust SSH Testing**: Multi-attempt connectivity testing with fallback strategies
  - Oracle Linux Cloud Developer with pre-installed GraalVM JDK 21 and automatic Docker setup
  - Python benchmark pipeline integration (no code duplication)
  - Results download and cleanup
- **`oci/setup/list-all-instances.sh`**: Multi-region instance monitoring
  - Shows instances across all accessible regions
  - Displays state, cost implications, and detailed information
  - Accurate counting of running/stopped/terminated instances
- **`oci/setup/stop-all-instances.sh`**: Emergency cleanup across regions
  - Terminates all instances in all accessible regions
  - Optional force cleanup of terminated instances
  - Cost protection and safety features

### ✅ Phase 5: SSH Disconnection Protection (COMPLETED)
- **Enhanced `oci/setup/run-benchmarks.sh`**: Complete tmux session management
  - Automatic tmux installation and session creation
  - Benchmarks run in persistent sessions that survive SSH disconnections
  - Real-time monitoring with benchmark output logging
  - Smart session management and completion detection
- **`oci/monitor-benchmark.sh`**: Advanced monitoring with reconnection capabilities
  - Automatic session detection and reconnection
  - Real-time progress monitoring with log output
  - Interactive and non-interactive terminal support
  - Multiple monitoring modes (continuous, single-check, reconnect)
  - Live benchmark output streaming and status tracking
- **Robust SSH protection workflow**:
  - Benchmarks continue running despite network interruptions
  - Easy reconnection to existing sessions after disconnection
  - Comprehensive progress tracking and completion detection
  - Automatic result collection upon benchmark completion

## Commands

### Complete Automated Pipeline
- **Full end-to-end pipeline**: `python -m benchmark.reporting.main <baseline> <comparison>`
  - Downloads benchmark suites if needed
  - Runs benchmarks if results don't exist
  - Generates comprehensive reports and LLM prompts
  - Organizes all artifacts in version-specific directories
- **Pipeline options**:
  - `--skip-benchmarks`: Use existing results, skip download/execution
  - `--quick`: Use quick benchmark mode (faster but less accurate)
  - `--force-rerun`: Re-download and re-run benchmarks even if results exist
  - `--no-charts`: Skip chart generation
  - `--prompt-only`: Only generate LLM prompts
  - `--technical-prompt`: Generate technical investigation prompt

### Individual Components (for testing/development)
- **Benchmark execution**: `python -m benchmark.execution.main <version> [--quick]`
- **Analysis components**: 
  - Parser: `python -m benchmark.analysis.main parse results/1.6.1 1.6.1`
  - Comparator: `python -m benchmark.analysis.main compare 1.5.0 1.6.1`
  - Visualizer: `python -m benchmark.analysis.main visualize results/1.6.1`
- **Reporting components**:
  - Full reporting: `python -m benchmark.reporting.main 1.5.0 1.6.1`

### Examples
- **Complete analysis pipeline**: `python -m benchmark.reporting.main 1.5.0 1.6.1`
- **Quick analysis with existing results**: `python -m benchmark.reporting.main 1.5.0 1.6.1 --skip-benchmarks`
- **Generate only LLM prompts**: `python -m benchmark.reporting.main 1.5.0 1.6.1 --prompt-only`
- **Quick benchmark mode**: `python -m benchmark.reporting.main 1.5.0 1.6.1 --quick`
- **Single version analysis**: `python -m benchmark.analysis.main parse results/1.6.1 1.6.1`

### OCI Cloud Benchmarks with SSH Protection (PostgreSQL + SQLite)
- **One-time setup**: `./setup/setup-prerequisites.sh`
- **Run cloud benchmarks**: `./setup/run-benchmarks.sh 1.6.1` (auto-reuses instances, tmux protected)
- **Complete comparison**: `./setup/run-benchmarks.sh 1.6.1 --baseline 1.5.0` (full pipeline with baseline)
- **Monitor progress**: `./oci/monitor-benchmark.sh --reconnect` (reconnect after disconnection)
- **Quick cloud testing**: `./setup/run-benchmarks.sh 1.6.1 --quick` (fast reuse cycles)
- **Force new instance**: `./setup/run-benchmarks.sh 1.6.1 --force-new-instance` (clean environment)
- **Keep for reuse**: `./setup/run-benchmarks.sh 1.6.1 --keep-instance`
- **Monitor instances**: `./setup/list-all-instances.sh`
- **Emergency cleanup**: `./setup/stop-all-instances.sh`

### SSH Disconnection Protection Commands
- **Enhanced monitoring**: `./oci/monitor-benchmark.sh` (continuous monitoring)
- **Reconnect to session**: `./oci/monitor-benchmark.sh --reconnect` (after disconnection)
- **Single status check**: `./oci/monitor-benchmark.sh --once` (one-time check)
- **Manual tmux reconnect**: `ssh benchmark@<ip> 'tmux attach -t kapper-benchmark'`

### Environment Setup
- **Java**: Eclipse Temurin JDK 21 LTS (free license, production-ready)
- **Python**: Activate virtual environment: `source venv/bin/activate` (macOS/Linux)
- Install dependencies: `pip install -r requirements.txt`

### Legacy Data Analysis
- Process benchmark results: Use the Jupyter notebook at `python/process.ipynb`
- Start Jupyter: `jupyter notebook python/process.ipynb`

## Repository Structure

- **`benchmark/`**: Unified Python package for all benchmark operations
  - `execution/`: Benchmark execution components
    - `release_manager.py`: Downloads benchmark suites from GitHub releases
    - `executor.py`: Executes benchmarks and collects results
    - `main.py`: Entry point for benchmark execution
  - `analysis/`: Data processing and analysis components
    - `models.py`: Data structures for benchmark results and comparisons
    - `result_parser.py`: Parses JMH JSON into structured data (tested ✅)
    - `comparator.py`: Version and library comparison engine (tested ✅)
    - `visualizer.py`: Chart generation with stacked bars and error bars (tested ✅)
  - `reporting/`: Report generation and LLM prompt building
    - `report_generator.py`: Comprehensive markdown report generation (✅)
    - `llm_prompt_builder.py`: Structured LLM analysis prompts (✅)  
    - `main.py`: Complete end-to-end pipeline integration script (✅)
  - `__main__.py`: Package entry point with subcommand routing
- **`downloads/`**: Downloaded benchmark suites
  - `kapper-benchmarks-1.5.0/`: Synthetic benchmark package for 1.5.0
  - `kapper-benchmarks-1.6.1/`: Downloaded from GitHub release
- **`oci/`**: Oracle Cloud Infrastructure automation with SSH disconnection protection
  - `setup/setup-prerequisites.sh`: One-time infrastructure setup (5-script architecture)
  - `setup/run-benchmarks.sh`: Complete cloud benchmark execution with tmux protection
  - `monitor-benchmark.sh`: Enhanced monitoring with reconnection capability (✅)
  - `setup/list-all-instances.sh`: Multi-region instance monitoring
  - `setup/stop-all-instances.sh`: Emergency cleanup across regions
  - `instances/`: Configuration files for infrastructure state and reusable instances
  - `README.md`: Complete OCI documentation with SSH protection guide
- **`results/`**: Version-specific benchmark results and artifacts
  - **`<version>/`**: Each version has its own directory containing:
    - Benchmark results: `*.json` files with JMH output
    - System info: `info.txt` with runtime details
    - Generated charts: `graphs/*.png` visualizations
    - Analysis reports: `*.md` comprehensive reports
    - LLM prompts: `llm_prompt_*.md` for AI analysis
  - Legacy: `1.3/01/`: Legacy results with error/percentile data
  - Results format: `main-results-avgt.json`, `mapper-results-avgt.json`, `mapper-results-ss.json`
- `python/process.ipynb`: Legacy Jupyter notebook (being replaced)
- `requirements.txt`: Python dependencies (includes matplotlib, seaborn, pandas, numpy)
- `venv/`: Virtual environment for Python dependencies

## Data Processing Workflow (Legacy)

The old analysis workflow is in `process.ipynb` - this is being replaced by the automated pipeline.

## Key Data Structure

Benchmark results contain columns: Benchmark, DatabaseType, Library, Rows, Mode, Cnt, Score, Error, Units
- Libraries compared: JDBC, KAPPER, KAPPER-NO-AUTOMAP, HIBERNATE, KTORM (and KAPPER-RECORD in v1.6+)
- Benchmark types: find100, findById, insertSingleRow, simpleJoin, updateSingleRow
- Databases: SQLITE, POSTGRESQL
- Mapper benchmarks: AutoMapperBenchmark with different scenarios

## Key Implementation Notes

- **Kapper 1.5.0 doesn't have KAPPER-RECORD library** (added in 1.6.0+)
- **Synthetic 1.5.0 package** was created by building from source at tag 1.5.0
- **Executor runs mapper benchmarks first** (faster for testing), then main benchmarks
- **All scripts handle missing execute permissions** automatically
- **Scripts work from both root directory and analysis directory** (fixed path resolution)
- **Quick mode benchmarks** (--quick flag) produce no variation data (P50=P99, no errors)
- **Full benchmark mode needed** for proper stacked bar charts and error margins
- **1.3 legacy data** has proper error/percentile data for testing visualizations
- **Version-specific directories** organize all artifacts (results, charts, reports) by version
- **Smart skipping** prevents redundant downloads/executions if results already exist
- **End-to-end automation** from GitHub release to AI-ready analysis prompts
- **Multi-region OCI capacity detection** finds available ARM instances automatically
- **5-script OCI architecture** with enhanced monitoring and SSH protection
- **SSH disconnection protection** using tmux sessions for long-running benchmarks (✅)
- **Enhanced monitoring capabilities** with real-time reconnection support (✅)
- **Dynamic IP-restricted SSH** for security (fetches current public IP automatically)
- **Oracle Linux Cloud Developer** with pre-installed GraalVM JDK 21 and automatic Docker setup for Testcontainers support
- **Dynamic instance detection** scans for running instances in real-time (no stale config files)
- **Intelligent SSH testing** with multiple retry attempts and fallback strategies
- **Smart instance cleanup** automatically terminates multiple instances to prevent resource waste
- **Cost control** ensures only one instance runs at a time across all regions
- **Python pipeline integration** eliminates code duplication between local and cloud execution
- **Tmux session persistence** allows benchmarks to survive network interruptions (✅)
- **Intelligent reconnection** automatically detects and reconnects to active sessions (✅)

## Analysis Pipeline Workflow

The complete automated pipeline (`reporting/main.py`) performs these steps:

1. **Benchmark Execution** (if needed):
   - Downloads benchmark suite using `release_manager.py`
   - Executes benchmarks using `executor.py`
   - Organizes results in version-specific directories
   
2. **Data Processing**:
   - `result_parser.py`: Converts JMH JSON to structured Python objects
   - `comparator.py`: Performs version and library comparisons
   
3. **Visualization & Reporting**:
   - `visualizer.py`: Creates charts with stacked bars and error margins
   - `report_generator.py`: Generates comprehensive markdown reports
   - `llm_prompt_builder.py`: Creates structured LLM analysis prompts
   
4. **Output Organization**:
   - All artifacts stored in `/results/<version>/` directories
   - Charts, reports, and prompts co-located with benchmark data
   - Ready for sharing and AI-powered analysis

## Directory Structure After Pipeline Run

```
results/
├── 1.5.0/                     # Baseline version directory
│   ├── *.json                  # Benchmark result files
│   ├── info.txt               # System information
│   └── graphs/                # Charts for this version
│       └── *.png
└── 1.6.1/                     # Comparison version directory
    ├── *.json                  # Benchmark result files
    ├── info.txt               # System information
    ├── graphs/                # Comparison charts
    │   └── *.png
    ├── kapper_benchmark_report_*.md    # Generated report
    └── llm_prompt_*.md        # LLM analysis prompts
```