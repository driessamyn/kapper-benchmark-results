#!/usr/bin/env python3
"""
Benchmark Execution Main Entry Point

Downloads benchmark suites and executes JMH benchmarks.
"""

import sys
import argparse
from pathlib import Path

from .release_manager import KapperReleaseManager as ReleaseManager
from .executor import BenchmarkExecutor

def main():
    """Execute benchmarks for a specific version."""
    parser = argparse.ArgumentParser(
        description="Download and execute Kapper benchmarks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m benchmark.execution 1.6.1
  python -m benchmark.execution 1.6.1 --quick
  python -m benchmark.execution 1.6.1 --results-dir /tmp/results
        """
    )
    
    parser.add_argument('version', help='Benchmark version to execute (e.g., 1.6.1)')
    parser.add_argument('--quick', action='store_true', 
                       help='Use quick mode (faster, less accurate)')
    parser.add_argument('--results-dir', default='results',
                       help='Directory to store results (default: results)')
    parser.add_argument('--force-rerun', action='store_true',
                       help='Re-download and re-run even if results exist')
    parser.add_argument('--download-only', action='store_true',
                       help='Only download, do not execute')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    print(f"🚀 Benchmark Execution Pipeline - Version {args.version}")
    print("=" * 50)
    
    # Initialize components
    manager = ReleaseManager()
    executor = BenchmarkExecutor(results_dir=args.results_dir)
    
    # Download benchmark suite
    print("📥 Downloading benchmark suite...")
    benchmark_dir = manager.download_version(args.version)
    print(f"✅ Benchmark suite ready: {benchmark_dir}")
    
    if args.download_only:
        print("📁 Download complete (--download-only specified)")
        return
    
    # Execute benchmarks
    print("🎯 Executing benchmarks...")
    results_path = executor.run_benchmark(
        benchmark_dir=benchmark_dir,
        version=args.version,
        quick=args.quick
    )
    
    print(f"✅ Benchmarks completed successfully!")
    print(f"📁 Results saved to: {results_path}")
    
    if args.verbose:
        print("\n📊 Results Summary:")
        result_files = list(Path(results_path).glob("*.json"))
        for result_file in result_files:
            size = result_file.stat().st_size / 1024  # KB
            print(f"   {result_file.name}: {size:.1f} KB")

if __name__ == '__main__':
    main()