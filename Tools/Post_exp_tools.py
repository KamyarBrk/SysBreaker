import os
from langchain.tools import tool
import subprocess
import tempfile
import shutil
import re

@tool
def john_crack_passwords(hash_file : str, wordlist="/usr/share/wordlists/rockyou.txt", hash_format=None):
    """
    Agent tool to run John the Ripper on a hash file.
    """
    # 1. Verify JtR is installed before trying to run it
    # shutil.which checks if the command exists in the system's PATH
    if not shutil.which("john"):
        return {
            "status": "error",
            "error": "John the Ripper executable ('john') not found. Please install it or check your PATH."
        }

    # 2. Build the command (Options first, target file last)
    command = ["john"]
    
    if wordlist:
        command.append(f"--wordlist={wordlist}")
    if hash_format: # Renamed from 'format'
        command.append(f"--format={hash_format}")
        
    command.append(hash_file)

    try:
        # 3. Execute JtR and capture output
        # Removed 'check=True' because JtR returns 1 if no new passwords are cracked
        result = subprocess.run(command, capture_output=True, text=True)
        
        # 4. Retrieve cracked results using --show
        show_command = ["john", "--show", hash_file]
        show_result = subprocess.run(show_command, capture_output=True, text=True)
        
        return {
            "status": "success",
            "log": result.stdout,
            "cracked_passwords": show_result.stdout
        }
        
    except Exception as e:
        # Catch any unexpected system errors (like file read permissions)
        return {
            "status": "error",
            "error": f"An unexpected error occurred: {str(e)}"
        }

@tool
def run_hashcat_attack(target_hash: str, hash_mode: int, wordlist_path: str = "rockyou.txt") -> dict:
    """
    Runs hashcat against a single hash string using a dictionary attack.
    
    Args:
        target_hash: The raw hash string to crack (e.g., '5f4dcc3b5aa765d61d8327deb882cf99').
        hash_mode: The numeric hashcat mode (e.g., 0=MD5, 1000=NTLM, 1800=SHA-512/Unix).
        wordlist_path: Path to the dictionary file. Defaults to 'rockyou.txt'.
        
    Returns:
        dict: {'status': 'success'|'failed'|'error', 'password': '...', 'details': '...'}
    """
    
    # 1. Check prerequisites
    hashcat_bin = shutil.which("hashcat") or "hashcat"
    if not os.path.exists(wordlist_path):
        return {"status": "error", "details": f"Wordlist not found at {wordlist_path}"}

    # 2. Create a temporary file for the hash
    # Hashcat requires a file input for stability, not command-line args
    temp_fd, temp_path = tempfile.mkstemp(suffix=".txt", text=True)
    
    try:
        # Write the hash to the temp file
        with os.fdopen(temp_fd, 'w') as tmp:
            tmp.write(target_hash + "\n")

        # 3. Construct the command
        # -a 0 = Dictionary Attack
        # --potfile-disable = Do not cache results (useful for agents to verify fresh cracks)
        # --machine-readable = Output is easier to parse
        # --quiet = Suppress banner info
        command = [
            hashcat_bin,
            "-m", str(hash_mode),
            "-a", "0",
            temp_path,
            wordlist_path,
            "--potfile-disable",
            "--status",
            "--machine-readable"
        ]

        # 4. Run the process
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60  # Force timeout after 60s to prevent agent hanging
        )

        # 5. Handle Exit Codes & Output
        # Exit Code 0: Cracked
        # Exit Code 1: Exhausted (Failed)
        if process.returncode == 0:
            # Parse output: hashcat prints "hash:password"
            # We look for the line containing our target hash
            match = re.search(rf"{re.escape(target_hash)}:(.*)", process.stdout)
            password = match.group(1) if match else "Unknown (Parse Error)"
            return {"status": "success", "password": password, "original_hash": target_hash}
            
        elif process.returncode == 1:
            return {"status": "failed", "details": "Password not found in wordlist."}
            
        else:
            # Other error codes (permissions, invalid mode, etc)
            return {
                "status": "error", 
                "code": process.returncode, 
                "details": process.stderr.strip() or "Unknown error"
            }

    except subprocess.TimeoutExpired:
        return {"status": "error", "details": "Timeout: Hashcat took too long."}
    except Exception as e:
        return {"status": "error", "details": str(e)}
        
    finally:
        # 6. Cleanup: Always remove the temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)


