#!/usr/bin/env python3
"""
Main entry point for the benchmark package.

Usage:
    python -m benchmark execution <version> [--quick]
    python -m benchmark analysis <baseline> <comparison>
    python -m benchmark reporting <baseline> <comparison>
    python -m benchmark pipeline <baseline> <comparison> [options]
"""

import sys
import argparse
from pathlib import Path

def main():
    """Main entry point for benchmark package."""
    # If no arguments, show help
    if len(sys.argv) == 1:
        sys.argv.append('--help')
        
    # Parse the subcommand first
    if len(sys.argv) < 2:
        print("Error: No subcommand specified")
        sys.exit(1)
        
    subcommand = sys.argv[1]
    
    if subcommand in ['-h', '--help']:
        parser = argparse.ArgumentParser(
            description="Kapper Benchmark Analysis Pipeline",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Subcommands:
  execution   Download and execute benchmarks for a specific version
  analysis    Parse and analyze benchmark results 
  reporting   Generate reports and analysis prompts
  pipeline    Complete end-to-end pipeline (equivalent to reporting/main.py)

Examples:
  python -m benchmark execution 1.6.1 --quick
  python -m benchmark pipeline 1.5.0 1.6.1 --skip-benchmarks
            """
        )
        parser.add_argument('subcommand', choices=['execution', 'analysis', 'reporting', 'pipeline'])
        parser.print_help()
        return
    
    if subcommand not in ['execution', 'analysis', 'reporting', 'pipeline']:
        print(f"Error: Unknown subcommand '{subcommand}'")
        print("Available: execution, analysis, reporting, pipeline")
        sys.exit(1)
    
    # Remove the subcommand from sys.argv and call the appropriate module
    remaining_args = sys.argv[2:]  # Skip 'python -m benchmark' and subcommand
    
    if subcommand == 'execution':
        from .execution.main import main as execution_main
        sys.argv = ['benchmark.execution'] + remaining_args
        execution_main()
    elif subcommand == 'analysis':
        from .analysis.main import main as analysis_main
        sys.argv = ['benchmark.analysis'] + remaining_args
        analysis_main()
    elif subcommand == 'reporting':
        from .reporting.main import main as reporting_main
        sys.argv = ['benchmark.reporting'] + remaining_args
        reporting_main()
    elif subcommand == 'pipeline':
        from .reporting.main import main as pipeline_main
        sys.argv = ['benchmark.pipeline'] + remaining_args
        pipeline_main()

if __name__ == '__main__':
    main()