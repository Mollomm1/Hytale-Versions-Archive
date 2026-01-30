import argparse
import os
import sys

def calculate_bytes(text):
    """
    Converts a string to a specific byte pattern:
    1. Length byte
    2. 00 00 00 padding
    3. ASCII characters separated by 00 (Wide-char style, no trailing 00 for last char)
    """
    # Step 1: Calculate length
    length = len(text)
    
    # Initialize the byte array
    result_bytes = bytearray()
    
    # Step 5: Add the length byte at the beginning
    result_bytes.append(length)
    
    # Step 4: Add 00 00 00 in start
    result_bytes.extend([0x00, 0x00, 0x00])
    
    # Step 1 & 3: Convert to ASCII and add 00 bytes between groups
    for i, char in enumerate(text):
        result_bytes.append(ord(char))
        
        # Add 00 byte if this is NOT the last character
        if i < length - 1:
            result_bytes.append(0x00)
            
    return result_bytes

def edit_file_from_hex(data, old_bytes, new_bytes):
    """
    Searches for old_bytes in data and replaces them with new_bytes.
    - If new_bytes is longer: Do nothing (prevents corrupting offsets).
    - If new_bytes is shorter: Overwrite the start, keep trailing original bytes.
    """
    len_old = len(old_bytes)
    len_new = len(new_bytes)

    if len_new > len_old:
        print(f"[!] Error: New byte sequence is larger than the original ({len_new} > {len_old}). Skipping.")
        return

    # Find all occurrences
    start = 0
    found_count = 0
    
    while True:
        index = data.find(old_bytes, start)
        if index == -1:
            break
        
        # Apply the edit
        # We only overwrite the length of the new bytes.
        # Any remaining bytes from the old sequence (if new is smaller) are left alone.
        data[index : index + len_new] = new_bytes
        
        found_count += 1
        # Move start forward to continue searching
        start = index + len_new

    if found_count > 0:
        print(f"[*] Replaced {found_count} occurrence(s).")
    else:
        print(f"[-] Pattern not found for replacement.")

def main():
    parser = argparse.ArgumentParser(description="Utility to patch Hytale clients")
    parser.add_argument("file", help="Path to the executable file")
    parser.add_argument("domain", help="new domain that will replace hytale.com")
    parser.add_argument("--use-http", action="store_true", help="Use http:// instead of https:// for subdomains")
    
    args = parser.parse_args()
    file_path = args.file
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)
        
    print(f"[*] Reading {file_path}...")
    with open(file_path, 'rb') as f:
        data = bytearray(f.read())

    # Logic to generate replacements
    domain = args.domain
    subdomain_hack = ""
    
    # Logic provided to split domain if too long
    if len(domain) > 10:
        if len(domain) > 16:
            print("Domains over 16 caracters are unsupported!")
            exit(1)
        subdomain_hack = domain[:6]
        domain_main = domain[6:]
        replacements = [("hytale.com", domain_main)]
    else:
        replacements = [("hytale.com", domain)]

    protocol = "http://" if args.use_http else "https://"

    print("[*] Applying telemetry patches...")
    edit_file_from_hex(data, calculate_bytes("https://ca900df42fcf57d4dd8401a86ddd7da2@sentry.hytale.com/2"), calculate_bytes(f'{protocol}t@{domain}/2'))
    
    # If subdomain_hack is empty (short domain), we usually prepend the whole domain 
    # or handle it differently, but strictly following your logic snippet:
    target_sub = protocol + subdomain_hack 
    
    subs = ["https://tools.", "https://sessions.", "https://account-data.", "https://telemetry."]
    for s in subs:
        replacements.append((s, target_sub))

    print("[*] Applying domain patches...")
    # Apply
    for old, new in replacements:
        print(f" -> Replacing '{old}' with '{new}'...")
        # We convert both the search string and the replacement string to the byte format
        edit_file_from_hex(data, calculate_bytes(old), calculate_bytes(new))

    try:
        with open(file_path, 'wb') as f:
            f.write(data)
        print(f"[*] Success. Saved to {file_path}")
    except Exception as e:
        print(f"Error saving file: {e}")

if __name__ == "__main__":
    main()