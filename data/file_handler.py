"""
File Handler for Dataset Uploads

Handles ZIP files (containing code) and JSON files (code snippets).
Extracts, validates, and converts to standard JSON format.
"""

import os
import json
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import hashlib


# Supported code file extensions
SUPPORTED_EXTENSIONS = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.jsx': 'javascript',
    '.tsx': 'typescript',
    '.java': 'java',
    '.cpp': 'cpp',
    '.c': 'c',
    '.h': 'c',
    '.hpp': 'cpp',
    '.go': 'go',
    '.rs': 'rust',
    '.rb': 'ruby',
    '.php': 'php',
    '.cs': 'csharp',
    '.swift': 'swift',
    '.kt': 'kotlin',
    '.scala': 'scala',
    '.r': 'r',
    '.sql': 'sql',
    '.sh': 'shell',
    '.bash': 'shell',
}


@dataclass
class CodeSample:
    """Represents a single code sample."""
    content: str
    language: str
    filename: Optional[str] = None
    file_hash: Optional[str] = None
    size_bytes: int = 0
    line_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FileHandler:
    """
    Handles file uploads and extraction for dataset processing.
    
    Supports:
    - ZIP files containing code files
    - JSON files with code snippets
    """
    
    def __init__(self, max_file_size_mb: int = 10, max_upload_size_mb: int = 500):
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.max_upload_size_bytes = max_upload_size_mb * 1024 * 1024
        self.supported_extensions = SUPPORTED_EXTENSIONS
    
    def process_upload(self, file_path: str) -> Tuple[List[CodeSample], Dict[str, Any]]:
        """
        Process an uploaded file (ZIP or JSON).
        
        Args:
            file_path: Path to the uploaded file
            
        Returns:
            Tuple of (list of CodeSamples, metadata dict)
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_size = file_path.stat().st_size
        if file_size > self.max_upload_size_bytes:
            raise ValueError(f"File too large: {file_size} bytes (max: {self.max_upload_size_bytes})")
        
        suffix = file_path.suffix.lower()
        
        if suffix == '.zip':
            samples, stats = self._process_zip(file_path)
        elif suffix == '.json':
            samples, stats = self._process_json(file_path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}. Use .zip or .json")
        
        metadata = {
            "upload_type": suffix[1:],  # 'zip' or 'json'
            "original_filename": file_path.name,
            "upload_size_bytes": file_size,
            "total_samples": len(samples),
            **stats
        }
        
        return samples, metadata
    
    def _process_zip(self, zip_path: Path) -> Tuple[List[CodeSample], Dict[str, Any]]:
        """Extract and process code files from a ZIP archive."""
        samples = []
        stats = {
            "files_processed": 0,
            "files_skipped": 0,
            "languages": {},
            "total_lines": 0,
            "total_bytes": 0,
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract ZIP
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(temp_dir)
            
            # Walk through extracted files
            for root, dirs, files in os.walk(temp_dir):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for filename in files:
                    if filename.startswith('.'):
                        continue
                    
                    file_path = Path(root) / filename
                    ext = file_path.suffix.lower()
                    
                    # Check if supported extension
                    if ext not in self.supported_extensions:
                        stats["files_skipped"] += 1
                        continue
                    
                    # Check file size
                    file_size = file_path.stat().st_size
                    if file_size > self.max_file_size_bytes:
                        stats["files_skipped"] += 1
                        continue
                    
                    if file_size == 0:
                        stats["files_skipped"] += 1
                        continue
                    
                    try:
                        # Read file content
                        content = file_path.read_text(encoding='utf-8', errors='ignore')
                        
                        # Skip empty files
                        if not content.strip():
                            stats["files_skipped"] += 1
                            continue
                        
                        language = self.supported_extensions[ext]
                        line_count = content.count('\n') + 1
                        file_hash = hashlib.md5(content.encode()).hexdigest()
                        
                        # Create sample
                        sample = CodeSample(
                            content=content,
                            language=language,
                            filename=filename,
                            file_hash=file_hash,
                            size_bytes=len(content.encode('utf-8')),
                            line_count=line_count,
                        )
                        samples.append(sample)
                        
                        # Update stats
                        stats["files_processed"] += 1
                        stats["languages"][language] = stats["languages"].get(language, 0) + 1
                        stats["total_lines"] += line_count
                        stats["total_bytes"] += file_size
                        
                    except Exception as e:
                        stats["files_skipped"] += 1
                        continue
        
        return samples, stats
    
    def _process_json(self, json_path: Path) -> Tuple[List[CodeSample], Dict[str, Any]]:
        """
        Process a JSON file containing code snippets.
        
        Expected JSON format:
        [
            {"content": "code here", "language": "python", "filename": "optional.py"},
            ...
        ]
        
        Or:
        {"samples": [...]}
        """
        samples = []
        stats = {
            "files_processed": 0,
            "files_skipped": 0,
            "languages": {},
            "total_lines": 0,
            "total_bytes": 0,
        }
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle both list and dict with 'samples' key
        if isinstance(data, dict):
            if 'samples' in data:
                items = data['samples']
            elif 'data' in data:
                items = data['data']
            else:
                # Single sample
                items = [data]
        elif isinstance(data, list):
            items = data
        else:
            raise ValueError("JSON must be a list of samples or object with 'samples' key")
        
        for item in items:
            try:
                # Support multiple field names for content
                content = None
                for key in ['content', 'text', 'code', 'source']:
                    if key in item and item[key]:
                        content = item[key]
                        break
                
                if not content or not content.strip():
                    stats["files_skipped"] += 1
                    continue
                
                # Support multiple field names for language
                language = item.get('language') or item.get('lang') or 'unknown'
                
                # Support multiple field names for filename
                filename = item.get('filename') or item.get('file_name') or item.get('file_path')
                
                if language == 'unknown' and filename:
                    ext = Path(filename).suffix.lower()
                    language = self.supported_extensions.get(ext, 'unknown')
                
                # Compute stats
                line_count = content.count('\n') + 1
                size_bytes = len(content.encode('utf-8'))
                file_hash = hashlib.md5(content.encode()).hexdigest()
                
                # Check size limit
                if size_bytes > self.max_file_size_bytes:
                    stats["files_skipped"] += 1
                    continue
                
                sample = CodeSample(
                    content=content,
                    language=language,
                    filename=filename,
                    file_hash=file_hash,
                    size_bytes=size_bytes,
                    line_count=line_count,
                )
                samples.append(sample)
                
                # Update stats
                stats["files_processed"] += 1
                stats["languages"][language] = stats["languages"].get(language, 0) + 1
                stats["total_lines"] += line_count
                stats["total_bytes"] += size_bytes
                
            except Exception as e:
                stats["files_skipped"] += 1
                continue
        
        return samples, stats
    
    def samples_to_json(self, samples: List[CodeSample], output_path: str) -> None:
        """Save samples to a JSON file."""
        data = [sample.to_dict() for sample in samples]
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load_samples_from_json(self, json_path: str) -> List[CodeSample]:
        """Load samples from a JSON file."""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return [CodeSample(**item) for item in data]
