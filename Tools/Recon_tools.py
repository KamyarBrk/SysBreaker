
from langchain.tools import tool
from nmap import nmap
import telnetlib3
import ftplib



@tool
def host_discovery(cidr_or_host: str) -> str:
    """
    Performs a ping sweep / ARP scan to discover live hosts on a network.
    Use this first when given a subnet (CIDR notation) to find active targets.

    Args:
        cidr_or_host: IP address, hostname, or CIDR range (e.g., "192.168.1.0/24").
    """
    nm = nmap.PortScanner()
    nm.scan(hosts=cidr_or_host, arguments="-sn -T4 --open")
    live = []
    for host in nm.all_hosts():
        state = nm[host].state()
        hostname = nm[host].hostname() or "N/A"
        if state == "up":
            live.append(f"  {host:18s} ({hostname})")
    if live:
        return f"Live hosts on {cidr_or_host}:\n" + "\n".join(live)
    return f"No live hosts found on {cidr_or_host}."



@tool
def telnet_probe(target: str) -> str:
    """
    Probes Telnet (port 23) to check if the service is active and grabs the banner.

    Args:
        target: IP address or hostname.
    """
    tn = telnetlib3.Telnet(target, 23, timeout=6)
    banner = tn.read_until(b"login:", timeout=4).decode(errors="replace").strip()
    tn.close()
    if banner:
        return f"[+] TELNET OPEN — Banner:\n{banner}"
    return "[+] Telnet port open (no banner received)"



@tool
def ftp_probe(target: str) -> str:
    """
    Probes FTP (port 21) for anonymous login, server version, and directory listing.

    Args:
        target: IP address or hostname.
    """
    results = []
    try:
        ftp = ftplib.FTP(timeout=8)
        banner = ftp.connect(target, 21)
        results.append(f"FTP Banner: {banner.strip()}")

        # Anonymous login
        try:
            ftp.login("anonymous", "anonymous@example.com")
            results.append("[+] ANONYMOUS LOGIN SUCCESSFUL")
            results.append(f"Welcome: {ftp.getwelcome()}")

            # List root
            files = []
            ftp.retrlines("LIST", files.append)
            results.append("Root directory contents:")
            for f in files[:15]:
                results.append(f"  {f}")
            if len(files) > 15:
                results.append(f"  ... and {len(files) - 15} more")

            ftp.quit()
        except ftplib.error_perm:
            results.append("[-] Anonymous login denied (credentials required)")

    except ConnectionRefusedError:
        return "FTP port 21 is closed or filtered."

    return "\n".join(results)



@tool
def port_scanner(ip: str, arguments: str = "-sV") -> str:
    """
    Tool that allows the AI model to run nmap commands on the host system.
     Args:
        ip: The target IP address or hostname to scan.
        arguments: Nmap arguments/flags to customize the scan (e.g. '-sV', '-p 80,443', '-A').
                   Defaults to '-sV' for version detection.
    """
    nm = nmap.PortScanner()
    return nm.scan(ip, arguments=arguments)