# Kapper Benchmark Analysis Pipeline

This repository contains a **complete automated benchmark analysis pipeline** for the Kapper Kotlin SQL mapping library, featuring **SSH disconnection protection** and **comprehensive cloud infrastructure** for performance testing against:

- **JDBC** (raw SQL)  
- **Hibernate** (JPA)
- **Ktorm** (Kotlin SQL DSL)

## ✨ Key Features

- **🔐 SSH Disconnection Protection**: Tmux session persistence for long-running benchmarks
- **☁️ Multi-region OCI Cloud Infrastructure**: Automated ARM instance deployment
- **🔄 Intelligent Instance Reuse**: Dynamic detection and reuse of running instances
- **📊 Complete Analysis Pipeline**: From raw benchmarks to AI-ready insights
- **🐳 Multi-Database Testing**: PostgreSQL (Testcontainers) + SQLite embedded
- **🤖 AI-Ready Output**: Structured LLM prompts for performance analysis

## 🚀 Quick Start

### Cloud Benchmark Execution (Recommended)

```bash
# Complete end-to-end pipeline with SSH protection
cd oci
./setup/run-benchmarks.sh 1.6.1 --baseline 1.5.0

# Quick testing with instance reuse
./setup/run-benchmarks.sh 1.6.1 --quick

# Monitor progress (reconnect after disconnection)
./monitor-benchmark.sh --reconnect
```

### Local Analysis Pipeline

```bash
# Complete end-to-end analysis pipeline
python -m benchmark.reporting.main 1.5.0 1.6.1

# Use existing results (skip download/execution)
python -m benchmark.reporting.main 1.5.0 1.6.1 --skip-benchmarks

# Generate only LLM analysis prompts
python -m benchmark.reporting.main 1.5.0 1.6.1 --prompt-only
```
## 🏗️ Architecture

### Benchmark Package Structure

```
benchmark/
├── execution/          # Benchmark execution
│   ├── release_manager.py   # Downloads GitHub releases
│   ├── executor.py         # JMH benchmark runner
│   └── main.py            # Execution entry point
├── analysis/           # Data processing  
│   ├── result_parser.py    # JMH JSON → structured data
│   ├── comparator.py      # Version/library comparisons
│   ├── visualizer.py      # Performance charts
│   └── main.py           # Analysis entry point
└── reporting/          # Report generation
    ├── report_generator.py  # Markdown reports
    ├── llm_prompt_builder.py # AI analysis prompts
    └── main.py             # Reporting entry point
```

### Directory Structure

```
results/
├── 1.5.0/                     # Baseline version
│   ├── *.json                 # Benchmark results
│   ├── info.txt              # System info
│   └── graphs/               # Performance charts
└── 1.6.1/                     # Comparison version
    ├── *.json                 # Benchmark results
    ├── info.txt              # System info
    ├── graphs/               # Performance charts
    ├── *.md                  # Analysis reports
    └── llm_prompt_*.md       # AI analysis prompts
```

## 📊 Benchmark Operations

The pipeline analyzes these database operations:

- **find100**: Retrieve 100 records
- **findById**: Single record lookup
- **insertSingleRow**: Insert one record  
- **simpleJoin**: Basic JOIN query
- **updateSingleRow**: Update one record
- **AutoMapper**: Various mapping scenarios

Across databases:
- **SQLite** (embedded)
- **PostgreSQL** (client-server)

And library variants:
- **JDBC**: Raw SQL queries (baseline)
- **KAPPER**: Full auto-mapping with reflection
- **KAPPER-NO-AUTOMAP**: Manual mapping (minimal reflection)
- **KAPPER-RECORD**: Record-based mapping (v1.6+, compile-time safety)
- **HIBERNATE**: JPA with Hibernate ORM
- **HIBERNATE-RECORD**: Hibernate with Records (v1.6+)
- **KTORM**: Kotlin SQL DSL framework

## 🛠️ Setup

### Prerequisites

- Python 3.8+
- Java 21+
- Git
- **For OCI Cloud Benchmarks**: OCI CLI configured with appropriate permissions

### Installation

```bash
# Clone repository
git clone <repository-url>
cd kapper-benchmar-results

# Install JDK 21
# macOS with Homebrew
brew install --cask temurin21

# Linux
curl -fsSL https://packages.adoptium.net/artifactory/api/gpg/key/public | sudo gpg --dearmor -o /usr/share/keyrings/adoptium.gpg
echo "deb [signed-by=/usr/share/keyrings/adoptium.gpg] https://packages.adoptium.net/artifactory/deb $(awk -F= '/^VERSION_CODENAME/{print$2}' /etc/os-release) main" | sudo tee /etc/apt/sources.list.d/adoptium.list
sudo apt-get update && sudo apt-get install temurin-21-jdk

# Set up Python environment (optional - cloud script will auto-create)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or  
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

## 📖 Usage

### Complete Analysis Pipeline

```bash
# Full end-to-end analysis (recommended)
python -m benchmark.reporting.main 1.5.0 1.6.1

# With options
python -m benchmark.reporting.main 1.5.0 1.6.1 \
  --skip-benchmarks \      # Use existing results
  --no-charts \           # Skip chart generation
  --technical-prompt      # Generate technical analysis prompt
```

### Available Options

- `--skip-benchmarks`: Skip download/execution, use existing results
- `--quick`: Fast benchmark mode (less accurate, for testing)
- `--force-rerun`: Re-download and re-run even if results exist
- `--no-charts`: Skip chart generation
- `--prompt-only`: Only generate LLM prompts
- `--technical-prompt`: Generate technical investigation prompt
- `--verbose`: Detailed output

### Individual Components

```bash
# Download benchmark suite only
python -m benchmark.execution.main 1.6.1 --download-only

# Run benchmarks only (local)  
python -m benchmark.execution.main 1.6.1

# Parse results only
python -m benchmark.analysis.main parse results/1.6.1 1.6.1

# Generate report only
python -m benchmark.reporting.main 1.5.0 1.6.1 --skip-benchmarks

# Cloud benchmark execution
./setup/run-benchmarks.sh 1.6.1 --baseline 1.5.0
```

## 📈 Analysis Output

The pipeline generates:

1. **📊 Performance Charts**:
   - Stacked bars (P50 + P99-P50)
   - Error bars with min/max ranges
   - Version comparisons
   - Library comparisons

2. **📝 Comprehensive Reports**:
   - Executive summary
   - Performance evolution analysis
   - Competitive positioning
   - Detailed results tables

3. **🤖 LLM Analysis Prompts**:
   - Structured performance analysis prompts
   - Technical investigation prompts
   - Ready for ChatGPT, Claude, etc.

## ☁️ OCI Cloud Infrastructure with SSH Protection

The project includes **automated OCI (Oracle Cloud Infrastructure) deployment** with **tmux session persistence** for SSH disconnection protection during long-running benchmarks.

### 🚀 Quick Start - Cloud Benchmarks

```bash
cd oci

# One-time setup (creates VCNs and networking across regions)
./setup/setup-prerequisites.sh

# Run full benchmarks with SSH protection (complete pipeline)
./setup/run-benchmarks.sh 1.6.1 --baseline 1.5.0

# Monitor progress (reconnect safely after disconnection)
./monitor-benchmark.sh --reconnect

# Quick testing mode with instance reuse
./setup/run-benchmarks.sh 1.6.1 --quick

# Monitor instances across all regions  
./setup/list-all-instances.sh

# Emergency cleanup - terminate all instances
./setup/stop-all-instances.sh
```

### 🔐 SSH Disconnection Protection

- **Tmux Session Persistence**: Benchmarks continue running if SSH disconnects
- **Reconnection Monitoring**: `./monitor-benchmark.sh --reconnect`
- **Real-time Progress**: Live benchmark output and progress tracking
- **Automatic Recovery**: Intelligent session detection and reconnection

### 🏗️ OCI Architecture

- **Free tier ARM instances**: VM.Standard.A1.Flex (4 OCPUs, 24GB RAM)  
- **Database testing**: PostgreSQL via Testcontainers + SQLite embedded
- **Dynamic capacity detection**: Finds available ARM capacity at runtime
- **Intelligent instance reuse**: Automatically reuses existing instances (5-8 min savings)
- **Python environment isolation**: Virtual environment with dependency management
- **Multi-region deployment**: us-phoenix-1, ca-toronto-1, uk-london-1

### 🔧 OCI Components

1. **`setup-prerequisites.sh`**: One-time infrastructure setup across regions
2. **`run-benchmarks.sh`**: Complete benchmark execution with tmux protection
3. **`monitor-benchmark.sh`**: Enhanced monitoring with reconnection capability
4. **`list-all-instances.sh`**: Multi-region instance monitoring
5. **`stop-all-instances.sh`**: Emergency cleanup with terminated instance handling

### 💰 Cost Management

- Uses **OCI Always Free** ARM A1.Flex instances (no charges)
- Automatic instance termination after benchmark completion
- IP-restricted security groups prevent unauthorized access
- Comprehensive monitoring across all regions
- Smart cleanup prevents resource waste

**📖 For detailed OCI setup and usage**: See [oci/README.md](oci/README.md)


## 📊 Available Data

The repository contains benchmark results for multiple Kapper versions:

- **Kapper 1.6.1**: Full benchmark suite with PostgreSQL + SQLite testing
- **Kapper 1.5.0**: Baseline comparison data for version analysis
- **Kapper 1.3**: Historical results with performance evolution data

## 🤝 Contributing

The pipeline is designed to be extended. Key extension points:

- **New benchmark operations**: Add to JMH suites
- **Additional libraries**: Extend comparator logic
- **Custom visualizations**: Modify visualizer components
- **Report formats**: Extend report generator
- **AI prompts**: Customize LLM prompt templates

## 🔗 Links

- [Kapper Library](https://github.com/kapper-project/kapper) 
- [JMH Documentation](https://openjdk.org/projects/code-tools/jmh/)
