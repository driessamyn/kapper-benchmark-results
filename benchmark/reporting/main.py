#!/usr/bin/env python3
"""
Kapper Benchmark Analysis Pipeline

Complete end-to-end benchmark pipeline that:
1. Downloads benchmark suites (if needed)
2. Runs benchmarks (if results don't exist)
3. Parses benchmark results
4. Performs comparisons (version and library)
5. Generates visualizations 
6. Creates markdown reports
7. Builds LLM analysis prompts

All artifacts are organized by version in /results/<version>/ directories.

Usage:
    python reporting/main.py 1.5.0 1.6.1                    # Full end-to-end pipeline
    python reporting/main.py 1.5.0 1.6.1 --no-charts       # Skip visualizations
    python reporting/main.py 1.5.0 1.6.1 --prompt-only     # Only generate LLM prompts
    python reporting/main.py 1.5.0 1.6.1 --skip-benchmarks # Skip download/execution
"""

import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# Handle imports for both standalone and module usage
try:
    from .report_generator import BenchmarkReportGenerator
    from .llm_prompt_builder import LLMPromptBuilder
except ImportError:
    sys.path.append(str(Path(__file__).parent.parent))
    from reporting.report_generator import BenchmarkReportGenerator
    from reporting.llm_prompt_builder import LLMPromptBuilder


def main():
    """Run the complete benchmark analysis pipeline."""
    parser = argparse.ArgumentParser(
        description="Run complete Kapper benchmark analysis pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 1.5.0 1.6.1                    # Full end-to-end pipeline
  %(prog)s 1.5.0 1.6.1 --no-charts       # Skip chart generation
  %(prog)s 1.5.0 1.6.1 --prompt-only     # Only generate LLM prompts
  %(prog)s 1.5.0 1.6.1 --skip-benchmarks # Skip download/execution, use existing results
        """
    )
    
    parser.add_argument("baseline_version", help="Baseline version (e.g., 1.5.0)")
    parser.add_argument("comparison_version", help="Comparison version (e.g., 1.6.1)")
    
    parser.add_argument("--results-dir", default="results", 
                       help="Base directory for all results (default: results)")
    
    parser.add_argument("--skip-benchmarks", action="store_true",
                       help="Skip download and benchmark execution (use existing results)")
    parser.add_argument("--quick", action="store_true",
                       help="Use quick benchmark mode (faster but less accurate)")
    parser.add_argument("--force-rerun", action="store_true",
                       help="Force re-download and re-run benchmarks even if results exist")
    
    parser.add_argument("--no-charts", action="store_true",
                       help="Skip chart generation (faster execution)")
    parser.add_argument("--prompt-only", action="store_true",
                       help="Only generate LLM prompts, skip full report")
    parser.add_argument("--technical-prompt", action="store_true",
                       help="Generate technical investigation prompt instead of performance analysis")
    
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    
    args = parser.parse_args()
    
    # Set up version-specific directory structure
    results_dir = Path(args.results_dir)
    results_dir.mkdir(exist_ok=True)
    
    baseline_version_dir = results_dir / args.baseline_version
    comparison_version_dir = results_dir / args.comparison_version
    
    # Create version directories
    baseline_version_dir.mkdir(exist_ok=True)
    comparison_version_dir.mkdir(exist_ok=True)
    
    # Set up output directories for each version
    comparison_output_dir = comparison_version_dir
    
    baseline_graphs_dir = baseline_version_dir / "graphs"
    comparison_graphs_dir = comparison_version_dir / "graphs"
    
    if not args.no_charts and not args.prompt_only:
        baseline_graphs_dir.mkdir(exist_ok=True)
        comparison_graphs_dir.mkdir(exist_ok=True)
    
    print(f"🚀 Kapper Benchmark Analysis Pipeline")
    print(f"   Baseline: {args.baseline_version} → {baseline_version_dir}")
    print(f"   Comparison: {args.comparison_version} → {comparison_version_dir}")
    if not args.no_charts and not args.prompt_only:
        print(f"   Charts: {baseline_graphs_dir}, {comparison_graphs_dir}")
    print()
    
    start_time = datetime.now()
    
    try:
        # Step 1: Download and run benchmarks if needed
        if not args.skip_benchmarks:
            # Check if results already exist
            baseline_needs_run = _needs_benchmark_run(baseline_version_dir, args.baseline_version, args.force_rerun)
            comparison_needs_run = _needs_benchmark_run(comparison_version_dir, args.comparison_version, args.force_rerun)
            
            if baseline_needs_run or comparison_needs_run:
                if args.verbose:
                    print("📥 Downloading and running benchmarks...")
                
                # Download and run baseline if needed
                if baseline_needs_run:
                    _download_and_run_benchmark(args.baseline_version, baseline_version_dir, args.quick, args.verbose)
                else:
                    print(f"✅ Baseline {args.baseline_version} results already exist")
                
                # Download and run comparison if needed
                if comparison_needs_run:
                    _download_and_run_benchmark(args.comparison_version, comparison_version_dir, args.quick, args.verbose)
                else:
                    print(f"✅ Comparison {args.comparison_version} results already exist")
            else:
                print(f"✅ Both benchmark results already exist, skipping download/execution")
        else:
            print(f"⏭️  Skipping benchmark download/execution")
        
        # Validate that results exist
        if not _has_benchmark_results(baseline_version_dir):
            print(f"❌ No benchmark results found for baseline {args.baseline_version}")
            print(f"   Try running without --skip-benchmarks")
            sys.exit(1)
        
        if not _has_benchmark_results(comparison_version_dir):
            print(f"❌ No benchmark results found for comparison {args.comparison_version}")
            print(f"   Try running without --skip-benchmarks")
            sys.exit(1)
        # Generate LLM prompts in comparison version directory
        if args.verbose:
            print("📝 Generating LLM analysis prompts...")
        
        prompt_builder = LLMPromptBuilder(comparison_output_dir)
        
        if args.technical_prompt:
            prompt_content = prompt_builder.build_technical_investigation_prompt(
                args.baseline_version, args.comparison_version, results_dir
            )
            prompt_path = prompt_builder.save_prompt(
                prompt_content, "technical", args.baseline_version, args.comparison_version
            )
        else:
            prompt_content = prompt_builder.build_performance_analysis_prompt(
                args.baseline_version, args.comparison_version, results_dir
            )
            prompt_path = prompt_builder.save_prompt(
                prompt_content, "performance", args.baseline_version, args.comparison_version
            )
        
        print(f"✅ LLM prompt generated: {prompt_path}")
        
        # If prompt-only mode, exit here
        if args.prompt_only:
            print(f"\n🎯 Prompt-only mode completed in {datetime.now() - start_time}")
            print(f"\n📋 Next steps:")
            print(f"   1. Review the generated prompt: {prompt_path}")
            print(f"   2. Use it with your preferred LLM (ChatGPT, Claude, etc.)")
            print(f"   3. Paste the benchmark data and get AI-powered analysis")
            return
        
        # Generate full report with charts in comparison version directory
        if args.verbose:
            print("📊 Generating comprehensive benchmark report...")
        
        # Set up visualizer with comparison version graphs directory if not skipping charts
        if args.no_charts:
            if args.verbose:
                print("⏭️  Skipping chart generation...")
        else:
            if args.verbose:
                print("📈 Generating performance charts...")
        
        report_generator = BenchmarkReportGenerator(comparison_output_dir)
        if not args.no_charts:
            # Override the visualizer's output directory to use comparison version graphs
            report_generator.visualizer = BenchmarkVisualizerWrapper(comparison_graphs_dir)
        
        report_path = report_generator.generate_full_report(
            args.baseline_version, args.comparison_version, results_dir
        )
        
        print(f"✅ Benchmark report generated: {report_path}")
        
        if not args.no_charts:
            chart_count = len(list(comparison_graphs_dir.glob("*.png")))
            if chart_count > 0:
                print(f"✅ Generated {chart_count} performance charts in: {comparison_graphs_dir}")
        
        duration = datetime.now() - start_time
        print(f"\n🎉 Analysis pipeline completed in {duration}")
        
        # Print summary of outputs
        print(f"\n📋 Generated Files:")
        print(f"   📄 Report: {report_path}")
        print(f"   🤖 LLM Prompt: {prompt_path}")
        if not args.no_charts:
            print(f"   📊 Charts: {comparison_graphs_dir}/*.png")
        
        print(f"\n📁 Version Directories:")
        print(f"   📂 Baseline ({args.baseline_version}): {baseline_version_dir}")
        print(f"   📂 Comparison ({args.comparison_version}): {comparison_version_dir}")
        
        print(f"\n🔍 Next Steps:")
        print(f"   1. Review the benchmark report: {report_path}")
        print(f"   2. Use the LLM prompt for AI-powered analysis: {prompt_path}")
        print(f"   3. Share charts and insights with your team")
        if not args.no_charts and chart_count == 0:
            print(f"   ⚠️  Note: No charts were generated. Data may lack variation (quick mode results?)")
            print(f"      Consider running full benchmarks (without --quick) for better visualizations.")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _needs_benchmark_run(version_dir: Path, version: str, force_rerun: bool) -> bool:
    """Check if a benchmark run is needed for a version.
    
    Args:
        version_dir: Directory where benchmark results should be stored
        version: Version string (for logging purposes)
        force_rerun: Whether to force a rerun even if results exist
    """
    if force_rerun:
        return True
    
    # Check for main benchmark results
    has_main_results = any([
        (version_dir / "jmh-result.json").exists(),
        (version_dir / "benchmark_results.json").exists(),
        len(list(version_dir.glob("*avgt*.json"))) > 0
    ])
    
    # Check for mapper benchmark results
    has_mapper_results = any([
        (version_dir / "mapper-jmh-result.json").exists(),
        (version_dir / "mapper_benchmark_results.json").exists(),
        len(list(version_dir.glob("*mapper*.json"))) > 0
    ])
    
    return not (has_main_results and has_mapper_results)


def _has_benchmark_results(version_dir: Path) -> bool:
    """Check if a version directory has benchmark results."""
    # Look for JSON result files
    json_files = list(version_dir.glob("*.json"))
    return len(json_files) > 0


def _download_and_run_benchmark(version: str, version_dir: Path, quick: bool, verbose: bool):
    """Download and run benchmarks for a specific version."""
    if verbose:
        print(f"  📥 Downloading benchmark suite for {version}...")
    
    # Download the benchmark suite
    download_cmd = ["python", "scripts/release_manager.py", version]
    download_result = subprocess.run(download_cmd, capture_output=True, text=True)
    
    if download_result.returncode != 0:
        print(f"❌ Failed to download benchmark suite for {version}")
        print(f"   Command: {' '.join(download_cmd)}")
        print(f"   Error: {download_result.stderr}")
        sys.exit(1)
    
    if verbose:
        print(f"  🏃 Running benchmarks for {version}...")
    
    # Run the benchmarks
    downloads_dir = Path("downloads")
    benchmark_dir = downloads_dir / f"kapper-benchmarks-{version}"
    
    if not benchmark_dir.exists():
        print(f"❌ Benchmark directory not found: {benchmark_dir}")
        sys.exit(1)
    
    # Build executor command
    executor_cmd = ["python", "scripts/executor.py", str(benchmark_dir), version]
    if quick:
        executor_cmd.append("--quick")
    
    executor_result = subprocess.run(executor_cmd, capture_output=False, text=True)
    
    if executor_result.returncode != 0:
        print(f"❌ Failed to run benchmarks for {version}")
        print(f"   Command: {' '.join(executor_cmd)}")
        sys.exit(1)
    
    # Move results to version-specific directory
    results_source = Path("results") / version
    if results_source.exists() and results_source != version_dir:
        import shutil
        # Copy all files from results/<version>/ to the version directory
        for item in results_source.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(results_source)
                target_path = version_dir / rel_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target_path)
        
        # Remove the old results directory if it's different
        if results_source != version_dir:
            shutil.rmtree(results_source)
    
    print(f"✅ Benchmarks completed for {version}")


class BenchmarkVisualizerWrapper:
    """Wrapper to allow custom output directory for visualizer."""
    
    def __init__(self, graphs_dir: Path):
        # Import here to avoid circular dependencies
        sys.path.append(str(Path(__file__).parent.parent))
        from analysis.visualizer import BenchmarkVisualizer
        self.visualizer = BenchmarkVisualizer(output_dir=graphs_dir)
    
    def __getattr__(self, name):
        return getattr(self.visualizer, name)


if __name__ == "__main__":
    main()