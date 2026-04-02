
from langchain.tools import tool
from nmap import nmap
import telnetlib3
import ftplib
import httpx
import ssl
import socket
import dns.resolver

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
        return f"TELNET OPEN — Banner:\n{banner}"
    return "Telnet port open (no banner received)"



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

@tool
def probe_http(url: str) -> str:
    """
    Sends an HTTP GET request to the target URL and returns the status code,
    response headers, and a snippet of the response body. Useful for checking
    if a URL is live and identifying server information.

    Args:
        url: url of the website to probe
    """
    try:
        with httpx.Client(follow_redirects=True, timeout=10) as client:
            r = client.get(url)
            snippet = r.text[:500].strip()
            return (
                f"Status: {r.status_code}\n"
                f"Headers: {dict(r.headers)}\n"
                f"Body snippet:\n{snippet}"
            )
    except Exception as e:
        return(f'Error: {e}')


@tool
def dns_lookup(domain: str) -> str:
    """
    Performs DNS lookups for A, MX, TXT, CNAME, and NS records on the given
    domain. Useful for mapping infrastructure and finding related services.

    Args:
        domain: Domain for the DNS lookup
    """
    record_types = ["A", "MX", "TXT", "CNAME", "NS"]
    results = {}
    for rtype in record_types:
        answers = dns.resolver.resolve(domain, rtype)
        results[rtype] = [str(r) for r in answers]
    return "\n".join(f"{k}: {v}" for k, v in results.items())

@tool
def get_tls_info(hostname: str) -> str:
    """
    Connects to the host on port 443 and retrieves TLS certificate details
    including subject, issuer, expiry date, and SANs (Subject Alternative Names).
    """
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(
            socket.create_connection((hostname, 443), timeout=10),
            server_hostname=hostname,
        ) as sock:
            cert = sock.getpeercert()
        subject = dict(x[0] for x in cert.get("subject", []))
        issuer = dict(x[0] for x in cert.get("issuer", []))
        sans = [v for k, v in cert.get("subjectAltName", [])]
        return (
            f"Subject: {subject}\n"
            f"Issuer: {issuer}\n"
            f"Valid from: {cert.get('notBefore')}\n"
            f"Valid until: {cert.get('notAfter')}\n"
            f"SANs: {sans}"
            )
    except Exception as e:
        return(f'Error: {e}')