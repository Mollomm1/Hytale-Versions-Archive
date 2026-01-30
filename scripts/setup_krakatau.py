#!/usr/bin/env python3
"""
Utility to initialize and verify Krakatau installation.
Downloads from the master branch if not already present.
"""
import os
import subprocess
import sys
import shutil

def setup_krakatau(krakatau_path="./Krakatau"):
    """
    Ensure Krakatau is installed at the specified path.
    If missing, clones from the master branch.
    """
    if os.path.exists(krakatau_path):
        print(f"[*] Krakatau already exists at {krakatau_path}")
        return True
    
    print(f"[*] Krakatau not found. Cloning from master branch...")
    try:
        # Clone from master branch
        result = subprocess.run(
            ["git", "clone", "--branch", "master", 
             "https://github.com/Storyyeller/Krakatau.git", krakatau_path],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"[!] Error cloning Krakatau: {result.stderr}")
            return False
        
        print(f"[+] Krakatau cloned successfully to {krakatau_path}")
        return True
        
    except Exception as e:
        print(f"[!] Error setting up Krakatau: {e}")
        return False

def verify_krakatau(krakatau_path="./Krakatau"):
    """Verify that Krakatau has the required files."""
    required_files = ["disassemble.py", "assemble.py"]
    
    for file in required_files:
        if not os.path.exists(os.path.join(krakatau_path, file)):
            print(f"[!] Missing required file: {file}")
            return False
    
    print(f"[+] Krakatau verification passed")
    return True

if __name__ == "__main__":
    krakatau_path = sys.argv[1] if len(sys.argv) > 1 else "./Krakatau"
    
    if not setup_krakatau(krakatau_path):
        sys.exit(1)
    
    if not verify_krakatau(krakatau_path):
        sys.exit(1)
    
    print("[+] Krakatau is ready to use")
