"""
Dataset Splitter

Splits processed datasets into train, validation, and test sets.
Saves results to JSON files for training.
"""

import json
import random
from typing import List, Dict, Tuple, Optional
from pathlib import Path

from data.file_handler import CodeSample


class DatasetSplitter:
    """
    Splits dataset into train, validation, and test sets.
    """
    
    def __init__(
        self,
        train_ratio: float = 0.85,
        val_ratio: float = 0.10,
        test_ratio: float = 0.05,
        seed: int = 42,
    ):
        if abs(train_ratio + val_ratio + test_ratio - 1.0) > 0.001:
            raise ValueError("Split ratios must sum to 1.0")
        
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.seed = seed
    
    def split(
        self, 
        samples: List[CodeSample],
        stratify_by_language: bool = True,
    ) -> Dict[str, List[CodeSample]]:
        """
        Split samples into train/val/test sets.
        
        Args:
            samples: List of CodeSamples to split
            stratify_by_language: If True, maintain language distribution in each split
            
        Returns:
            Dict with 'train', 'val', 'test' keys
        """
        random.seed(self.seed)
        
        if stratify_by_language:
            return self._stratified_split(samples)
        else:
            return self._random_split(samples)
    
    def _random_split(self, samples: List[CodeSample]) -> Dict[str, List[CodeSample]]:
        """Simple random split."""
        shuffled = samples.copy()
        random.shuffle(shuffled)
        
        n = len(shuffled)
        train_end = int(n * self.train_ratio)
        val_end = train_end + int(n * self.val_ratio)
        
        return {
            'train': shuffled[:train_end],
            'val': shuffled[train_end:val_end],
            'test': shuffled[val_end:],
        }
    
    def _stratified_split(self, samples: List[CodeSample]) -> Dict[str, List[CodeSample]]:
        """Split maintaining language distribution."""
        # Group by language
        by_language: Dict[str, List[CodeSample]] = {}
        for sample in samples:
            lang = sample.language
            if lang not in by_language:
                by_language[lang] = []
            by_language[lang].append(sample)
        
        # Split each language group
        train, val, test = [], [], []
        
        for lang, lang_samples in by_language.items():
            random.shuffle(lang_samples)
            n = len(lang_samples)
            
            train_end = int(n * self.train_ratio)
            val_end = train_end + int(n * self.val_ratio)
            
            train.extend(lang_samples[:train_end])
            val.extend(lang_samples[train_end:val_end])
            test.extend(lang_samples[val_end:])
        
        # Shuffle final splits
        random.shuffle(train)
        random.shuffle(val)
        random.shuffle(test)
        
        return {
            'train': train,
            'val': val,
            'test': test,
        }
    
    def save_splits(
        self, 
        splits: Dict[str, List[CodeSample]], 
        output_dir: str,
    ) -> Dict[str, str]:
        """
        Save splits to JSON files.
        
        Args:
            splits: Dict with train/val/test samples
            output_dir: Directory to save files
            
        Returns:
            Dict mapping split name to file path
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        file_paths = {}
        
        for split_name, samples in splits.items():
            file_path = output_path / f"{split_name}.json"
            
            # Convert to dicts for JSON serialization
            data = [sample.to_dict() for sample in samples]
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            file_paths[split_name] = str(file_path)
        
        # Also save metadata
        metadata = {
            "total_samples": sum(len(s) for s in splits.values()),
            "splits": {
                name: {
                    "count": len(samples),
                    "file": str(file_paths[name]),
                }
                for name, samples in splits.items()
            },
            "config": {
                "train_ratio": self.train_ratio,
                "val_ratio": self.val_ratio,
                "test_ratio": self.test_ratio,
                "seed": self.seed,
            }
        }
        
        metadata_path = output_path / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        file_paths['metadata'] = str(metadata_path)
        
        return file_paths
    
    def get_split_stats(self, splits: Dict[str, List[CodeSample]]) -> Dict[str, Dict]:
        """Get statistics for each split."""
        stats = {}
        
        for split_name, samples in splits.items():
            languages = {}
            total_lines = 0
            total_bytes = 0
            
            for sample in samples:
                languages[sample.language] = languages.get(sample.language, 0) + 1
                total_lines += sample.line_count
                total_bytes += sample.size_bytes
            
            stats[split_name] = {
                "count": len(samples),
                "languages": languages,
                "total_lines": total_lines,
                "total_bytes": total_bytes,
                "avg_lines_per_sample": total_lines / len(samples) if samples else 0,
            }
        
        return stats
