#!/usr/bin/env python3
"""
Auto-patching utility for Hytale server and client.
Handles domain replacement and protocol changes to connect to standalone emulator.
"""
import os
import sys
import shutil
import subprocess

def patch_server(server_jar, new_domain, use_http=True, krakatau_path="./Krakatau"):
    """Patch the server JAR file."""
    print("[*] Patching server JAR...")
    
    if not os.path.exists(server_jar):
        print(f"[!] Server JAR not found: {server_jar}")
        return False
    
    # Create a backup
    backup_jar = server_jar + ".backup"
    if not os.path.exists(backup_jar):
        shutil.copy(server_jar, backup_jar)
        print(f"[*] Backup created: {backup_jar}")
    
    # Determine output path (patched version)
    output_jar = server_jar.replace(".jar", ".patched.jar")
    
    # Build the serverPatcher command
    script_dir = os.path.dirname(os.path.abspath(__file__))
    patcher_script = os.path.join(script_dir, "serverPatcher.py")
    
    cmd = [
        sys.executable,
        patcher_script,
        server_jar,
        output_jar,
        "--new", new_domain,
        "--krakatau", krakatau_path
    ]
    
    if use_http:
        cmd.append("--use-http")
    
    print(f"[*] Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(f"[*] Warnings/Info: {result.stderr}")
        
        if result.returncode != 0:
            print(f"[!] Server patching failed")
            return False
        
        # Replace original with patched version
        shutil.move(output_jar, server_jar)
        print(f"[+] Server patched successfully")
        return True
        
    except Exception as e:
        print(f"[!] Error during server patching: {e}")
        return False

def patch_client(client_exe, new_domain, use_http=True):
    """Patch the client executable."""
    print("[*] Patching client executable...")
    
    if not os.path.exists(client_exe):
        print(f"[!] Client executable not found: {client_exe}")
        return False
    
    # Create a backup
    backup_exe = client_exe + ".backup"
    if not os.path.exists(backup_exe):
        shutil.copy(client_exe, backup_exe)
        print(f"[*] Backup created: {backup_exe}")
    
    # Build the clientPatcher command
    script_dir = os.path.dirname(os.path.abspath(__file__))
    patcher_script = os.path.join(script_dir, "clientPatcher.py")
    
    cmd = [
        sys.executable,
        patcher_script,
        client_exe,
        new_domain
    ]
    
    if use_http:
        cmd.append("--use-http")
    
    print(f"[*] Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(f"[*] Warnings/Info: {result.stderr}")
        
        if result.returncode != 0:
            print(f"[!] Client patching failed")
            return False
        
        print(f"[+] Client patched successfully")
        return True
        
    except Exception as e:
        print(f"[!] Error during client patching: {e}")
        return False

def auto_patch(game_dir, new_domain="localhost:4478", krakatau_path="./Krakatau"):
    """
    Automatically patch server and client.
    Args:
        game_dir: Root game directory
        new_domain: New domain for the emulator (default: localhost:4478)
        krakatau_path: Path to Krakatau directory (default: ./Krakatau)
    """
    print(f"[*] Starting auto-patch for domain: {new_domain}")
    
    server_jar = os.path.join(game_dir, "data", "Server", "HytaleServer.jar")
    
    # Determine client executable - try both Windows (.exe) and Linux versions
    client_dir = os.path.join(game_dir, "data", "Client")
    client_exe_windows = os.path.join(client_dir, "HytaleClient.exe")
    client_exe_linux = os.path.join(client_dir, "HytaleClient")
    
    if os.path.exists(client_exe_windows):
        client_exe = client_exe_windows
    elif os.path.exists(client_exe_linux):
        client_exe = client_exe_linux
    else:
        client_exe = client_exe_windows  # Default to Windows, will error if neither exists
    
    # Setup Krakatau first
    print("[*] Verifying Krakatau installation...")
    setup_script = os.path.join(os.path.dirname(__file__), "setup_krakatau.py")
    try:
        result = subprocess.run([sys.executable, setup_script, krakatau_path], capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print(f"[!] Krakatau setup failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"[!] Error setting up Krakatau: {e}")
        return False
    
    # Patch server
    if not patch_server(server_jar, new_domain, use_http=True, krakatau_path=krakatau_path):
        return False
    
    # Patch client
    if not patch_client(client_exe, new_domain, use_http=True):
        return False
    
    print("[+] All patches applied successfully!")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: auto_patch.py <game_dir> [new_domain] [krakatau_path]")
        print("Example: auto_patch.py ./game localhost:4478 ./Krakatau")
        sys.exit(1)
    
    game_dir = sys.argv[1]
    new_domain = sys.argv[2] if len(sys.argv) > 2 else "localhost:4478"
    krakatau_path = sys.argv[3] if len(sys.argv) > 3 else "./Krakatau"
    
    if not auto_patch(game_dir, new_domain, krakatau_path):
        sys.exit(1)
