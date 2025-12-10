"""
Bias Detection Module

Analyzes datasets for potential biases using data slicing techniques.
Reports on:
1. Language distribution imbalance
2. Code complexity distribution
3. File size distribution
4. Coding style variations
5. Documentation/comment ratios
"""

import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict, field
from collections import defaultdict
from pathlib import Path
import statistics

from data.file_handler import CodeSample


@dataclass
class BiasMetrics:
    """Metrics for a single bias dimension."""
    dimension: str
    distribution: Dict[str, int]
    percentages: Dict[str, float]
    imbalance_score: float  # 0 = perfectly balanced, 1 = completely imbalanced
    dominant_category: str
    minority_categories: List[str]
    recommendation: str
    severity: str  # "low", "medium", "high"


@dataclass
class BiasReport:
    """Complete bias analysis report for a dataset."""
    dataset_id: str
    total_samples: int
    analysis_timestamp: str
    
    # Individual bias metrics
    language_bias: Optional[BiasMetrics] = None
    complexity_bias: Optional[BiasMetrics] = None
    size_bias: Optional[BiasMetrics] = None
    documentation_bias: Optional[BiasMetrics] = None
    
    # Overall assessment
    overall_bias_score: float = 0.0  # Average of all bias scores
    overall_severity: str = "low"
    recommendations: List[str] = field(default_factory=list)
    
    # Detailed statistics
    statistics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        # Convert nested dataclasses
        for key in ['language_bias', 'complexity_bias', 'size_bias', 'documentation_bias']:
            if result[key] is not None:
                result[key] = asdict(result[key]) if hasattr(result[key], '__dict__') else result[key]
        return result


class BiasDetector:
    """
    Detects bias in code datasets using data slicing techniques.
    
    Analyzes multiple dimensions of potential bias and provides
    actionable recommendations for addressing imbalances.
    """
    
    # Complexity indicators
    COMPLEXITY_PATTERNS = {
        'loops': re.compile(r'\b(for|while|do)\b'),
        'conditionals': re.compile(r'\b(if|else|elif|switch|case)\b'),
        'functions': re.compile(r'\b(def|function|func|fn|void|int|string|public|private)\b'),
        'classes': re.compile(r'\b(class|struct|interface|enum)\b'),
        'try_catch': re.compile(r'\b(try|catch|except|finally|throw|raise)\b'),
    }
    
    # Comment patterns by language
    COMMENT_PATTERNS = {
        'single_line': re.compile(r'(//.*$|#.*$)', re.MULTILINE),
        'multi_line': re.compile(r'/\*[\s\S]*?\*/|"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\''),
        'docstring': re.compile(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\''),
    }
    
    def __init__(self, imbalance_threshold: float = 0.3):
        """
        Args:
            imbalance_threshold: Threshold for flagging imbalance (0-1)
        """
        self.imbalance_threshold = imbalance_threshold
    
    def analyze(self, samples: List[CodeSample], dataset_id: str = "unknown") -> BiasReport:
        """
        Perform complete bias analysis on a dataset.
        
        Args:
            samples: List of code samples to analyze
            dataset_id: ID of the dataset
            
        Returns:
            BiasReport with all bias metrics
        """
        from datetime import datetime
        
        report = BiasReport(
            dataset_id=dataset_id,
            total_samples=len(samples),
            analysis_timestamp=datetime.utcnow().isoformat(),
        )
        
        if not samples:
            report.recommendations.append("Dataset is empty - no bias analysis possible")
            return report
        
        # Analyze each dimension
        report.language_bias = self._analyze_language_bias(samples)
        report.complexity_bias = self._analyze_complexity_bias(samples)
        report.size_bias = self._analyze_size_bias(samples)
        report.documentation_bias = self._analyze_documentation_bias(samples)
        
        # Calculate overall score
        bias_scores = []
        for bias in [report.language_bias, report.complexity_bias, 
                     report.size_bias, report.documentation_bias]:
            if bias:
                bias_scores.append(bias.imbalance_score)
        
        if bias_scores:
            report.overall_bias_score = statistics.mean(bias_scores)
        
        # Determine overall severity
        if report.overall_bias_score > 0.7:
            report.overall_severity = "high"
        elif report.overall_bias_score > 0.4:
            report.overall_severity = "medium"
        else:
            report.overall_severity = "low"
        
        # Compile recommendations
        for bias in [report.language_bias, report.complexity_bias,
                     report.size_bias, report.documentation_bias]:
            if bias and bias.severity in ["medium", "high"]:
                report.recommendations.append(bias.recommendation)
        
        # Add statistics
        report.statistics = self._compute_statistics(samples)
        
        return report
    
    def _analyze_language_bias(self, samples: List[CodeSample]) -> BiasMetrics:
        """Analyze programming language distribution."""
        distribution = defaultdict(int)
        for sample in samples:
            distribution[sample.language] += 1
        
        return self._create_metrics(
            dimension="Programming Language",
            distribution=dict(distribution),
            total=len(samples),
            recommendation_template="Consider adding more {minority} samples to balance the dataset"
        )
    
    def _analyze_complexity_bias(self, samples: List[CodeSample]) -> BiasMetrics:
        """Analyze code complexity distribution."""
        complexity_levels = defaultdict(int)
        
        for sample in samples:
            score = self._compute_complexity_score(sample.content)
            if score < 2:
                level = "simple"
            elif score < 5:
                level = "moderate"
            elif score < 10:
                level = "complex"
            else:
                level = "very_complex"
            complexity_levels[level] += 1
        
        return self._create_metrics(
            dimension="Code Complexity",
            distribution=dict(complexity_levels),
            total=len(samples),
            recommendation_template="Dataset lacks {minority} code samples - consider diversifying complexity"
        )
    
    def _analyze_size_bias(self, samples: List[CodeSample]) -> BiasMetrics:
        """Analyze file size distribution."""
        size_buckets = defaultdict(int)
        
        for sample in samples:
            lines = sample.line_count
            if lines < 20:
                bucket = "small (<20 lines)"
            elif lines < 100:
                bucket = "medium (20-100 lines)"
            elif lines < 500:
                bucket = "large (100-500 lines)"
            else:
                bucket = "very_large (>500 lines)"
            size_buckets[bucket] += 1
        
        return self._create_metrics(
            dimension="File Size",
            distribution=dict(size_buckets),
            total=len(samples),
            recommendation_template="Most samples are in one size category - add {minority} files"
        )
    
    def _analyze_documentation_bias(self, samples: List[CodeSample]) -> BiasMetrics:
        """Analyze documentation/comment coverage."""
        doc_levels = defaultdict(int)
        
        for sample in samples:
            ratio = self._compute_comment_ratio(sample.content)
            if ratio < 0.05:
                level = "no_docs (<5%)"
            elif ratio < 0.15:
                level = "minimal_docs (5-15%)"
            elif ratio < 0.30:
                level = "moderate_docs (15-30%)"
            else:
                level = "well_documented (>30%)"
            doc_levels[level] += 1
        
        return self._create_metrics(
            dimension="Documentation Level",
            distribution=dict(doc_levels),
            total=len(samples),
            recommendation_template="Documentation coverage is uneven - add {minority} samples"
        )
    
    def _compute_complexity_score(self, content: str) -> int:
        """Compute a simple complexity score based on control structures."""
        score = 0
        for pattern_name, pattern in self.COMPLEXITY_PATTERNS.items():
            matches = pattern.findall(content)
            score += len(matches)
        return score
    
    def _compute_comment_ratio(self, content: str) -> float:
        """Compute the ratio of comments to total content."""
        if not content:
            return 0.0
        
        comment_chars = 0
        for pattern in self.COMMENT_PATTERNS.values():
            matches = pattern.findall(content)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                comment_chars += len(match)
        
        return comment_chars / len(content)
    
    def _create_metrics(
        self,
        dimension: str,
        distribution: Dict[str, int],
        total: int,
        recommendation_template: str,
    ) -> BiasMetrics:
        """Create bias metrics from a distribution."""
        if not distribution:
            return BiasMetrics(
                dimension=dimension,
                distribution={},
                percentages={},
                imbalance_score=0.0,
                dominant_category="N/A",
                minority_categories=[],
                recommendation="No data available",
                severity="low",
            )
        
        # Calculate percentages
        percentages = {k: (v / total) * 100 for k, v in distribution.items()}
        
        # Find dominant and minority categories
        sorted_items = sorted(distribution.items(), key=lambda x: x[1], reverse=True)
        dominant = sorted_items[0][0]
        dominant_pct = percentages[dominant]
        
        # Find minorities (< 10% of samples)
        minorities = [k for k, v in percentages.items() if v < 10]
        
        # Calculate imbalance score (Gini-like coefficient)
        if len(distribution) == 1:
            imbalance_score = 0.0  # Single category is not imbalanced
        else:
            # Use normalized entropy as balance measure
            n = len(distribution)
            entropy = 0
            for count in distribution.values():
                if count > 0:
                    p = count / total
                    entropy -= p * (p if p == 0 else statistics.log2(p) if hasattr(statistics, 'log2') else 0)
            
            # Normalize: max entropy = log2(n)
            import math
            max_entropy = math.log2(n) if n > 1 else 1
            normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
            imbalance_score = 1 - normalized_entropy  # High entropy = low imbalance
        
        # Simpler imbalance: how much does dominant exceed fair share?
        n_categories = len(distribution)
        fair_share = 100 / n_categories if n_categories > 0 else 100
        # Avoid division by zero when there's only 1 category
        if n_categories <= 1 or fair_share >= 100:
            imbalance_score = 0.0  # Single category = no imbalance
        else:
            imbalance_score = max(0, (dominant_pct - fair_share) / (100 - fair_share))
        
        # Determine severity
        if imbalance_score > 0.7:
            severity = "high"
        elif imbalance_score > 0.4:
            severity = "medium"
        else:
            severity = "low"
        
        # Generate recommendation
        minority_str = ", ".join(minorities[:3]) if minorities else "diverse"
        recommendation = recommendation_template.format(minority=minority_str)
        
        return BiasMetrics(
            dimension=dimension,
            distribution=distribution,
            percentages={k: round(v, 2) for k, v in percentages.items()},
            imbalance_score=round(imbalance_score, 3),
            dominant_category=dominant,
            minority_categories=minorities,
            recommendation=recommendation if severity != "low" else "Distribution is acceptable",
            severity=severity,
        )
    
    def _compute_statistics(self, samples: List[CodeSample]) -> Dict[str, Any]:
        """Compute overall dataset statistics."""
        if not samples:
            return {}
        
        line_counts = [s.line_count for s in samples]
        sizes = [s.size_bytes for s in samples]
        
        return {
            "total_samples": len(samples),
            "total_lines": sum(line_counts),
            "total_bytes": sum(sizes),
            "avg_lines_per_sample": round(statistics.mean(line_counts), 2),
            "median_lines": statistics.median(line_counts),
            "std_dev_lines": round(statistics.stdev(line_counts), 2) if len(line_counts) > 1 else 0,
            "avg_bytes_per_sample": round(statistics.mean(sizes), 2),
            "unique_languages": len(set(s.language for s in samples)),
        }
    
    def save_report(self, report: BiasReport, output_path: str) -> None:
        """Save bias report to JSON file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, indent=2)
    
    def load_report(self, path: str) -> Dict:
        """Load bias report from JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
