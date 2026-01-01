#!/usr/bin/env python3
"""
Simple Kapper Release Manager

Downloads benchmark suites for specific Kapper versions.
"""

import json
import shutil
import zipfile
from pathlib import Path
import urllib.request
import urllib.error


class KapperReleaseManager:
    """Downloads Kapper benchmark suites from GitHub releases."""
    
    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = Path(download_dir).resolve()
        self.download_dir.mkdir(exist_ok=True)
    
    def download_version(self, version: str) -> Path:
        """Download and extract benchmark suite for a specific version.
        
        Args:
            version: Kapper version (e.g., "1.6.1")
            
        Returns:
            Path to extracted benchmark directory
        """
        # Check if already downloaded
        extract_path = self.download_dir / f"kapper-benchmarks-{version}"
        if extract_path.exists():
            return extract_path
        
        # Get release info from GitHub API
        api_url = f"https://api.github.com/repos/driessamyn/kapper/releases/tags/{version}"
        
        try:
            with urllib.request.urlopen(api_url) as response:
                release = json.loads(response.read())
        except urllib.error.URLError as e:
            if "404" in str(e):
                raise RuntimeError(f"Version {version} not found")
            raise RuntimeError(f"Failed to fetch release info: {e}")
        
        # Find benchmark asset
        benchmark_asset = None
        expected_name = f"kapper-benchmarks-{version}.zip"
        
        for asset in release.get('assets', []):
            if asset['name'] == expected_name:
                benchmark_asset = asset
                break
        
        if not benchmark_asset:
            raise RuntimeError(f"No benchmark asset found for version {version}")
        
        # Download the ZIP file
        zip_path = self.download_dir / expected_name
        print(f"Downloading {expected_name}...")
        
        try:
            urllib.request.urlretrieve(benchmark_asset['browser_download_url'], zip_path)
        except urllib.error.URLError as e:
            raise RuntimeError(f"Failed to download benchmark suite: {e}")
        
        # Extract to target directory
        print(f"Extracting to {extract_path}...")
        temp_extract_path = extract_path.parent / f"temp_{extract_path.name}"
        temp_extract_path.mkdir(parents=True, exist_ok=True)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_path)
        except zipfile.BadZipFile as e:
            raise RuntimeError(f"Failed to extract ZIP file: {e}")
        
        # Check if ZIP created a nested directory structure
        extracted_items = list(temp_extract_path.iterdir())
        if len(extracted_items) == 1 and extracted_items[0].is_dir():
            # Single directory extracted - move its contents up
            nested_dir = extracted_items[0]
            if extract_path.exists():
                shutil.rmtree(extract_path)
            nested_dir.rename(extract_path)
            temp_extract_path.rmdir()
        else:
            # Multiple items extracted - move temp directory to final location
            if extract_path.exists():
                shutil.rmtree(extract_path)
            temp_extract_path.rename(extract_path)
        
        # Clean up ZIP file
        zip_path.unlink()
        
        return extract_path


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python release_manager.py <version>")
        print("Example: python release_manager.py 1.6.1")
        sys.exit(1)
    
    version = sys.argv[1]
    manager = KapperReleaseManager()
    
    try:
        path = manager.download_version(version)
        print(f"Benchmark suite for {version} ready at: {path}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)