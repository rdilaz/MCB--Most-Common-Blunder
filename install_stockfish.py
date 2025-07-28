#!/usr/bin/env python3
"""
Download Stockfish binary for Linux during build
"""
import os
import urllib.request
import tarfile
import stat

def download_stockfish():
    """Download and extract Stockfish for Linux"""
    print("🔍 Downloading Stockfish for Linux...")
    
    # Stockfish 16 for Linux
    url = "https://github.com/official-stockfish/Stockfish/releases/download/sf_16/stockfish-ubuntu-x86-64-avx2.tar"
    
    # Download to a temporary location
    tar_path = "/tmp/stockfish.tar"
    urllib.request.urlretrieve(url, tar_path)
    
    print("📦 Extracting Stockfish...")
    
    # Extract the tar file
    with tarfile.open(tar_path, 'r') as tar:
        tar.extractall("/tmp/stockfish_extract")
    
    # Find the stockfish binary
    extracted_binary = "/tmp/stockfish_extract/stockfish/stockfish-ubuntu-x86-64-avx2"
    
    if os.path.exists(extracted_binary):
        # Copy to a location we can use
        target_dir = os.path.dirname(__file__)
        target_path = os.path.join(target_dir, "stockfish_linux")
        
        # Copy the binary
        import shutil
        shutil.copy2(extracted_binary, target_path)
        
        # Make it executable
        os.chmod(target_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        
        print(f"✅ Stockfish installed at: {target_path}")
        return target_path
    else:
        print("❌ Could not find Stockfish binary in extracted files")
        return None

if __name__ == "__main__":
    download_stockfish() 