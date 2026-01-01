#!/usr/bin/env python3
"""
Kapper Benchmark Visualizer

Creates charts and graphs for benchmark results and comparisons.
Supports both version comparisons and library comparisons.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import seaborn as sns
import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
try:
    from .models import (
        VersionResults, VersionComparison, LibraryComparison,
        VersionComparisonResult, LibraryComparisonResult,
        BenchmarkType, Library, DatabaseType, AutoMapperScenario, BenchmarkMode
    )
except ImportError:
    from models import (
        VersionResults, VersionComparison, LibraryComparison,
        VersionComparisonResult, LibraryComparisonResult,
        BenchmarkType, Library, DatabaseType, AutoMapperScenario, BenchmarkMode
    )


class BenchmarkVisualizer:
    """Creates visualizations for benchmark results."""
    
    def __init__(self, output_dir: Path = Path("graphs")):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Set up plotting style
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
    
    def create_version_comparison_charts(self, comparison: VersionComparison) -> List[Path]:
        """Create charts comparing two Kapper versions using absolute values with bars."""
        created_files = []
        
        # Main benchmark comparisons - only Kapper libraries, grouped by operation
        main_comparisons = [c for c in comparison.version_comparisons 
                           if c.benchmark_type != BenchmarkType.AUTO_MAPPER and
                           c.library and 'KAPPER' in c.library.value]
        if main_comparisons:
            chart = self._create_kapper_version_comparison_chart(comparison, main_comparisons)
            if chart:
                created_files.append(chart)
        
        return created_files
    
    def create_library_comparison_charts(self, comparison: LibraryComparison, version_results: VersionResults = None) -> List[Path]:
        """Create charts comparing Kapper against other libraries using absolute values."""
        created_files = []
        
        # Library comparisons - absolute values by benchmark type
        for benchmark_type in set(c.benchmark_type for c in comparison.library_comparisons if c.benchmark_type):
            chart = self._create_absolute_library_chart(comparison, benchmark_type, version_results)
            if chart:
                created_files.append(chart)
        
        return created_files
    
    def create_mapper_comparison_charts(self, version_results: VersionResults) -> List[Path]:
        """Create charts comparing different mapper types within a version."""
        created_files = []
        
        # AVGT mapper comparisons
        if version_results.mapper_avgt_results:
            avgt_chart = self._create_mapper_chart(version_results, BenchmarkMode.AVGT)
            if avgt_chart:
                created_files.append(avgt_chart)
        
        # SS (cold start) mapper comparisons
        if version_results.mapper_ss_results:
            ss_chart = self._create_mapper_chart(version_results, BenchmarkMode.SS)
            if ss_chart:
                created_files.append(ss_chart)
        
        return created_files
    
    def _create_absolute_benchmark_chart(self, comparison: VersionComparison, 
                                        comparisons: List[VersionComparisonResult], 
                                        benchmark_type: BenchmarkType, chart_type: str) -> Optional[Path]:
        """Create absolute value bar chart for a specific benchmark type."""
        # Filter comparisons for this benchmark type
        filtered_comps = [c for c in comparisons if c.benchmark_type == benchmark_type]
        if not filtered_comps:
            return None
        
        # Prepare data with percentiles
        data = []
        for c in filtered_comps:
            # Get percentile data from the original results
            baseline_result = self._find_original_result(comparison, c, is_baseline=True)
            comparison_result = self._find_original_result(comparison, c, is_baseline=False)
            
            # Add baseline version data
            p50_baseline = baseline_result.primary_metric.score_percentiles.get('50.0', c.baseline_score) if baseline_result else c.baseline_score
            p99_baseline = baseline_result.primary_metric.score_percentiles.get('99.0', c.baseline_score) if baseline_result else c.baseline_score
            error_baseline = baseline_result.primary_metric.score_error if baseline_result else None
            
            data.append({
                'library': c.library.value if c.library else 'Unknown',
                'version': comparison.baseline_version,
                'p50': p50_baseline,
                'p99': p99_baseline,
                'error': error_baseline,
                'database': c.database_type.value if c.database_type else 'Unknown'
            })
            
            # Add comparison version data
            p50_comparison = comparison_result.primary_metric.score_percentiles.get('50.0', c.comparison_score) if comparison_result else c.comparison_score
            p99_comparison = comparison_result.primary_metric.score_percentiles.get('99.0', c.comparison_score) if comparison_result else c.comparison_score
            error_comparison = comparison_result.primary_metric.score_error if comparison_result else None
            
            data.append({
                'library': c.library.value if c.library else 'Unknown',
                'version': comparison.comparison_version,
                'p50': p50_comparison,
                'p99': p99_comparison,
                'error': error_comparison,
                'database': c.database_type.value if c.database_type else 'Unknown'
            })
        
        df = pd.DataFrame(data)
        
        # Create separate charts for each database type
        created_files = []
        for db_type in df['database'].unique():
            db_data = df[df['database'] == db_type]
            
            fig, ax = plt.subplots(figsize=(14, 8))
            
            # Sort all data by P50 (fastest first)
            db_data_sorted = db_data.sort_values('p50')
            
            x_positions = []
            x_labels = []
            
            for i, (_, row) in enumerate(db_data_sorted.iterrows()):
                x_positions.append(i)
                x_labels.append(f"{row['library']}\n{row['version']}")
                
                # Create stacked bar: P50 base, then P99-P50 stack
                p50 = row['p50']
                p99_additional = max(0, row['p99'] - row['p50'])  # Additional time from P50 to P99
                
                # P50 bar (base)
                bar1 = ax.bar(i, p50, width=0.8, color=f'C{i % 10}', alpha=0.8, label='P50' if i == 0 else "")
                
                # P99 additional bar (stacked on top)
                if p99_additional > 0:
                    bar2 = ax.bar(i, p99_additional, bottom=p50, width=0.8, 
                                color=f'C{i % 10}', alpha=0.4, label='P99 additional' if i == 0 else "")
                
                # Add error bar if available
                if row['error'] is not None and row['error'] > 0:
                    ax.errorbar(i, p50, yerr=row['error'], fmt='none', 
                              color='red', capsize=4, linewidth=1.5, alpha=0.8)
                
                # Add value labels
                ax.text(i, p50 + p50 * 0.01, f'{p50:.1f}', ha='center', va='bottom', 
                       fontsize=9, fontweight='bold')
                if p99_additional > 0:
                    ax.text(i, row['p99'] + row['p99'] * 0.01, f'{row["p99"]:.1f}', 
                           ha='center', va='bottom', fontsize=8, style='italic')
            
            ax.set_xticks(x_positions)
            ax.set_xticklabels(x_labels, rotation=45, ha='right')
            ax.set_ylabel(f'Time ({filtered_comps[0].baseline_unit})')
            ax.set_title(f'{benchmark_type.value} - {db_type} Database\n{comparison.baseline_version} vs {comparison.comparison_version}\n(Bars: P50 solid, P99 additional faded, Error bars in red)')
            
            # Add legend
            ax.legend(loc='upper left')
            
            # Add grid for easier reading
            ax.grid(True, alpha=0.3, axis='y')
            
            plt.tight_layout()
            
            filename = f"{benchmark_type.value}_{db_type}_{comparison.baseline_version}_vs_{comparison.comparison_version}.png"
            filepath = self.output_dir / filename
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            created_files.append(filepath)
        
        return created_files[0] if created_files else None
    
    def _create_kapper_version_comparison_chart(self, comparison: VersionComparison, 
                                              comparisons: List[VersionComparisonResult]) -> Optional[Path]:
        """Create version comparison chart showing only Kapper operations grouped by benchmark type."""
        if not comparisons:
            return None
        
        # Group by database type for separate charts
        by_database = {}
        for c in comparisons:
            db_key = c.database_type.value if c.database_type else 'Unknown'
            if db_key not in by_database:
                by_database[db_key] = []
            by_database[db_key].append(c)
        
        created_files = []
        for db_type, db_comparisons in by_database.items():
            # Group by benchmark type
            by_benchmark = {}
            for c in db_comparisons:
                bench_key = c.benchmark_type.value if c.benchmark_type else 'Unknown'
                if bench_key not in by_benchmark:
                    by_benchmark[bench_key] = []
                by_benchmark[bench_key].append(c)
            
            fig, ax = plt.subplots(figsize=(14, 8))
            
            # Sort benchmark types for consistent ordering
            benchmark_types = sorted(by_benchmark.keys())
            x_positions = []
            x_labels = []
            
            for i, bench_type in enumerate(benchmark_types):
                bench_comparisons = by_benchmark[bench_type]
                
                for j, comp in enumerate(bench_comparisons):
                    # For now, use the average score as both P50 and P99
                    # TODO: Get actual percentile data from original results
                    baseline_p50 = comp.baseline_score
                    baseline_p99 = comp.baseline_score  
                    baseline_error = None  # TODO: Get error from original results
                    comparison_p50 = comp.comparison_score  
                    comparison_p99 = comp.comparison_score
                    comparison_error = None  # TODO: Get error from original results
                    
                    # Position bars: baseline and comparison side by side
                    x_base = i * 3  # Space between benchmark groups
                    x_baseline = x_base - 0.2
                    x_comparison = x_base + 0.2
                    
                    # Baseline version bars (stacked P50 + P99-P50)
                    p99_additional_baseline = max(0, baseline_p99 - baseline_p50)
                    ax.bar(x_baseline, baseline_p50, width=0.35, color='#4682B4', alpha=0.8, 
                          label=f'{comparison.baseline_version} P50' if i == 0 and j == 0 else "")
                    if p99_additional_baseline > 0:
                        ax.bar(x_baseline, p99_additional_baseline, bottom=baseline_p50, width=0.35, 
                              color='#4682B4', alpha=0.4, 
                              label=f'{comparison.baseline_version} P99' if i == 0 and j == 0 else "")
                    
                    # Comparison version bars (stacked P50 + P99-P50)
                    p99_additional_comparison = max(0, comparison_p99 - comparison_p50)
                    ax.bar(x_comparison, comparison_p50, width=0.35, color='#2E8B57', alpha=0.8,
                          label=f'{comparison.comparison_version} P50' if i == 0 and j == 0 else "")
                    if p99_additional_comparison > 0:
                        ax.bar(x_comparison, p99_additional_comparison, bottom=comparison_p50, width=0.35,
                              color='#2E8B57', alpha=0.4,
                              label=f'{comparison.comparison_version} P99' if i == 0 and j == 0 else "")
                    
                    # Add error bars if available
                    if baseline_error is not None and baseline_error > 0:
                        ax.errorbar(x_baseline, baseline_p50, yerr=baseline_error, fmt='none', 
                                  color='black', capsize=6, linewidth=2, alpha=0.8, capthick=2)
                    
                    if comparison_error is not None and comparison_error > 0:
                        ax.errorbar(x_comparison, comparison_p50, yerr=comparison_error, fmt='none', 
                                  color='black', capsize=6, linewidth=2, alpha=0.8, capthick=2)
                    
                    # Add value labels
                    ax.text(x_baseline, baseline_p50 + baseline_p50 * 0.01, f'{baseline_p50:.1f}', 
                           ha='center', va='bottom', fontsize=9, fontweight='bold')
                    ax.text(x_comparison, comparison_p50 + comparison_p50 * 0.01, f'{comparison_p50:.1f}', 
                           ha='center', va='bottom', fontsize=9, fontweight='bold')
                    
                    # Store positions and labels
                    if j == 0:  # Only add label once per benchmark type
                        x_positions.append(x_base)
                        x_labels.append(f"{bench_type}\n{comp.library.value}")
            
            ax.set_xticks(x_positions)
            ax.set_xticklabels(x_labels, rotation=45, ha='right')
            ax.set_ylabel(f'Time (us/op)')
            ax.set_title(f'Kapper Version Comparison - {db_type} Database\n{comparison.baseline_version} vs {comparison.comparison_version}')
            
            # Add legend
            ax.legend(loc='upper left')
            
            # Add grid for easier reading
            ax.grid(True, alpha=0.3, axis='y')
            
            plt.tight_layout()
            
            filename = f"kapper_version_comparison_{db_type}_{comparison.baseline_version}_vs_{comparison.comparison_version}.png"
            filepath = self.output_dir / filename
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            created_files.append(filepath)
        
        return created_files[0] if created_files else None
    
    def _find_original_result(self, comparison: VersionComparison, comp_result: VersionComparisonResult, is_baseline: bool) -> Optional[Any]:
        """Find the original benchmark result to get percentile data."""
        # For now, return None since we need to modify the comparator to pass through the original results
        # This will be handled by using the average score as fallback in the calling code
        return None
    
    def _create_absolute_library_chart(self, comparison: LibraryComparison, 
                                     benchmark_type: BenchmarkType, version_results: VersionResults = None) -> Optional[Path]:
        """Create absolute value bar chart comparing libraries for a specific benchmark."""
        # Filter comparisons for this benchmark type
        filtered_comps = [c for c in comparison.library_comparisons if c.benchmark_type == benchmark_type]
        if not filtered_comps:
            return None
        
        # Prepare data including Kapper with percentiles
        data = []
        for c in filtered_comps:
            # Find original results to get percentile data
            kapper_result = None
            competitor_result = None
            
            if version_results:
                for result in version_results.main_avgt_results:
                    if (result.benchmark_type == c.benchmark_type and 
                        result.database_type == c.database_type and
                        result.rows == c.rows):
                        if result.library and 'KAPPER' in result.library.value:
                            kapper_result = result
                        elif result.library == c.competitor_library:
                            competitor_result = result
            
            # Add Kapper data with percentiles
            kapper_p50 = kapper_result.primary_metric.score_percentiles.get('50.0', c.kapper_score) if kapper_result else c.kapper_score
            kapper_p99 = kapper_result.primary_metric.score_percentiles.get('99.0', c.kapper_score) if kapper_result else c.kapper_score
            kapper_error = kapper_result.primary_metric.score_error if kapper_result else None
            
            data.append({
                'library': 'KAPPER',
                'p50': kapper_p50,
                'p99': kapper_p99,
                'error': kapper_error,
                'database': c.database_type.value if c.database_type else 'Unknown',
                'rows': c.rows
            })
            
            # Add competitor data with percentiles
            comp_p50 = competitor_result.primary_metric.score_percentiles.get('50.0', c.competitor_score) if competitor_result else c.competitor_score
            comp_p99 = competitor_result.primary_metric.score_percentiles.get('99.0', c.competitor_score) if competitor_result else c.competitor_score
            comp_error = competitor_result.primary_metric.score_error if competitor_result else None
            
            data.append({
                'library': c.competitor_library.value,
                'p50': comp_p50,
                'p99': comp_p99,
                'error': comp_error,
                'database': c.database_type.value if c.database_type else 'Unknown',
                'rows': c.rows
            })
        
        df = pd.DataFrame(data)
        
        # Create separate charts for each database/rows combination
        created_files = []
        for (db_type, rows), group_data in df.groupby(['database', 'rows']):
            # Sort by P50 (fastest first)
            group_data = group_data.sort_values('p50')
            
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # Create stacked bars for P50 and P99
            libraries = group_data['library'].values
            p50_values = group_data['p50'].values
            p99_values = group_data['p99'].values
            errors = group_data['error'].values
            
            for i, (lib, p50, p99, error) in enumerate(zip(libraries, p50_values, p99_values, errors)):
                # Color Kapper bars differently
                color = '#2E8B57' if lib == 'KAPPER' else '#4682B4'
                
                # Create stacked bar: P50 as base, P99-P50 on top
                p99_additional = max(0, p99 - p50)
                
                # P50 bar (base) - this is the bottom part of the stack
                bar1 = ax.bar(i, p50, width=0.8, color=color, alpha=0.8, 
                             edgecolor='black' if lib == 'KAPPER' else None,
                             linewidth=2 if lib == 'KAPPER' else None,
                             label='P50' if i == 0 else "")
                
                # P99 additional bar (stacked on top of P50)
                if p99_additional > 0:
                    bar2 = ax.bar(i, p99_additional, bottom=p50, width=0.8, 
                                color=color, alpha=0.4, 
                                edgecolor='black' if lib == 'KAPPER' else None,
                                linewidth=1 if lib == 'KAPPER' else None,
                                label='P99 tail' if i == 0 else "")
                
                # Add error bar (min/max style) if available
                if error is not None and error > 0:
                    # Create error bar showing ±error range
                    ax.errorbar(i, p50, yerr=error, fmt='none', 
                              color='black', capsize=8, linewidth=3, alpha=0.8,
                              capthick=3)
                
                # Add value labels
                # P50 label at the P50 level
                ax.text(i, p50 + p50 * 0.01, f'{p50:.1f}', ha='center', va='bottom', 
                       fontsize=10, fontweight='bold')
                
                # P99 label at the top of the stack
                if p99_additional > 0:
                    ax.text(i, p99 + p99 * 0.01, f'{p99:.1f}', ha='center', va='bottom', 
                           fontsize=8, style='italic', alpha=0.8)
            
            ax.set_xticks(range(len(libraries)))
            ax.set_xticklabels(libraries, rotation=45, ha='right')
            ax.set_ylabel(f'Time ({filtered_comps[0].score_unit})')
            ax.set_title(f'{benchmark_type.value} - {db_type} Database ({rows} rows)\nVersion {comparison.version}\n(Bars: P50 solid, P99 additional faded, Error bars in red)')
            
            # Add legend
            ax.legend(loc='upper left')
            
            # Add grid for easier reading
            ax.grid(True, alpha=0.3, axis='y')
            
            plt.tight_layout()
            
            filename = f"{benchmark_type.value}_{db_type}_{rows}rows_libraries_{comparison.version}.png"
            filepath = self.output_dir / filename
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            
            created_files.append(filepath)
        
        return created_files[0] if created_files else None
    
    def _create_mapper_chart(self, version_results: VersionResults, mode: BenchmarkMode) -> Optional[Path]:
        """Create chart comparing different mapper scenarios."""
        results = version_results.mapper_avgt_results if mode == BenchmarkMode.AVGT else version_results.mapper_ss_results
        if not results:
            return None
        
        # Prepare data
        data = []
        for result in results:
            data.append({
                'scenario': result.scenario.value if result.scenario else 'Unknown',
                'score': result.primary_metric.score,
                'error': result.primary_metric.score_error,
                'rows': result.rows
            })
        
        df = pd.DataFrame(data)
        
        # Sort by score (fastest first)
        df = df.sort_values('score')
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Create bars
        scenarios = df['scenario'].values
        scores = df['score'].values
        errors = df['error'].values
        
        # For mapper charts, we'll use the score as P50 and create a simple bar
        # (We don't have separate P99 data for mapper results in the current structure)
        for i, (scenario, score, error) in enumerate(zip(scenarios, scores, errors)):
            # Create simple bar for mapper (P50 equivalent)
            bar = ax.bar(i, score, width=0.8, color='#8B4513', alpha=0.8,
                        label='Average time' if i == 0 else "")
            
            # Add error bar if available
            if error is not None and error > 0:
                ax.errorbar(i, score, yerr=error, fmt='none', 
                          color='black', capsize=6, linewidth=2, alpha=0.8, capthick=2)
            
            # Add value label
            ax.text(i, score + score * 0.01, f'{score:.1f}', 
                   ha='center', va='bottom', fontsize=10, fontweight='bold')
        
        ax.set_xticks(range(len(scenarios)))
        ax.set_xticklabels(scenarios, rotation=45, ha='right')
        ax.set_ylabel(f'Time ({results[0].primary_metric.score_unit})')
        
        mode_text = "Average Time" if mode == BenchmarkMode.AVGT else "Cold Start"
        ax.set_title(f'AutoMapper Scenarios - {mode_text}\nVersion {version_results.version}')
        
        # Add grid for easier reading
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        filename = f"mapper_{mode.value}_{version_results.version}.png"
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        return filepath
    
    def _old_create_version_summary_chart(self, comparison: VersionComparison) -> Optional[Path]:
        """Create summary chart showing overall version improvements."""
        stats = comparison.summary_stats
        if not stats:
            return None
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # Left: Improvement/Regression counts
        categories = ['Improvements', 'Regressions', 'No Change']
        counts = [stats.get('improvements', 0), stats.get('regressions', 0), stats.get('no_change', 0)]
        colors = ['green', 'red', 'gray']
        
        ax1.bar(categories, counts, color=colors, alpha=0.7)
        ax1.set_title(f'Version Comparison: {comparison.baseline_version} → {comparison.comparison_version}')
        ax1.set_ylabel('Number of Benchmarks')
        
        # Add count labels on bars
        for i, count in enumerate(counts):
            if count > 0:
                ax1.text(i, count + 0.1, str(count), ha='center', va='bottom')
        
        # Right: Distribution of improvement percentages
        improvements = [c.improvement_percent for c in comparison.version_comparisons]
        if improvements:
            ax2.hist(improvements, bins=20, alpha=0.7, color='blue', edgecolor='black')
            ax2.axvline(x=0, color='red', linestyle='--', label='No Change')
            ax2.axvline(x=np.mean(improvements), color='orange', linestyle='-', label=f'Average: {np.mean(improvements):.1f}%')
            ax2.set_xlabel('Improvement Percentage (%)')
            ax2.set_ylabel('Frequency')
            ax2.set_title('Distribution of Performance Changes')
            ax2.legend()
        
        plt.tight_layout()
        
        filename = f"version_comparison_{comparison.baseline_version}_vs_{comparison.comparison_version}.png"
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        return filepath
    
    def _create_main_benchmark_comparison_chart(self, comparison: VersionComparison, 
                                              main_comparisons: List[VersionComparisonResult]) -> Optional[Path]:
        """Create chart showing main benchmark comparisons."""
        if not main_comparisons:
            return None
        
        # Create DataFrame for easier plotting
        data = []
        for c in main_comparisons:
            data.append({
                'benchmark': c.benchmark_type.value if c.benchmark_type else 'Unknown',
                'library': c.library.value if c.library else 'Unknown',
                'database': c.database_type.value if c.database_type else 'Unknown',
                'rows': c.rows or 0,
                'improvement': c.improvement_percent,
                'baseline_score': c.baseline_score,
                'comparison_score': c.comparison_score,
                'unit': c.baseline_unit
            })
        
        df = pd.DataFrame(data)
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(f'Main Benchmark Comparison: {comparison.baseline_version} → {comparison.comparison_version}', 
                     fontsize=16)
        
        # Top-left: Improvement by benchmark type
        if 'benchmark' in df.columns:
            benchmark_improvements = df.groupby('benchmark')['improvement'].mean()
            ax = axes[0, 0]
            bars = ax.bar(range(len(benchmark_improvements)), benchmark_improvements.values, 
                         color=['green' if x > 0 else 'red' for x in benchmark_improvements.values],
                         alpha=0.7)
            ax.set_xticks(range(len(benchmark_improvements)))
            ax.set_xticklabels(benchmark_improvements.index, rotation=45)
            ax.set_ylabel('Average Improvement (%)')
            ax.set_title('Performance by Benchmark Type')
            ax.axhline(y=0, color='black', linestyle='-', alpha=0.5)
            
            # Add value labels
            for bar, value in zip(bars, benchmark_improvements.values):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + (1 if height > 0 else -3),
                       f'{value:.1f}%', ha='center', va='bottom' if height > 0 else 'top')
        
        # Top-right: Improvement by library
        if 'library' in df.columns:
            library_improvements = df.groupby('library')['improvement'].mean()
            ax = axes[0, 1]
            bars = ax.bar(range(len(library_improvements)), library_improvements.values,
                         color=['green' if x > 0 else 'red' for x in library_improvements.values],
                         alpha=0.7)
            ax.set_xticks(range(len(library_improvements)))
            ax.set_xticklabels(library_improvements.index, rotation=45)
            ax.set_ylabel('Average Improvement (%)')
            ax.set_title('Performance by Library')
            ax.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        
        # Bottom-left: Improvement by database
        if 'database' in df.columns:
            db_improvements = df.groupby('database')['improvement'].mean()
            ax = axes[1, 0]
            bars = ax.bar(range(len(db_improvements)), db_improvements.values,
                         color=['green' if x > 0 else 'red' for x in db_improvements.values],
                         alpha=0.7)
            ax.set_xticks(range(len(db_improvements)))
            ax.set_xticklabels(db_improvements.index)
            ax.set_ylabel('Average Improvement (%)')
            ax.set_title('Performance by Database')
            ax.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        
        # Bottom-right: Score comparison scatter plot
        ax = axes[1, 1]
        ax.scatter(df['baseline_score'], df['comparison_score'], alpha=0.6)
        
        # Add diagonal line for reference (no change)
        min_score = min(df['baseline_score'].min(), df['comparison_score'].min())
        max_score = max(df['baseline_score'].max(), df['comparison_score'].max())
        ax.plot([min_score, max_score], [min_score, max_score], 'r--', alpha=0.5, label='No Change')
        
        ax.set_xlabel(f'{comparison.baseline_version} Score')
        ax.set_ylabel(f'{comparison.comparison_version} Score')
        ax.set_title('Score Correlation')
        ax.legend()
        
        plt.tight_layout()
        
        filename = f"main_benchmarks_{comparison.baseline_version}_vs_{comparison.comparison_version}.png"
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        return filepath
    
    def _create_mapper_benchmark_comparison_chart(self, comparison: VersionComparison,
                                                mapper_comparisons: List[VersionComparisonResult]) -> Optional[Path]:
        """Create chart showing mapper benchmark comparisons (AVGT vs SS)."""
        if not mapper_comparisons:
            return None
        
        # Separate AVGT and SS results
        avgt_results = [c for c in mapper_comparisons if c.mode == BenchmarkMode.AVGT]
        ss_results = [c for c in mapper_comparisons if c.mode == BenchmarkMode.SS]
        
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        fig.suptitle(f'AutoMapper Benchmark Comparison: {comparison.baseline_version} → {comparison.comparison_version}', 
                     fontsize=14)
        
        # Left: AVGT results
        if avgt_results:
            scenarios = [c.scenario.value if c.scenario else 'Unknown' for c in avgt_results]
            improvements = [c.improvement_percent for c in avgt_results]
            
            ax = axes[0]
            bars = ax.bar(range(len(scenarios)), improvements,
                         color=['green' if x > 0 else 'red' for x in improvements],
                         alpha=0.7)
            ax.set_xticks(range(len(scenarios)))
            ax.set_xticklabels(scenarios, rotation=45)
            ax.set_ylabel('Improvement (%)')
            ax.set_title('Average Time (AVGT) Improvements')
            ax.axhline(y=0, color='black', linestyle='-', alpha=0.5)
            
            # Add value labels
            for bar, value in zip(bars, improvements):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + (1 if height > 0 else -3),
                       f'{value:.1f}%', ha='center', va='bottom' if height > 0 else 'top')
        
        # Right: SS (cold start) results
        if ss_results:
            scenarios = [c.scenario.value if c.scenario else 'Unknown' for c in ss_results]
            improvements = [c.improvement_percent for c in ss_results]
            
            ax = axes[1]
            bars = ax.bar(range(len(scenarios)), improvements,
                         color=['green' if x > 0 else 'red' for x in improvements],
                         alpha=0.7)
            ax.set_xticks(range(len(scenarios)))
            ax.set_xticklabels(scenarios, rotation=45)
            ax.set_ylabel('Improvement (%)')
            ax.set_title('Cold Start (SS) Improvements')
            ax.axhline(y=0, color='black', linestyle='-', alpha=0.5)
            
            # Add value labels
            for bar, value in zip(bars, improvements):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + (1 if height > 0 else -3),
                       f'{value:.1f}%', ha='center', va='bottom' if height > 0 else 'top')
        
        plt.tight_layout()
        
        filename = f"mapper_benchmarks_{comparison.baseline_version}_vs_{comparison.comparison_version}.png"
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        return filepath
    
    def _create_library_summary_chart(self, comparison: LibraryComparison) -> Optional[Path]:
        """Create summary chart showing Kapper vs other libraries."""
        if not comparison.library_comparisons:
            return None
        
        # Group by competitor library
        library_stats = {}
        for c in comparison.library_comparisons:
            lib = c.competitor_library.value
            if lib not in library_stats:
                library_stats[lib] = {'advantages': [], 'total': 0}
            library_stats[lib]['advantages'].append(c.kapper_advantage_percent)
            library_stats[lib]['total'] += 1
        
        # Calculate averages
        libraries = []
        avg_advantages = []
        win_rates = []
        
        for lib, stats in library_stats.items():
            libraries.append(lib)
            avg_advantages.append(np.mean(stats['advantages']))
            wins = len([a for a in stats['advantages'] if a > 0])
            win_rates.append((wins / stats['total']) * 100)
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle(f'Kapper vs Other Libraries (Version {comparison.version})', fontsize=14)
        
        # Left: Average advantage percentage
        bars = ax1.bar(libraries, avg_advantages,
                      color=['green' if x > 0 else 'red' for x in avg_advantages],
                      alpha=0.7)
        ax1.set_ylabel('Average Kapper Advantage (%)')
        ax1.set_title('Performance Advantage')
        ax1.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        
        # Add value labels
        for bar, value in zip(bars, avg_advantages):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + (1 if height > 0 else -3),
                    f'{value:.1f}%', ha='center', va='bottom' if height > 0 else 'top')
        
        # Right: Win rate
        bars = ax2.bar(libraries, win_rates, alpha=0.7, color='blue')
        ax2.set_ylabel('Win Rate (%)')
        ax2.set_title('Kapper Win Rate')
        ax2.set_ylim(0, 100)
        
        # Add value labels
        for bar, value in zip(bars, win_rates):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + 2,
                    f'{value:.0f}%', ha='center', va='bottom')
        
        plt.tight_layout()
        
        filename = f"library_comparison_{comparison.version}.png"
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        return filepath
    
    def _create_library_detail_chart(self, comparison: LibraryComparison) -> Optional[Path]:
        """Create detailed chart showing library comparison by benchmark type."""
        if not comparison.library_comparisons:
            return None
        
        # Create DataFrame
        data = []
        for c in comparison.library_comparisons:
            data.append({
                'benchmark': c.benchmark_type.value if c.benchmark_type else 'Unknown',
                'competitor': c.competitor_library.value,
                'database': c.database_type.value if c.database_type else 'Unknown',
                'rows': c.rows,
                'advantage': c.kapper_advantage_percent,
                'kapper_score': c.kapper_score,
                'competitor_score': c.competitor_score
            })
        
        df = pd.DataFrame(data)
        
        # Create heatmap of advantages
        pivot_table = df.pivot_table(values='advantage', index='benchmark', columns='competitor', aggfunc='mean')
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Create heatmap
        sns.heatmap(pivot_table, annot=True, fmt='.1f', cmap='RdYlGn', center=0,
                   ax=ax, cbar_kws={'label': 'Kapper Advantage (%)'})
        
        ax.set_title(f'Kapper Performance vs Competitors (Version {comparison.version})')
        ax.set_xlabel('Competitor Library')
        ax.set_ylabel('Benchmark Type')
        
        plt.tight_layout()
        
        filename = f"library_detail_{comparison.version}.png"
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        
        return filepath


if __name__ == "__main__":
    # Test the visualizer
    import sys
    from pathlib import Path
    try:
        from result_parser import ResultParser
        from comparator import BenchmarkComparator
    except ImportError:
        print("Make sure to run from the analysis directory")
        sys.exit(1)
    
    parser = ResultParser()
    comparator = BenchmarkComparator()
    
    # Handle different execution contexts (from analysis dir or from root)
    script_dir = Path(__file__).parent
    if (script_dir.parent / "results").exists():
        results_dir = script_dir.parent / "results"  # Running from analysis dir or root
        graphs_dir = script_dir.parent / "graphs"
    else:
        results_dir = Path("../results")  # Fallback
        graphs_dir = Path("../graphs")
    
    visualizer = BenchmarkVisualizer(output_dir=graphs_dir)
    
    # Test version comparison visualization
    analyse_version = "1.6.1"
    compare_version = "1.5.0"
    
    print(f"Looking for results in: {results_dir.resolve()}")
    print(f"Will save graphs to: {graphs_dir.resolve()}")
    
    if (results_dir / analyse_version).exists() and (results_dir / compare_version).exists():
        print(f"Creating version comparison visualizations: {analyse_version} vs {compare_version}")
        baseline = parser.parse_version_results(results_dir / analyse_version, analyse_version)
        comparison = parser.parse_version_results(results_dir / compare_version, compare_version)
        
        version_comp = comparator.compare_versions(baseline, comparison)
        version_charts = visualizer.create_version_comparison_charts(version_comp)
        
        print(f"Created version comparison charts:")
        for chart in version_charts:
            print(f"  - {chart}")
    else:
        print(f"Skipping version comparison - one or both directories not found")
    
    # Test library comparison visualization for both versions
    print(f"\nCreating library comparison visualizations for {analyse_version}")
    if (results_dir / analyse_version).exists():
        baseline_results = parser.parse_version_results(results_dir / analyse_version, analyse_version)
        
        library_comp_baseline = comparator.compare_libraries(baseline_results)
        library_charts_baseline = visualizer.create_library_comparison_charts(library_comp_baseline, baseline_results)
        
        print(f"Created library comparison charts for {analyse_version}:")
        for chart in library_charts_baseline:
            print(f"  - {chart}")
        
        # Test mapper comparison visualization for this version
        mapper_charts_baseline = visualizer.create_mapper_comparison_charts(baseline_results)
        if mapper_charts_baseline:
            print(f"Created mapper comparison charts for {analyse_version}:")
            for chart in mapper_charts_baseline:
                print(f"  - {chart}")
    
    print(f"\nCreating library comparison visualizations for {compare_version}")
    if (results_dir / compare_version).exists():
        comparison_results = parser.parse_version_results(results_dir / compare_version, compare_version)
        
        library_comp_comparison = comparator.compare_libraries(comparison_results)
        library_charts_comparison = visualizer.create_library_comparison_charts(library_comp_comparison, comparison_results)
        
        print(f"Created library comparison charts for {compare_version}:")
        for chart in library_charts_comparison:
            print(f"  - {chart}")
        
        # Test mapper comparison visualization for this version
        mapper_charts_comparison = visualizer.create_mapper_comparison_charts(comparison_results)
        if mapper_charts_comparison:
            print(f"Created mapper comparison charts for {compare_version}:")
            for chart in mapper_charts_comparison:
                print(f"  - {chart}")
    
    print(f"\nAll visualizations saved to: {visualizer.output_dir}")