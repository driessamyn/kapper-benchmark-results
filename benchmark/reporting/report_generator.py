#!/usr/bin/env python3
"""
Kapper Benchmark Report Generator

Generates comprehensive markdown reports from benchmark analysis results.
Combines version comparisons, library comparisons, and visualizations into a unified report.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# Handle imports for both standalone and module usage
try:
    from ..analysis.models import (
        VersionResults, VersionComparison, LibraryComparison,
        BenchmarkType, Library, DatabaseType, AutoMapperScenario, BenchmarkMode
    )
    from ..analysis.result_parser import ResultParser
    from ..analysis.comparator import BenchmarkComparator
    from ..analysis.visualizer import BenchmarkVisualizer
except ImportError:
    sys.path.append(str(Path(__file__).parent.parent))
    from analysis.models import (
        VersionResults, VersionComparison, LibraryComparison,
        BenchmarkType, Library, DatabaseType, AutoMapperScenario, BenchmarkMode
    )
    from analysis.result_parser import ResultParser
    from analysis.comparator import BenchmarkComparator
    from analysis.visualizer import BenchmarkVisualizer


class BenchmarkReportGenerator:
    """Generates comprehensive benchmark reports in markdown format."""
    
    def __init__(self, output_dir: Path = Path("reports")):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize analysis components
        self.parser = ResultParser()
        self.comparator = BenchmarkComparator()
        self.visualizer = BenchmarkVisualizer()
    
    def generate_full_report(self, baseline_version: str, comparison_version: str, 
                           results_dir: Path = Path("results")) -> Path:
        """Generate a complete benchmark report comparing two versions."""
        
        # Parse results for both versions
        baseline_results = self._load_version_results(results_dir, baseline_version)
        comparison_results = self._load_version_results(results_dir, comparison_version)
        
        if not baseline_results or not comparison_results:
            raise RuntimeError(f"Could not load results for {baseline_version} or {comparison_version}")
        
        # Perform comparisons
        version_comparison = self.comparator.compare_versions(baseline_results, comparison_results)
        baseline_library_comp = self.comparator.compare_libraries(baseline_results)
        comparison_library_comp = self.comparator.compare_libraries(comparison_results)
        
        # Generate visualizations
        version_charts = self.visualizer.create_version_comparison_charts(version_comparison)
        baseline_lib_charts = self.visualizer.create_library_comparison_charts(baseline_library_comp, baseline_results)
        comparison_lib_charts = self.visualizer.create_library_comparison_charts(comparison_library_comp, comparison_results)
        baseline_mapper_charts = self.visualizer.create_mapper_comparison_charts(baseline_results)
        comparison_mapper_charts = self.visualizer.create_mapper_comparison_charts(comparison_results)
        
        # Generate report
        report_content = self._build_full_report(
            baseline_results, comparison_results, version_comparison,
            baseline_library_comp, comparison_library_comp,
            version_charts, baseline_lib_charts, comparison_lib_charts,
            baseline_mapper_charts, comparison_mapper_charts
        )
        
        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"kapper_benchmark_report_{baseline_version}_vs_{comparison_version}_{timestamp}.md"
        report_path = self.output_dir / filename
        
        with open(report_path, 'w') as f:
            f.write(report_content)
        
        return report_path
    
    def _load_version_results(self, results_dir: Path, version: str) -> Optional[VersionResults]:
        """Load benchmark results for a specific version."""
        # First try version-specific directory structure
        version_path = results_dir / version
        if not version_path.exists():
            # Try alternative paths for legacy data
            alt_path = results_dir / f"{version}/01"
            if alt_path.exists():
                version_path = alt_path
            else:
                return None
        
        try:
            return self.parser.parse_version_results(version_path, version)
        except Exception as e:
            print(f"Error loading {version}: {e}")
            return None
    
    def _build_full_report(self, baseline_results: VersionResults, comparison_results: VersionResults,
                          version_comparison: VersionComparison, baseline_library_comp: LibraryComparison,
                          comparison_library_comp: LibraryComparison, version_charts: List[Path],
                          baseline_lib_charts: List[Path], comparison_lib_charts: List[Path],
                          baseline_mapper_charts: List[Path], comparison_mapper_charts: List[Path]) -> str:
        """Build the complete markdown report."""
        
        report = []
        
        # Title and metadata
        report.append(f"# Kapper Benchmark Report: {baseline_results.version} vs {comparison_results.version}")
        report.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        report.append("")
        
        # Executive Summary
        report.append("## Executive Summary")
        report.append("")
        summary = self._generate_executive_summary(version_comparison, baseline_library_comp, comparison_library_comp)
        report.append(summary)
        report.append("")
        
        # Table of Contents
        report.append("## Table of Contents")
        report.append("1. [Executive Summary](#executive-summary)")
        report.append("2. [Version Comparison](#version-comparison)")
        report.append("3. [Library Performance Analysis](#library-performance-analysis)")
        report.append("4. [AutoMapper Analysis](#automapper-analysis)")
        report.append("5. [System Information](#system-information)")
        report.append("6. [Detailed Results](#detailed-results)")
        report.append("7. [Visualizations](#visualizations)")
        report.append("")
        
        # Version Comparison Section
        report.append("## Version Comparison")
        report.append("")
        version_section = self._generate_version_comparison_section(version_comparison)
        report.append(version_section)
        report.append("")
        
        # Library Performance Analysis
        report.append("## Library Performance Analysis")
        report.append("")
        library_section = self._generate_library_comparison_section(baseline_library_comp, comparison_library_comp)
        report.append(library_section)
        report.append("")
        
        # AutoMapper Analysis
        report.append("## AutoMapper Analysis")
        report.append("")
        mapper_section = self._generate_mapper_section(baseline_results, comparison_results)
        report.append(mapper_section)
        report.append("")
        
        # System Information
        report.append("## System Information")
        report.append("")
        system_section = self._generate_system_info_section(baseline_results, comparison_results)
        report.append(system_section)
        report.append("")
        
        # Detailed Results Tables
        report.append("## Detailed Results")
        report.append("")
        detailed_section = self._generate_detailed_results_section(version_comparison)
        report.append(detailed_section)
        report.append("")
        
        # Visualizations
        report.append("## Visualizations")
        report.append("")
        viz_section = self._generate_visualizations_section(
            version_charts, baseline_lib_charts, comparison_lib_charts,
            baseline_mapper_charts, comparison_mapper_charts
        )
        report.append(viz_section)
        report.append("")
        
        return "\n".join(report)
    
    def _generate_executive_summary(self, version_comparison: VersionComparison,
                                  baseline_library_comp: LibraryComparison,
                                  comparison_library_comp: LibraryComparison) -> str:
        """Generate executive summary of key findings."""
        summary = []
        
        stats = version_comparison.summary_stats
        if stats:
            total = stats.get('total_comparisons', 0)
            improvements = stats.get('improvements', 0)
            regressions = stats.get('regressions', 0)
            avg_improvement = stats.get('avg_improvement_percent', 0)
            
            summary.append(f"**Version Performance**: Comparing {total} benchmarks, "
                         f"{version_comparison.comparison_version} shows {improvements} improvements "
                         f"and {regressions} regressions versus {version_comparison.baseline_version}. "
                         f"Average performance change: {avg_improvement:+.1f}%.")
            summary.append("")
        
        # Library competitive analysis
        baseline_stats = baseline_library_comp.summary_stats
        comparison_stats = comparison_library_comp.summary_stats
        
        if baseline_stats and comparison_stats:
            baseline_wins = baseline_stats.get('kapper_wins', 0)
            baseline_total = baseline_stats.get('total_comparisons', 1)
            comparison_wins = comparison_stats.get('kapper_wins', 0)
            comparison_total = comparison_stats.get('total_comparisons', 1)
            
            baseline_win_rate = (baseline_wins / baseline_total) * 100
            comparison_win_rate = (comparison_wins / comparison_total) * 100
            
            summary.append(f"**Competitive Position**: Kapper's win rate vs other libraries changed from "
                         f"{baseline_win_rate:.0f}% ({baseline_wins}/{baseline_total}) in "
                         f"{baseline_library_comp.version} to {comparison_win_rate:.0f}% "
                         f"({comparison_wins}/{comparison_total}) in {comparison_library_comp.version}.")
            summary.append("")
        
        return "\n".join(summary)
    
    def _generate_version_comparison_section(self, version_comparison: VersionComparison) -> str:
        """Generate version comparison analysis section."""
        section = []
        
        stats = version_comparison.summary_stats
        if not stats:
            section.append("No version comparison data available.")
            return "\n".join(section)
        
        section.append(f"### Performance Changes: {version_comparison.baseline_version} → {version_comparison.comparison_version}")
        section.append("")
        
        # Summary statistics
        total = stats.get('total_comparisons', 0)
        improvements = stats.get('improvements', 0)
        regressions = stats.get('regressions', 0)
        avg_improvement = stats.get('avg_improvement_percent', 0)
        max_improvement = stats.get('max_improvement_percent', 0)
        max_regression = stats.get('max_regression_percent', 0)
        
        section.append(f"- **Total Benchmarks**: {total}")
        section.append(f"- **Improvements**: {improvements} benchmarks")
        section.append(f"- **Regressions**: {regressions} benchmarks")
        section.append(f"- **Average Change**: {avg_improvement:+.1f}%")
        section.append(f"- **Best Improvement**: {max_improvement:+.1f}%")
        section.append(f"- **Worst Regression**: {max_regression:+.1f}%")
        section.append("")
        
        # Top improvements and regressions
        improvements_list = [c for c in version_comparison.version_comparisons if c.improvement_percent > 0]
        regressions_list = [c for c in version_comparison.version_comparisons if c.improvement_percent < 0]
        
        if improvements_list:
            section.append("### Top Improvements")
            section.append("")
            improvements_sorted = sorted(improvements_list, key=lambda x: x.improvement_percent, reverse=True)[:5]
            for i, comp in enumerate(improvements_sorted, 1):
                bench_name = comp.benchmark_type.value if comp.benchmark_type else 'Unknown'
                lib_name = comp.library.value if comp.library else 'Unknown'
                section.append(f"{i}. **{bench_name}** ({lib_name}): {comp.improvement_percent:+.1f}% "
                             f"({comp.baseline_score:.1f} → {comp.comparison_score:.1f} us/op)")
            section.append("")
        
        if regressions_list:
            section.append("### Notable Regressions")
            section.append("")
            regressions_sorted = sorted(regressions_list, key=lambda x: x.improvement_percent)[:5]
            for i, comp in enumerate(regressions_sorted, 1):
                bench_name = comp.benchmark_type.value if comp.benchmark_type else 'Unknown'
                lib_name = comp.library.value if comp.library else 'Unknown'
                section.append(f"{i}. **{bench_name}** ({lib_name}): {comp.improvement_percent:+.1f}% "
                             f"({comp.baseline_score:.1f} → {comp.comparison_score:.1f} us/op)")
            section.append("")
        
        return "\n".join(section)
    
    def _generate_library_comparison_section(self, baseline_comp: LibraryComparison,
                                           comparison_comp: LibraryComparison) -> str:
        """Generate library comparison analysis section."""
        section = []
        
        section.append(f"### Kapper vs Competitors")
        section.append("")
        
        # Analysis for each version
        for comp_name, comp in [("Baseline", baseline_comp), ("Comparison", comparison_comp)]:
            stats = comp.summary_stats
            if not stats:
                continue
            
            wins = stats.get('kapper_wins', 0)
            losses = stats.get('kapper_losses', 0)
            total = stats.get('total_comparisons', 0)
            avg_advantage = stats.get('avg_kapper_advantage_percent', 0)
            
            win_rate = (wins / total * 100) if total > 0 else 0
            
            section.append(f"**{comp_name} Version ({comp.version})**:")
            section.append(f"- Win Rate: {win_rate:.0f}% ({wins}/{total})")
            section.append(f"- Average Advantage: {avg_advantage:+.1f}%")
            section.append("")
        
        return "\n".join(section)
    
    def _generate_mapper_section(self, baseline_results: VersionResults,
                               comparison_results: VersionResults) -> str:
        """Generate AutoMapper analysis section."""
        section = []
        
        section.append("AutoMapper performance comparison across different scenarios:")
        section.append("")
        
        # Analyze each version's mapper results
        for version_name, results in [("Baseline", baseline_results), ("Comparison", comparison_results)]:
            if not results.mapper_avgt_results:
                continue
                
            section.append(f"**{version_name} Version ({results.version})**:")
            section.append("")
            
            # Sort mapper results by performance
            mapper_sorted = sorted(results.mapper_avgt_results, key=lambda x: x.primary_metric.score)
            
            for result in mapper_sorted:
                scenario = result.scenario.value if result.scenario else 'Unknown'
                score = result.primary_metric.score
                section.append(f"- {scenario}: {score:.1f} us/op")
            
            section.append("")
        
        return "\n".join(section)
    
    def _generate_system_info_section(self, baseline_results: VersionResults,
                                    comparison_results: VersionResults) -> str:
        """Generate system information section."""
        section = []
        
        # System info from baseline
        if baseline_results.info:
            section.append(f"**Baseline ({baseline_results.version})**:")
            for key, value in baseline_results.info.items():
                if key != 'full_content':
                    section.append(f"- {key.replace('_', ' ').title()}: {value}")
            section.append("")
        
        # System info from comparison
        if comparison_results.info:
            section.append(f"**Comparison ({comparison_results.version})**:")
            for key, value in comparison_results.info.items():
                if key != 'full_content':
                    section.append(f"- {key.replace('_', ' ').title()}: {value}")
            section.append("")
        
        return "\n".join(section)
    
    def _generate_detailed_results_section(self, version_comparison: VersionComparison) -> str:
        """Generate detailed results table."""
        section = []
        
        section.append("### Detailed Performance Results")
        section.append("")
        section.append("| Benchmark | Library | Database | Baseline (us/op) | Comparison (us/op) | Change (%) |")
        section.append("|-----------|---------|----------|------------------|--------------------|-----------:|")
        
        # Sort by improvement percentage (best first)
        sorted_comparisons = sorted(version_comparison.version_comparisons,
                                  key=lambda x: x.improvement_percent, reverse=True)
        
        for comp in sorted_comparisons:
            benchmark = comp.benchmark_type.value if comp.benchmark_type else 'Unknown'
            library = comp.library.value if comp.library else 'Unknown'
            database = comp.database_type.value if comp.database_type else 'Unknown'
            baseline = f"{comp.baseline_score:.1f}"
            comparison = f"{comp.comparison_score:.1f}"
            change = f"{comp.improvement_percent:+.1f}%"
            
            section.append(f"| {benchmark} | {library} | {database} | {baseline} | {comparison} | {change} |")
        
        section.append("")
        return "\n".join(section)
    
    def _generate_visualizations_section(self, version_charts: List[Path],
                                       baseline_lib_charts: List[Path],
                                       comparison_lib_charts: List[Path],
                                       baseline_mapper_charts: List[Path],
                                       comparison_mapper_charts: List[Path]) -> str:
        """Generate visualizations section with chart references."""
        section = []
        
        section.append("The following charts were generated for this report:")
        section.append("")
        
        if version_charts:
            section.append("### Version Comparison Charts")
            for chart in version_charts:
                section.append(f"- [{chart.name}]({chart.relative_to(Path.cwd())})")
            section.append("")
        
        if baseline_lib_charts or comparison_lib_charts:
            section.append("### Library Comparison Charts")
            all_lib_charts = baseline_lib_charts + comparison_lib_charts
            for chart in all_lib_charts:
                section.append(f"- [{chart.name}]({chart.relative_to(Path.cwd())})")
            section.append("")
        
        if baseline_mapper_charts or comparison_mapper_charts:
            section.append("### AutoMapper Charts")
            all_mapper_charts = baseline_mapper_charts + comparison_mapper_charts
            for chart in all_mapper_charts:
                section.append(f"- [{chart.name}]({chart.relative_to(Path.cwd())})")
            section.append("")
        
        return "\n".join(section)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate Kapper benchmark report")
    parser.add_argument("baseline_version", help="Baseline version (e.g., 1.5.0)")
    parser.add_argument("comparison_version", help="Comparison version (e.g., 1.6.1)")
    parser.add_argument("--results-dir", default="results", help="Results directory path")
    parser.add_argument("--output-dir", default="reports", help="Output directory for reports")
    
    args = parser.parse_args()
    
    generator = BenchmarkReportGenerator(output_dir=Path(args.output_dir))
    
    try:
        report_path = generator.generate_full_report(
            args.baseline_version,
            args.comparison_version,
            Path(args.results_dir)
        )
        print(f"Report generated: {report_path}")
    except Exception as e:
        print(f"Error generating report: {e}")
        sys.exit(1)