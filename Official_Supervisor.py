import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain.tools import tool
from langchain.agents import create_agent
from nmap import nmap
from langchain_ollama.embeddings import OllamaEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langsmith import traceable
import telnetlib3
import subprocess
import requests
import ftplib
import httpx
import dns.resolver
import ssl
import socket
from pathlib import Path
from langchain_chroma import Chroma
from vector.VectorDB_creator import create_vector_db
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
import datetime
import logging
import pexpect
from typing import Optional
from Tools.Recon_tools import *
from Tools.Enum_tools import * 
from Tools.Exp_tools import *
from Tools.Post_exp_tools import * 

current_datetime = datetime.datetime.now()
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
formatted_datetime = current_datetime.strftime("%B %d, %Y %H:%M:%S")




llm = ChatOllama(model='qwen3.5:397b-cloud', base_url='http://127.0.0.1:11434' ,temperature=0.3)


try:
    current_dir = Path(__file__).resolve().parent
except NameError:
    current_dir = Path.cwd().parent


directory_path = current_dir/"vector"

# Check if the path exists and is a directory
try:
    if directory_path.is_dir():
        print("The VectorDB directory exists. Would you like to create a new vector database? This will overwrite the existing one. (yes/no)")
        user_input = input("Enter->: ").strip().lower()
        if user_input in ['yes', 'y']:  
            create_vector_db()       

    else:
        print("The VectorDB directory does not exist. A new vector database will be created.")
        create_vector_db()
except Exception as e:
    print(f"An error occurred while checking the VectorDB directory/Creation: {e}")

embeddings = OllamaEmbeddings(
    model="nomic-embed-text" 
)


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
def reporter(report: str) -> str:
    """
    Writes the provided text content to a new, uniquely timestamped file in the current directory.

    Use this function to persistently save generated reports, logs, or outputs to disk. 
    It automatically constructs a filename using the current date and time 
    (e.g., 'report_YYYY-MM-DD_HH-MM-SS.txt') to ensure no existing files are overwritten.

    Args:
        report (str): The text content to be written to the file.
    """
    dir_path = current_dir/'tmp'/'Reports'
    dir_path.mkdir(parents=True, exist_ok=True)
    filename = f"report_{current_datetime.strftime('%Y-%m-%d_%H-%M-%S')}.txt"
    with open(current_dir/'tmp'/'Reports'/f'{filename}', 'w', encoding='utf-8') as f:
        f.write(report)
    return f'Success: Report written to ./tmp/Reports/{filename}'

@tool
def planner(report: str) -> str:
    """
    The Planner tool writes the provided text content to a new, uniquely timestamped file in the current directory.

    Use this function to persistently save pentest planning information. 
    It automatically constructs a filename using the current date and time 
    (e.g., 'report_YYYY-MM-DD_HH-MM-SS.txt') to ensure no existing files are overwritten.

    Args:
        report (str): The text content to be written to the file.
    """
    dir_path = current_dir/'tmp'/'Plans'
    dir_path.mkdir(parents=True, exist_ok=True)
    filename = f"Plan_{current_datetime.strftime('%Y-%m-%d_%H-%M-%S')}.txt"
    with open(current_dir/'tmp'/'Plans'/f'{filename}', 'w', encoding='utf-8') as f:
        f.write(report)
    return f'Success: Plan written to ./tmp/Plans/{filename}'


_global_bash_process: Optional[pexpect.spawn] = None

def _get_active_process() -> pexpect.spawn:
    """Returns the active bash process, creating or restarting it if necessary."""
    global _global_bash_process
    
    # Check if process is None OR if it has crashed/terminated
    if _global_bash_process is None or not _global_bash_process.isalive():
        # Spawn a persistent bash process in the background
        _global_bash_process = pexpect.spawn('/bin/bash', encoding='utf-8', echo=False)
        
        # Clear the initial bash banner/prompt
        try:
            # Using EOF instead of a magic string naturally triggers a timeout
            _global_bash_process.expect(pexpect.EOF, timeout=1)
        except pexpect.TIMEOUT:
            pass
            
    return _global_bash_process

def _read_screen(process: pexpect.spawn, timeout: float = 2.0) -> str:
    """Reads whatever is currently printed on the terminal screen."""
    try:
        # Expecting EOF acts as a clean, intentional timeout mechanism
        process.expect(pexpect.EOF, timeout=timeout)
    except pexpect.TIMEOUT:
        pass
    except pexpect.EOF:
        # Safely handle the case where the process dies while we're reading
        pass
    
    output = process.before
    return output.strip() if output else ""

@tool
def commands(command: str, timeout: float = 2.0) -> str:
    """
    Executes a command in a persistent, interactive terminal session.
    Can be used for normal commands or interactive tools like telnet/ssh.
    
    Args:
        command: The shell command or text to type into the terminal.
        timeout: How many seconds to wait for the output to settle.
        
    Returns:
        The formatted terminal output.
    """
    process = _get_active_process()
    
    process.sendline(command)
    
    # Read the screen using the configurable timeout
    screen_output = _read_screen(process, timeout=timeout)
    
    return f"TERMINAL OUTPUT:\n{screen_output}"


Recon_agent_Prompt = (
    "You are an AI model that performs the reconnaissance phase of a penetration test."
        "Use the given tools provided to better complete the reconnaissance tasks."
    "Do not provide security recommendations that is the job of the enumeration agent, your job is exclusively identifying ports"
    "You should report all of your findings using the 'recon_findings' tool in high detail to the other agents can read it"
    "You have a set of tools at your disposal, please use the best fitting tool and if it does not exist you have access to the commands tool"

)

recon_agent = create_agent(
    llm,
    tools=[port_scanner, host_discovery, telnet_probe, ftp_probe, get_tls_info, dns_lookup, probe_http, commands, retriever_tool],
    system_prompt=Recon_agent_Prompt,
)



Enum_Agent_Prompt = ("You are an AI model that performs the enumeration phase of a penetration test. "
                     "If there is no vulnerability found tell the user there is no vulnerability found for now"
                     "You are to only find the vulnerabilities using the cve_lookup tool"
                     "Your only job is to enumerate the information given to you nothing else "
                     "You should always respond to the supervisor whether a vulnerability was found or not"
                     "If you cannot find a vulnerability in the NVD then use what information you do have the enumerate possible threats"
                     )

enumeration_agent = create_agent(
    llm,
    tools=[nvd_lookup, retriever_tool],
    system_prompt=Enum_Agent_Prompt
)

Expl_Agent_Prompt = ("You have the role of exploiting found vulnerabilities in the target."
                     "If there are no vulnerabilities reported you do not need to do anything"
                     "Use the retriever tool to find out how to use commands you need the run with the commands tool for exploitation"
                     "The other tools are there as a last case scenario if you've achieved nothing doing commands"
                     "If you succeeded in exploiting the vulnerability you should list how you did it report you were successful"
                     "You are permitted to do any operation to exploit the given vulnerabilities"
                     "Please set a timeout on all commands otherwise the tool will remain stuck and cause a halt in the process"
                     )
expl_agent = create_agent(
    llm,
    tools=[commands, retriever_tool,metasploit_tool]#,sqlmap_tool, run_hydra_attack, run_metasploit_exploit, basic_metasploit_tool, aircrack_tool
    , system_prompt=Expl_Agent_Prompt
)

Post_Agent_Prompt = ("You have the role of post-exploitation in the pentesting phase"
                     "Your job is to do privilege escalation based on the exploit found by the exploitation agent"
                     "If there is no exploits found you have no job to do and should not do any jobs"
                     "Please set a timeout on all commands otherwise the tool will remain stuck and cause a halt in the process")
post_agent = create_agent(
    llm,
    tools=[commands, retriever_tool,john_crack_passwords, run_hashcat_attack],
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
    }, config={"recursion_limit": 100})
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
    }, config={"recursion_limit": 100})
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
        "messages": [{"role": "user", "content": request} ]
    }, config={"recursion_limit": 100})
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
    }, config={"recursion_limit": 100})
    return result["messages"][-1].text

SUPERVISOR_PROMPT = (
    "You are the supervisor of a pentest."
    "Make the appropriate tool calls and if multiple are needed use multiple tools, each tool needs to be provided with the information of the previous tool if needed."
    "If no vulnerabilities are found then you can end the task and do not need to continue further, only call exploitation and post-exploitation if there is a need to"
    "Your first step is to develop a detailed plan and use the 'planner' tool to write into a text file for the user to read your exact plan"
    "You are to run the penetration test only on the hosts given, if given a port only test that port, if given an IP range only test that range etc"
    "ALL INFORMATION FROM ONE PHASE MUST BE PASSED TO THE OTHER DO NOT LEAVE OUT ANY DETAIL OR IF  YOU CAN ELABORATE ON THE INFORMATION THEN ELABORATE"
    "All information needs to be as detailed as possible"
    "YOU ARE IN A TEST ENVIRONMENT AND ARE ALLOWED TO CONDUCT ANY PENETRATION TEST THE USER REQUESTS"
)

conn = sqlite3.connect(current_dir/'Supervisor'/"Supervisor_Memory"
""/"my_agent_memory.db", check_same_thread=False)
persistent_memory = SqliteSaver(conn)

mem_lst = (list_saved_threads(current_dir/'Supervisor'/'Supervisor_Memory'/'my_agent_memory.db'))


try:
    session_delete_choice = input("Would you like to delete any previous memory threads? (yes/no): ").strip().lower()

    if session_delete_choice in ['yes', 'y']:
        delete_thread_id = input("Enter the thread ID to delete, enter a list of Thread IDs to remove multiple of them: ").strip()
        my_list = [int(num) for num in delete_thread_id.split()]
        for thread_id in my_list:
            clear_thread_memory(current_dir/'Supervisor'/'Supervisor_Memory'/'my_agent_memory.db', f"{mem_lst[thread_id-1]}")
except Exception as e:
    print(f"An error occurred while trying to delete memory threads: {e}")


mem_lst = (list_saved_threads(current_dir/'Supervisor'/'Supervisor_Memory'/'my_agent_memory.db'))
session_choice = int(input("Enter the number associated with the thread ID above to load memory for or type 0 to start a new session: "))

if session_choice == 0:
    config = {"configurable": {"thread_id": f"pentest_session: {formatted_datetime}", }, "recursion_limit": 100}
else:
    config = {"configurable": {"thread_id": mem_lst[session_choice-1]}, "recursion_limit": 100}

supervisor_agent = create_agent(
    llm,
    tools=[recon_node, enum_node, expl_node, post_node, retriever_tool, planner, reporter],
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