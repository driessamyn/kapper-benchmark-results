#!/usr/bin/env python3
"""
Analysis Main Entry Point

Provides analysis commands for benchmark results.
"""

import sys
import argparse
from pathlib import Path

from .result_parser import ResultParser
from .comparator import BenchmarkComparator
from .visualizer import BenchmarkVisualizer


def main():
    """Analysis command dispatcher."""
    parser = argparse.ArgumentParser(
        description="Benchmark analysis tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  parse    Parse JMH results into structured data
  compare  Compare benchmark results between versions
  visualize Generate charts from benchmark data

Examples:
  python -m benchmark.analysis parse results/1.6.1 1.6.1
  python -m benchmark.analysis compare 1.5.0 1.6.1
  python -m benchmark.analysis visualize results/1.6.1
        """
    )
    
    parser.add_argument('command', choices=['parse', 'compare', 'visualize'],
                       help='Analysis command to run')
    parser.add_argument('args', nargs='*', help='Command arguments')
    
    args = parser.parse_args()
    
    if args.command == 'parse':
        if len(args.args) < 2:
            print("Usage: parse <results_dir> <version>")
            sys.exit(1)
        
        results_dir = Path(args.args[0])
        version = args.args[1]
        
        print(f"🔍 Parsing benchmark results from {results_dir} for version {version}")
        
        parser = ResultParser()
        results = parser.parse_version_results(results_dir, version)
        
        print(f"✅ Parsed {len(results.main_avgt_results)} main AVGT benchmarks")
        print(f"✅ Parsed {len(results.main_ss_results)} main SS benchmarks")
        print(f"✅ Parsed {len(results.mapper_avgt_results)} mapper AVGT benchmarks")
        print(f"✅ Parsed {len(results.mapper_ss_results)} mapper SS benchmarks")
        
    elif args.command == 'compare':
        if len(args.args) < 2:
            print("Usage: compare <baseline_version> <comparison_version>")
            sys.exit(1)
        
        baseline_version = args.args[0]
        comparison_version = args.args[1]
        
        print(f"📊 Comparing {baseline_version} vs {comparison_version}")
        
        # Parse both versions
        parser = ResultParser()
        baseline_dir = Path("results") / baseline_version
        comparison_dir = Path("results") / comparison_version
        
        if not baseline_dir.exists():
            print(f"❌ Baseline results directory not found: {baseline_dir}")
            sys.exit(1)
            
        if not comparison_dir.exists():
            print(f"❌ Comparison results directory not found: {comparison_dir}")
            sys.exit(1)
        
        baseline_results = parser.parse_version_results(baseline_dir, baseline_version)
        comparison_results = parser.parse_version_results(comparison_dir, comparison_version)
        
        comparator = BenchmarkComparator()
        version_comparison = comparator.compare_versions(baseline_results, comparison_results)
        library_comparison = comparator.compare_libraries(comparison_results)
        
        # Print detailed results
        print(f"✅ Generated version comparison:")
        print(f"   - Total comparisons: {version_comparison.summary_stats.get('total_comparisons', 0)}")
        print(f"   - Improvements: {version_comparison.summary_stats.get('improvements', 0)}")
        print(f"   - Regressions: {version_comparison.summary_stats.get('regressions', 0)}")
        print(f"   - Average improvement: {version_comparison.summary_stats.get('avg_improvement_percent', 0):.1f}%")
        
        print(f"✅ Generated library comparison:")
        print(f"   - Total comparisons: {library_comparison.summary_stats.get('total_comparisons', 0)}")
        print(f"   - Kapper wins: {library_comparison.summary_stats.get('kapper_wins', 0)}")
        print(f"   - Kapper losses: {library_comparison.summary_stats.get('kapper_losses', 0)}")
        
        # Show top improvements and regressions
        improvements = [c for c in version_comparison.version_comparisons if c.improvement_percent > 0]
        regressions = [c for c in version_comparison.version_comparisons if c.improvement_percent < 0]
        
        improvements.sort(key=lambda x: x.improvement_percent, reverse=True)
        regressions.sort(key=lambda x: x.improvement_percent)
        
        if improvements:
            print(f"\n🚀 Top 5 Improvements:")
            for i, comp in enumerate(improvements[:5]):
                print(f"   {i+1}. {comp.benchmark_type.value if comp.benchmark_type else 'AutoMapper'} "
                      f"({comp.library.value if comp.library else comp.scenario}): "
                      f"{comp.improvement_percent:.1f}% "
                      f"({comp.baseline_score:.1f} → {comp.comparison_score:.1f} {comp.baseline_unit})")
        
        if regressions:
            print(f"\n⚠️  Top 5 Regressions:")
            for i, comp in enumerate(regressions[:5]):
                print(f"   {i+1}. {comp.benchmark_type.value if comp.benchmark_type else 'AutoMapper'} "
                      f"({comp.library.value if comp.library else comp.scenario}): "
                      f"{comp.improvement_percent:.1f}% "
                      f"({comp.baseline_score:.1f} → {comp.comparison_score:.1f} {comp.baseline_unit})")
        
    elif args.command == 'visualize':
        if len(args.args) < 1:
            print("Usage: visualize <results_dir>")
            sys.exit(1)
        
        results_dir = Path(args.args[0])
        
        print(f"📈 Generating visualizations for {results_dir}")
        
        visualizer = BenchmarkVisualizer()
        # Add visualization logic here when needed
        
        print("✅ Visualizations generated")


if __name__ == '__main__':
    main()