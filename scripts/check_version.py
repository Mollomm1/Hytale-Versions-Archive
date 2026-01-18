import requests
import os
import sys

def log(message):
    print(message, file=sys.stderr)

def check_url(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # stream=True downloads headers only
        r = requests.get(url, headers=headers, stream=True, timeout=10)
        status = r.status_code
        r.close()
        return status == 200
    except Exception as e:
        log(f"Error checking {url}: {e}")
        return False

def main():
    # Environment variables from Workflow
    manual_ver = os.environ.get("MANUAL_VER", "")
    manual_type = os.environ.get("MANUAL_TYPE", "")
    
    check_type = os.environ.get("CHECK_TYPE", "release") # 'release' or 'pre-release'
    last_known_ver = int(os.environ.get("LAST_KNOWN_VER", "0"))

    # --- Manual Trigger Logic ---
    # If user forced a version/type, we only proceed if the current job matches the type
    if manual_ver.strip():
        # If user didn't specify type, or specified type matches current job
        if not manual_type or manual_type == check_type:
             log(f"Manual trigger matches current job ({check_type}). Processing v{manual_ver}")
             print(f"VERSION={manual_ver}")
             print(f"TYPE={check_type}")
             print("FOUND=true")
             return
        else:
             log(f"Manual trigger ({manual_type}) does not match current job ({check_type}). Skipping.")
             print("FOUND=false")
             return

    # --- Automatic Logic ---
    next_ver = last_known_ver + 1
    
    # Construct URL based on current job type
    base_url = f"https://game-patches.hytale.com/patches/linux/amd64/{check_type}/0/{next_ver}.pwr"
    
    log(f"Checking {check_type} candidate: v{next_ver}...")
    log(f"URL: {base_url}")

    if check_url(base_url):
        log(f"!!! Found new {check_type}: v{next_ver}")
        print(f"VERSION={next_ver}")
        print(f"TYPE={check_type}")
        print("FOUND=true")
    else:
        log(f"No update found for {check_type} (v{next_ver} not available)")
        print("FOUND=false")

if __name__ == "__main__":
    main()