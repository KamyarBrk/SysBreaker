
import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain.tools import tool
from langchain.agents import create_agent
from nmap import nmap
from langchain_ollama.embeddings import OllamaEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
import telnetlib3
import subprocess
import requests
import ftplib
from pathlib import Path
from langchain_chroma import Chroma
from VectorDB_creator import create_vector_db
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
import datetime

current_datetime = datetime.datetime.now()

formatted_datetime = current_datetime.strftime("%B %d, %Y %H:%M:%S")

load_dotenv(dotenv_path='.env', override=True)

vulners_api = os.getenv("VULNERS_API_KEY")
NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"

PLAN_FILE = "plan.txt"
RECON_FILE = 'recon.txt'

llm = ChatOllama(model='qwen3.5:397b-cloud')
'''
choice = input("Choose one of the following LLMs:\n1. Gemini\n2. Ollama\nEnter the number corresponding to your choice: ")

if choice == "1":

# Gemini
    llm = ChatGoogleGenerativeAI(model="gemini-3.1-pro-preview", google_api_key=os.getenv("GOOGLE_API_KEY"))

# Ollama
else:
    llm = ChatOllama(model='qwen3.5:397b-cloud')

'''

try:
    current_dir = Path(__file__).resolve().parent
except NameError:
    current_dir = Path.cwd()


directory_path = current_dir/"vector"

# Check if the path exists and is a directory
if directory_path.is_dir():
    print("The VectorDB directory exists. Would you like to create a new vector database? This will overwrite the existing one. (yes/no)")
    user_input = input("Enter->: ").strip().lower()
    if user_input in ['yes', 'y']:  
        create_vector_db()       

else:
    print("The VectorDB directory does not exist. A new vector database will be created.")
    create_vector_db()

embeddings = OllamaEmbeddings(
    model="nomic-embed-text" 
)

#persist_directory = r"./vector" 
persist_directory = current_dir/"vector"
collection_name = "vector_storage" 

if not os.path.exists(persist_directory):
    raise FileNotFoundError(f"Database not found at {persist_directory}.")

vectorstore = Chroma(
    persist_directory=persist_directory,
    embedding_function=embeddings,
    collection_name=collection_name
)

# This defines the 'retriever' variable used in the tool below!
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5} 
)

def list_saved_threads(db_path: str) -> list:
    """Connects to the LangGraph SQLite DB and prints all unique thread_ids."""
    
    try:
        # 1. Connect to the database
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 2. Query for all unique thread IDs in the checkpoints table
            cursor.execute("SELECT DISTINCT thread_id FROM checkpoints;")
            threads = cursor.fetchall()
            
            # 3. Display the results
            if not threads:
                print("The database is empty. No thread_ids found.")
                return
                
            print("\n--- Available Saved Sessions ---")
            thread_id_lst = []
            for i, (thread_id,) in enumerate(threads, 1):
                print(f"{i}. {thread_id}")
                thread_id_lst.append(f"{thread_id}")
            print("--------------------------------\n")
        return thread_id_lst
    except sqlite3.OperationalError as e:
        # This triggers if the database file exists, but the LangGraph tables 
        # haven't been created yet (meaning no memory has ever been saved).
        if "no such table: checkpoints" in str(e):
            print("No memory found. The 'checkpoints' table doesn't exist yet.")
        else:
            print(f"Database error: {e}")


def clear_thread_memory(db_path: str, thread_id: str) -> None:
    """
    Deletes all checkpoints and memories for a specific thread_id.
    Requires langgraph-checkpoint-sqlite v2.0+.
    """
    # 1. Connect to the SQLite database
    conn = sqlite3.connect(db_path, check_same_thread=False)
    
    try:
        # 2. Initialize the checkpointer
        checkpointer = SqliteSaver(conn)
        
        # 3. Call the built-in delete method
        checkpointer.delete_thread(thread_id)
        
        print(f"Successfully cleared memory for thread: '{thread_id}'")
        
    except AttributeError:
        print("Error: '.delete_thread()' not found. You might need to update your LangGraph packages, or use Method 2 below.")
    finally:
        conn.close()

@tool
def retriever_tool(query: str) -> str:
    """
    Searches the cybersecurity training knowledge base for methodologies, commands, 
    and techniques related to enumeration, exploitation, post-exploitation, and recon.
    """
    # This now works because 'retriever' is defined right above it!
    docs = retriever.invoke(query)

    if not docs:
        return "I found no relevant information in the knowledge base for that query."
    
    results = []
    for i, doc in enumerate(docs):
        # Using .get() prevents KeyError if the metadata doesn't exist
        source = doc.metadata.get('source', 'Unknown File')
        page = doc.metadata.get('page', 'Unknown Page')
        
        chunk_info = f"--- Result {i+1} ---\n"
        chunk_info += f"Source: {source} (Page {page})\n"
        chunk_info += f"Content: {doc.page_content}\n"
        
        results.append(chunk_info)
    
    return "\n\n".join(results)


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

'''
@tool
def cve_lookup(software: str, version: str) -> str:
    """
        Looks up known CVEs for a given software and version using the Vulners API.
        Use this after port_scanner has identified service names and versions via -sV.

        Args:
            software: The software/service name (e.g. 'openssh', 'apache', 'nginx').
            version: The version string detected (e.g. '2.4.51', '7.4p1').

        Returns a list of CVEs with severity scores and descriptions.
        """
    api = vulners.VulnersApi(api_key=vulners_api)
    results = api.search.search_exploits_all(f'{software}:{version}')
    trimmed = [
        {
            "id": r.get("id"),
            "title": r.get("title"),
            "cvss_score": r.get("cvss", {}).get("score"),
            "description": r.get("description", "")[:300],
        }
        for r in results[:10]
    ]
    return trimmed
'''

@tool
def nvd_lookup(service_and_version: str) -> str:
    """
    Queries the NVD (National Vulnerability Database) for CVEs matching
    a given service name and optional version string.

    Args:
        service_and_version: Service and version to search for.
    """
    parts = service_and_version.strip().split(" ", 1)
    service = parts[0]
    version = parts[1] if len(parts) > 1 else ""

    keyword = f"{service} {version}".strip()

    params = {
        "keywordSearch": keyword,
        "resultsPerPage": 10,
        "startIndex": 0,
    }

    response = requests.get(NVD_API, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    total = data.get("totalResults", 0)
    vulns = data.get("vulnerabilities", [])

    if not vulns:
        return f"No CVEs found for '{keyword}'."

    results = [f"CVEs for '{keyword}' ({total} total, showing top {len(vulns)}):"]
    results.append("=" * 60)

    for item in vulns:
        cve = item.get("cve", {})
        cve_id = cve.get("id", "N/A")

        # Description
        descs = cve.get("descriptions", [])
        description = next(
            (d["value"] for d in descs if d.get("lang") == "en"),
            "No description available."
        )

        # CVSS score
        score = "N/A"
        severity = "N/A"
        metrics = cve.get("metrics", {})
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if key in metrics and metrics[key]:
                cvss_data = metrics[key][0].get("cvssData", {})
                score = cvss_data.get("baseScore", "N/A")
                severity = cvss_data.get("baseSeverity", metrics[key][0].get("baseSeverity", "N/A"))
                break

        # Published date
        published = cve.get("published", "N/A")[:10]

        # References
        refs = cve.get("references", [])
        ref_urls = [r["url"] for r in refs[:2]]

        results.append(f"\n[{cve_id}]  Score: {score} ({severity})  Published: {published}")
        results.append(f"  {description[:200]}{'...' if len(description) > 200 else ''}")
        if ref_urls:
            results.append(f"  Refs: {' | '.join(ref_urls)}")

    return "\n".join(results)


@tool
def commands(command: str) -> str:
    """
    Executes a shell command on the local system and returns
    the stdout, stderr, and exit code.

    Args:
        command: The shell command to execute.
    """

    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
    )
    output = []
    if result.stdout:
        output.append(f"STDOUT:\n{result.stdout.strip()}")
    if result.stderr:
        output.append(f"STDERR:\n{result.stderr.strip()}")
    output.append(f"EXIT CODE: {result.returncode}")
    return "\n".join(output)



Recon_agent_Prompt = (
    "You are an AI model that performs the reconnaissance phase of a penetration test."
        "Use the given tools provided to better complete the reconnaissance tasks."
    "Do not provide security recommendations that is the job of the enumeration agent, your job is exclusively identifying ports"
    "You should report all of your findings using the 'recon_findings' tool in high detail to the other agents can read it"
)

recon_agent = create_agent(
    llm,
    tools=[port_scanner, host_discovery, telnet_probe, ftp_probe, retriever_tool],
    system_prompt=Recon_agent_Prompt,
)



Enum_Agent_Prompt = ("You are an AI model that performs the enumeration phase of a penetration test. "
                     "If there is no vulnerability found tell the user there is no vulnerability found for now"
                     "You are to only find the vulnerabilities using the cve_lookup tool"
                     "Your only job is to enumerate the information given to you nothing else, you should always respond to the supervisor whether a vulnerability was found or not")

enumeration_agent = create_agent(
    llm,
    tools=[nvd_lookup, retriever_tool],
    system_prompt=Enum_Agent_Prompt
)

Expl_Agent_Prompt = ("You have the role of exploiting found vulnerabilities in the target."
                     "If there are no vulnerabilities reported you do not need to do anything"
                     "Use the tools provided to exploit found vulnerabilities."
                     "If you succeeded in exploiting the vulnerability you should list how you did it report you were successful")
expl_agent = create_agent(
    llm,
    tools=[commands, retriever_tool]
    , system_prompt=Expl_Agent_Prompt
)

Post_Agent_Prompt = ("You have the role of post-exploitation in the pentesting phase"
                     "Your job is to do privilege escalation based on the exploit found by the exploitation agent"
                     "If there is no exploits found you have no job to do and should not do any jobs")
post_agent = create_agent(
    llm,
    tools=[commands, retriever_tool],
    system_prompt= Post_Agent_Prompt
)


@tool
def recon_node(request: str) -> str:
    """
    This is the tool to call the recon agent to perform reconnaissance on the target system.

    Args:
        request: The request to run the recon agent on.

    Returns: The current ports opened on the target system.
    """
    result = recon_agent.invoke({
        "messages": [{"role": "user", "content": request}]
    })
    return result["messages"][-1].text


@tool
def enum_node(request: str) -> str:
    """
    This is the tool to call the enumeration agent to perform enumeration of vulnerabilities that may be on the target system.

    Args:
        request: The request to run the enumeration agent on.

    Returns: The current vulnerabilities found if any.
    """
    result = enumeration_agent.invoke({
        "messages": [{"role": "user", "content": request}]
    })
    return result["messages"][-1].text

@tool
def expl_node(request: str) -> str:
    """
      This is the tool to call the exploit agent to perform exploitation of vulnerabilities that may be on the target system.

      Args:
          request: The request to run the exploitation agent on.

      Returns: Whether it succeeded or not.
      """
    result = expl_agent.invoke({
        "messages": [{"role": "user", "content": request}]
    })
    return result["messages"][-1].text


@tool
def post_node(request: str) -> str:
    """
    This is the tool to call the post exploitation agent to perform privilege escalation on the target system.

    Args:
        request: The request to run the post exploitation agent on (provide it with the information of exploit agent).

    Returns: If it succeeded or not.
    """
    result = post_agent.invoke({
        "messages": [{"role": "user", "content": request}]
    })
    return result["messages"][-1].text

SUPERVISOR_PROMPT = (
    "You are the supervisor of a pentest."
    "Make the appropriate tool calls and if multiple are needed use multiple tools, each tool needs to be provided with the information of the previous tool if needed."
    "If no vulnerabilities are found then you can end the task and do not need to continue further, only call exploitation and post-exploitation if there is a need to"
    "Your first step is to develop a detailed plan and use the 'plan' tool to write into a text file for the user to read your exact plan"
)

conn = sqlite3.connect(current_dir/"Supervisor_Memory"
""/"my_agent_memory.db", check_same_thread=False)
persistent_memory = SqliteSaver(conn)

mem_lst = (list_saved_threads(current_dir/'Supervisor_Memory'/'my_agent_memory.db'))

session_delete_choice = input("Would you like to delete any previous memory threads? (yes/no): ").strip().lower()

if session_delete_choice in ['yes', 'y']:
    delete_thread_id = input("Enter the thread ID to delete, enter a list of Thread IDs to remove multiple of them: ").strip()
    my_list = [int(num) for num in delete_thread_id.split()]
    for thread_id in my_list:
        clear_thread_memory(current_dir/'Supervisor_Memory'/'my_agent_memory.db', f"{mem_lst[thread_id-1]}")
mem_lst = (list_saved_threads(current_dir/'Supervisor_Memory'/'my_agent_memory.db'))
session_choice = int(input("Enter the number associated with the thread ID above to load memory for or type 0 to start a new session: "))

if session_choice == 0:
    config = {"configurable": {"thread_id": f"pentest_session: {formatted_datetime}"}}
else:
    config = {"configurable": {"thread_id": mem_lst[session_choice-1]}}

supervisor_agent = create_agent(
    llm,
    tools=[recon_node, enum_node, expl_node, post_node, retriever_tool],
    system_prompt=SUPERVISOR_PROMPT,
    checkpointer=persistent_memory
)


exit_conditions = ["end","quit","exit","stop","done","finished"]
print(f"Welcome to the Multi-Agentic AI Pentesting Framework. Type your commands to start the pentesting process. Type any of the following to finish: {exit_conditions}")
query = input("Enter->: ")

while query not in exit_conditions:

    for step in supervisor_agent.stream(
        {"messages": [{"role": "user", "content": query}]},config=config):
        for update in step.values():
            for message in update.get("messages", []):
                message.pretty_print()

    query = input("Enter->: ")