"""
Data Preprocessing Pipeline

Implements preprocessing steps from the data pipeline requirements:
1. Code Cleaning - normalize whitespace, remove empty lines
2. Deduplication - MinHash for near-duplicate detection
3. PII Removal - redact emails, IPs, API keys, secrets
4. Tokenization - prepare for StarCoder2 training
"""

import re
import hashlib
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

from data.file_handler import CodeSample


# =============================================================================
# PII Patterns for Redaction
# =============================================================================

PII_PATTERNS = {
    # Email addresses
    'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    
    # IP addresses (IPv4)
    'ip_address': re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'),
    
    # API keys (common patterns)
    'api_key': re.compile(r'\b(?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token)["\']?\s*[:=]\s*["\']?([A-Za-z0-9_\-]{20,})["\']?', re.IGNORECASE),
    
    # AWS keys
    'aws_key': re.compile(r'\b(?:AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}\b'),
    
    # Generic secrets
    'secret': re.compile(r'\b(?:secret|password|passwd|pwd)["\']?\s*[:=]\s*["\']?([^\s"\']+)["\']?', re.IGNORECASE),
    
    # Private keys
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----'),
    
    # GitHub tokens
    'github_token': re.compile(r'\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}\b'),
}


class CodeCleaner:
    """
    Cleans and normalizes code content.
    """
    
    def __init__(
        self,
        normalize_whitespace: bool = True,
        remove_empty_lines: bool = True,
        max_line_length: int = 1000,
        min_content_length: int = 10,
        max_content_length: int = 100000,
    ):
        self.normalize_whitespace = normalize_whitespace
        self.remove_empty_lines = remove_empty_lines
        self.max_line_length = max_line_length
        self.min_content_length = min_content_length
        self.max_content_length = max_content_length
    
    def clean(self, content: str) -> Optional[str]:
        """
        Clean code content.
        
        Returns None if content should be filtered out.
        """
        if not content or len(content) < self.min_content_length:
            return None
        
        if len(content) > self.max_content_length:
            return None
        
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Truncate very long lines
            if len(line) > self.max_line_length:
                line = line[:self.max_line_length] + '...'
            
            # Normalize whitespace (convert tabs, remove trailing)
            if self.normalize_whitespace:
                line = line.rstrip()
                # Keep leading whitespace for indentation
            
            # Skip empty lines if configured
            if self.remove_empty_lines and not line.strip():
                continue
            
            cleaned_lines.append(line)
        
        cleaned = '\n'.join(cleaned_lines)
        
        # Final length check
        if len(cleaned) < self.min_content_length:
            return None
        
        return cleaned


class PIIRemover:
    """
    Removes Personally Identifiable Information from code.
    """
    
    def __init__(self, replacement: str = "[REDACTED]"):
        self.replacement = replacement
        self.patterns = PII_PATTERNS
    
    def remove_pii(self, content: str) -> Tuple[str, Dict[str, int]]:
        """
        Remove PII from content.
        
        Returns:
            Tuple of (cleaned content, dict of PII counts by type)
        """
        counts = defaultdict(int)
        
        for pii_type, pattern in self.patterns.items():
            matches = pattern.findall(content)
            if matches:
                counts[pii_type] = len(matches) if isinstance(matches[0], str) else len(matches)
                content = pattern.sub(self.replacement, content)
        
        return content, dict(counts)


class Deduplicator:
    """
    Removes duplicate and near-duplicate code samples.
    
    Uses content hashing for exact duplicates and MinHash for near-duplicates.
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.85,
        num_perm: int = 128,
    ):
        self.similarity_threshold = similarity_threshold
        self.num_perm = num_perm
        self._seen_hashes: Set[str] = set()
        self._minhash_index: Dict[str, List[int]] = {}
    
    def _compute_hash(self, content: str) -> str:
        """Compute content hash for exact deduplication."""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _get_shingles(self, content: str, k: int = 5) -> Set[str]:
        """Get k-shingles (character n-grams) from content."""
        # Normalize whitespace for shingling
        normalized = ' '.join(content.split())
        if len(normalized) < k:
            return {normalized}
        return {normalized[i:i+k] for i in range(len(normalized) - k + 1)}
    
    def _compute_minhash(self, shingles: Set[str]) -> List[int]:
        """Compute MinHash signature for near-duplicate detection."""
        import random
        
        if not shingles:
            return [0] * self.num_perm
        
        # Simple MinHash implementation
        signature = []
        for seed in range(self.num_perm):
            random.seed(seed)
            min_hash = float('inf')
            for shingle in shingles:
                h = hash((shingle, seed)) & 0xFFFFFFFF
                min_hash = min(min_hash, h)
            signature.append(min_hash)
        
        return signature
    
    def _jaccard_similarity(self, sig1: List[int], sig2: List[int]) -> float:
        """Estimate Jaccard similarity from MinHash signatures."""
        if not sig1 or not sig2:
            return 0.0
        return sum(1 for a, b in zip(sig1, sig2) if a == b) / len(sig1)
    
    def is_duplicate(self, content: str) -> bool:
        """
        Check if content is a duplicate of previously seen content.
        """
        # Exact duplicate check
        content_hash = self._compute_hash(content)
        if content_hash in self._seen_hashes:
            return True
        
        # Near-duplicate check using MinHash
        shingles = self._get_shingles(content)
        minhash = self._compute_minhash(shingles)
        
        for stored_hash, stored_minhash in self._minhash_index.items():
            similarity = self._jaccard_similarity(minhash, stored_minhash)
            if similarity >= self.similarity_threshold:
                return True
        
        # Not a duplicate - add to index
        self._seen_hashes.add(content_hash)
        self._minhash_index[content_hash] = minhash
        
        return False
    
    def reset(self):
        """Reset the deduplication index."""
        self._seen_hashes.clear()
        self._minhash_index.clear()


class DataPreprocessor:
    """
    Main preprocessing pipeline that combines all steps.
    """
    
    def __init__(
        self,
        cleaner: Optional[CodeCleaner] = None,
        pii_remover: Optional[PIIRemover] = None,
        deduplicator: Optional[Deduplicator] = None,
    ):
        self.cleaner = cleaner or CodeCleaner()
        self.pii_remover = pii_remover or PIIRemover()
        self.deduplicator = deduplicator or Deduplicator()
    
    def process_samples(
        self, 
        samples: List[CodeSample],
        deduplicate: bool = True,
    ) -> Tuple[List[CodeSample], Dict[str, any]]:
        """
        Process a list of code samples through the full pipeline.
        
        Steps:
        1. Clean code
        2. Remove PII
        3. Deduplicate
        
        Returns:
            Tuple of (processed samples, processing stats)
        """
        processed = []
        stats = {
            "input_count": len(samples),
            "cleaned_count": 0,
            "pii_found": defaultdict(int),
            "duplicates_removed": 0,
            "output_count": 0,
            "languages": defaultdict(int),
        }
        
        # Reset deduplicator for fresh batch
        if deduplicate:
            self.deduplicator.reset()
        
        for sample in samples:
            # Step 1: Clean
            cleaned_content = self.cleaner.clean(sample.content)
            if cleaned_content is None:
                continue
            stats["cleaned_count"] += 1
            
            # Step 2: Remove PII
            pii_cleaned, pii_counts = self.pii_remover.remove_pii(cleaned_content)
            for pii_type, count in pii_counts.items():
                stats["pii_found"][pii_type] += count
            
            # Step 3: Deduplicate
            if deduplicate and self.deduplicator.is_duplicate(pii_cleaned):
                stats["duplicates_removed"] += 1
                continue
            
            # Create processed sample
            processed_sample = CodeSample(
                content=pii_cleaned,
                language=sample.language,
                filename=sample.filename,
                file_hash=hashlib.md5(pii_cleaned.encode()).hexdigest(),
                size_bytes=len(pii_cleaned.encode('utf-8')),
                line_count=pii_cleaned.count('\n') + 1,
            )
            processed.append(processed_sample)
            stats["languages"][sample.language] += 1
        
        stats["output_count"] = len(processed)
        stats["pii_found"] = dict(stats["pii_found"])
        stats["languages"] = dict(stats["languages"])
        
        return processed, stats
