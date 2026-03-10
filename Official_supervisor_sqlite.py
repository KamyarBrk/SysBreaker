
import os
from dotenv import load_dotenv


from langchain_ollama import ChatOllama
from langchain.tools import tool
from langchain.agents import create_agent
from nmap import nmap
#import vulners
from langchain_ollama.embeddings import OllamaEmbeddings

from pathlib import Path
from langchain_chroma import Chroma
from VectorDB_creator import create_vector_db
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
import datetime

current_datetime = datetime.datetime.now()

formatted_datetime = current_datetime.strftime("%B %d, %Y %H:%M:%S")

#load_dotenv(dotenv_path='.env', override=True)

#vulners_api = os.getenv("VULNERS_API_KEY")

llm = ChatOllama(model='qwen3.5:397b-cloud')

try:
    current_dir = Path(__file__).parent
except NameError:
    current_dir = Path.cwd()
#MEMORY_FILE =  current_dir / "recon_memory.json"  # Path to the file used to persist chat memory
#MAX_MEMORY_MESSAGES = 200  # Maximum number of past messages to keep to prevent file bloat



directory_path = Path(current_dir/"vector")

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

def list_saved_threads(db_path: str = "memory.db"):
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

Recon_agent_Prompt = (
    "You are an AI model that performs the reconnaissance phase of a penetration test."
        "Use the given tools provided to better complete the reconnaissance tasks."
    "Do not provide security recommendations that is the job of the enumeration agent, your job is exclusively identifying ports"
)

recon_agent = create_agent(
    llm,
    tools=[port_scanner,retriever_tool],
    system_prompt=Recon_agent_Prompt,
)



Enum_Agent_Prompt = ("You are an AI model that performs the enumeration phase of a penetration test. "
                     "If there is no vulnerability found tell the user there is no vulnerability found for now"
                     "You are to only find the vulnerabilities using the cve_lookup tool"
                     "Your only job is to enumerate the information given to you nothing else, you should always respond to the supervisor whether a vulnerability was found or not")

enumeration_agent = create_agent(
    llm,
    tools=[retriever_tool],
    system_prompt=Enum_Agent_Prompt
)

Expl_Agent_Prompt = ("You have the role of exploiting found vulnerabilities in the target."
                     "If there are no vulnerabilities reported you do not need to do anything"
                     "Use the tools provided to exploit found vulnerabilities."
                     "If you succeeded in exploiting the vulnerability you should list how you did it report you were successful")
expl_agent = create_agent(
    llm,
    tools=[retriever_tool]
    , system_prompt=Expl_Agent_Prompt
)

Post_Agent_Prompt = ("You have the role of post-exploitation in the pentesting phase"
                     "Your job is to do privilege escalation based on the exploit found by the exploitation agent"
                     "If there is no exploits found you have no job to do and should not do any jobs")
post_agent = create_agent(
    llm,
    tools=[retriever_tool],
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
    result = recon_agent.invoke({
        "messages": [{"role": "user", "content": request}]
    })
    return result["messages"][-1].text

@tool
def expl_node(request: str) -> str:
    """
      This is the tool to call the exploit agent to perform exploitation of vulnerabilities that may be on the target system.

      Args:
          request: The request to run the exploitation agent on.

      Returns: The whether or not it succeeded or not.
      """
    result = recon_agent.invoke({
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

SUPERVISOR_PROMPT = (
    "You are the supervisor of a pentest."
    "You currently can do a portscan enumerate possible threats exploit vulnerabilities, and post-exploitation tasks."
    "Make the appropriate tool calls and if multiple are needed use multiple tools, each tool needs to be provided with the information of the previous tool if needed."
    "If no vulnerabilities are found then you can end the task and do not need to continue further, only call exploitation and post-exploitation if there is a need to"
)


conn = sqlite3.connect(current_dir/"Supervisor_Memory"
""/"my_agent_memory.db", check_same_thread=False)
persistent_memory = SqliteSaver(conn)

mem_lst = (list_saved_threads(current_dir/'Supervisor_Memory'/'my_agent_memory.db'))

session_choice = int(input("Enter the number associated with the thread ID above to load memory for or type 0 to start a new session: "))

if session_choice == 0:
    config = {"configurable": {"thread_id": f"pentest_session: {formatted_datetime}"}}
else:
    config = {"configurable": {"thread_id": mem_lst[session_choice-1]}}

supervisor_agent = create_agent(
    llm,
    tools=[recon_node, enum_node, expl_node,post_node,retriever_tool],
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