import zipfile
import argparse
import os
import re
import subprocess
import sys
import shutil

# Target directories to scan for class files
TARGET_DIRS = [
    "com/hypixel/hytale/server/core/auth",
    "com/hypixel/hytale/server/core/io/handlers/login"
]

# The specific class that needs the HTTP/1.1 logic patch
AUTH_CLASS_FILENAME = "SessionServiceClient.class"

def process_class_with_krakatau(class_data, filename, old_domain, new_domain, use_http, krakatau_path):
    """
    Safely patches a class by disassembling to Krakatau JASM, 
    editing the text, and reassembling.
    """
    krak_dis = os.path.join(krakatau_path, "disassemble.py")
    krak_asm = os.path.join(krakatau_path, "assemble.py")

    # Create a clean temporary workspace
    workspace_dir = "patch_workspace"
    if os.path.exists(workspace_dir):
        shutil.rmtree(workspace_dir)
    os.makedirs(workspace_dir)

    temp_in = "input.class"
    temp_j = os.path.join(workspace_dir, "output.j")
    temp_out = "output.class"
    
    with open(temp_in, "wb") as f:
        f.write(class_data)

    try:
        # 1. Disassemble (No -roundtrip so we get readable names for Regex)
        subprocess.run([sys.executable, krak_dis, "-out", temp_j, temp_in], check=True, capture_output=True)

        with open(temp_j, "r") as f:
            content = f.read()

        # --- Patch A: Domain Replacement ---
        # Matches subdomains + hytale.com
        domain_pattern = r'(?:[a-zA-Z0-9-]+\.)*' + re.escape(old_domain)
        content = re.sub(domain_pattern, new_domain, content)

        # --- Patch B: HTTP Protocol and Logic ---
        if use_http:
            # Change https:// to http:// in all string literals
            content = content.replace("https://", "http://")

            # Apply logic injection only to the SessionServiceClient
            if filename.endswith(AUTH_CLASS_FILENAME):
                # Krakatau specific syntax for the timeout interface call
                # Note: Regex handles the specific spacing in your snippet
                target_re = r"(invokeinterface\s+InterfaceMethod\s+java/net/http/HttpRequest\$Builder\s+timeout\s+\(Ljava/time/Duration;\)Ljava/net/http/HttpRequest\$Builder;\s+2)"
                
                # Injection: get HTTP_1_1 version, then call .version() on the builder
                injection = (
                    r"\1\n"
                    r"    getstatic Field java/net/http/HttpClient$Version HTTP_1_1 Ljava/net/http/HttpClient$Version;\n"
                    r"    invokeinterface InterfaceMethod java/net/http/HttpRequest$Builder version (Ljava/net/http/HttpClient$Version;)Ljava/net/http/HttpRequest$Builder; 2"
                )
                
                if "timeout" in content:
                    content = re.sub(target_re, injection, content)
                    print(f"   [{filename}] Successfully injected HTTP/1.1 enforcement logic.")
                else:
                    print(f"   [Warning] Found SessionServiceClient but 'timeout' instruction was missing.")

        with open(temp_j, "w") as f:
            f.write(content)

        # 2. Reassemble
        # -r: resolve names to constants
        # target: directory (workspace_dir) because Krakatau -r requires a directory target
        res = subprocess.run([sys.executable, krak_asm, "-r", "-out", temp_out, workspace_dir], capture_output=True, text=True)
        
        if res.returncode != 0:
            print(f"   [Error] Assembly failed for {filename}: {res.stderr}")
            return class_data

        with open(temp_out, "rb") as f:
            return f.read()

    except Exception as e:
        print(f"   [Error] Critical failure processing {filename}: {e}")
        return class_data
    finally:
        # Cleanup temporary files
        if os.path.exists(temp_in): os.remove(temp_in)
        if os.path.exists(temp_out): os.remove(temp_out)
        if os.path.exists(workspace_dir): shutil.rmtree(workspace_dir)

def process_jar(input_path, output_path, old_domain, new_domain, use_http, krakatau_path):
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return

    print(f"Patching {input_path} -> {output_path}...")
    temp_output = output_path + ".tmp"

    try:
        with zipfile.ZipFile(input_path, 'r') as zin, zipfile.ZipFile(temp_output, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                
                is_target = any(item.filename.startswith(d) for d in TARGET_DIRS)
                is_class = item.filename.endswith(".class")

                if is_target and is_class:
                    print(f"Processing: {item.filename}")
                    data = process_class_with_krakatau(data, item.filename, old_domain, new_domain, use_http, krakatau_path)
                
                zout.writestr(item, data)
        
        if os.path.exists(output_path): os.remove(output_path)
        os.rename(temp_output, output_path)
        print("\nJAR patched successfully!")

    except Exception as e:
        print(f"Fatal: {e}")
        if os.path.exists(temp_output): os.remove(temp_output)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hytale Server Patcher (Krakatau Edition)")
    parser.add_argument("input_jar", help="Source JAR")
    parser.add_argument("output_jar", help="Output JAR")
    parser.add_argument("--old", default="hytale.com", help="Old domain")
    parser.add_argument("--new", required=True, help="New domain (e.g. localhost:8000)")
    parser.add_argument("--use-http", action="store_true", help="Replace https and force HTTP/1.1")
    parser.add_argument("--krakatau", default="./Krakatau", help="Path to Krakatau directory")
    
    args = parser.parse_args()
    process_jar(args.input_jar, args.output_jar, args.old, args.new, args.use_http, args.krakatau)