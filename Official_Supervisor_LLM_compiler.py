
import os
from dotenv import load_dotenv
from langchain import tools
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
import httpx
import dns.resolver
import ssl
import socket
from pathlib import Path
from langchain_chroma import Chroma
from VectorDB_creator import create_vector_db
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
import datetime
from langgraph.errors import GraphRecursionError
from Tools.Recon_tools import *
from Tools.Enum_tools import * 
from Tools.Exp_tools import *
from Tools.Post_exp_tools import * 
from langchain_core.messages import HumanMessage, AIMessage
from LLM_compiler import *

current_datetime = datetime.datetime.now()

formatted_datetime = current_datetime.strftime("%B %d, %Y %H:%M:%S")





#PLAN_FILE = "plan.txt"
#RECON_FILE = 'recon.txt'

llm = ChatOllama(model='qwen3.5:397b-cloud',temperature=0).bind(format="json")

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
def reporter(report: str) -> None:
    """
    Writes the provided text content to a new, uniquely timestamped file in the current directory.

    Use this function to persistently save generated reports, logs, or outputs to disk. 
    It automatically constructs a filename using the current date and time 
    (e.g., 'report_YYYY-MM-DD_HH-MM-SS.txt') to ensure no existing files are overwritten.

    Args:
        report (str): The text content to be written to the file.
    """
    filename = f"report_{current_datetime.strftime('%Y-%m-%d_%H-%M-%S')}.txt"
    with open(current_dir/f'{filename}', 'w', encoding='utf-8') as f:
        f.write(report)



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
    "You have a set of tools at your disposal, please use the best fitting tool and if it does not exist you have access to the commands tool"
    "The commands tool gives you access to run any command you want on a kali linux system, when you are asked to do recon you need to do a full report"
)

recon_agent = create_agent(
    llm,
    tools=[port_scanner, host_discovery, telnet_probe, ftp_probe, probe_http, get_tls_info, dns_lookup, commands, retriever_tool],
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
    tools=[commands, retriever_tool,sqlmap_tool, run_hydra_attack, run_metasploit_exploit, basic_metasploit_tool, aircrack_tool]
    , system_prompt=Expl_Agent_Prompt
)

Post_Agent_Prompt = ("You have the role of post-exploitation in the pentesting phase"
                     "Your job is to do privilege escalation based on the exploit found by the exploitation agent"
                     "If there is no exploits found you have no job to do and should not do any jobs")
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
    "Your first step is to develop a detailed plan and use the 'plan' tool to write into a text file for the user to read your exact plan."
)

conn = sqlite3.connect(current_dir/"Supervisor_Memory"
""/"my_agent_memory.db", check_same_thread=False)
persistent_memory = SqliteSaver(conn)

mem_lst = (list_saved_threads(current_dir/'Supervisor_Memory'/'my_agent_memory.db'))


try:
    session_delete_choice = input("Would you like to delete any previous memory threads? (yes/no): ").strip().lower()

    if session_delete_choice in ['yes', 'y']:
        delete_thread_id = input("Enter the thread ID to delete, enter a list of Thread IDs to remove multiple of them: ").strip()
        my_list = [int(num) for num in delete_thread_id.split()]
        for thread_id in my_list:
            clear_thread_memory(current_dir/'Supervisor_Memory'/'my_agent_memory.db', f"{mem_lst[thread_id-1]}")
except Exception as e:
    print(f"An error occurred while trying to delete memory threads: {e}")

try:
    mem_lst = (list_saved_threads(current_dir/'Supervisor_Memory'/'my_agent_memory.db'))
    session_choice = int(input("Enter the number associated with the thread ID above to load memory for or type 0 to start a new session: "))
except Exception as e:
    session_choice = 0
    print(f"An error occurred while trying to select a memory thread a new session will be started: {e}")

    
if session_choice == 0:
    config = {"configurable": {"thread_id": f"pentest_session: {formatted_datetime}"}}
else:
    config = {"configurable": {"thread_id": mem_lst[session_choice-1]}}

supervisor_agent = create_agent(
    llm,
    tools=[recon_node, enum_node, expl_node, post_node, retriever_tool,reporter],
    system_prompt=SUPERVISOR_PROMPT,
    checkpointer=persistent_memory
)

# Plan execute begins

def supervisor_node(state: CompilerState) -> dict:
    query = state["input"]
    response = supervisor_agent.invoke({
        "messages": [{"role": "user", "content": query}]
    })
    return {"plan": response["messages"][-1].text}

tools = [recon_node, enum_node, expl_node, post_node,retriever_tool,reporter]
tool_map = {t.name: t for t in tools}

def extract_json_from_llm(text: str) -> str:
    """Removes markdown code blocks around JSON returned by the LLM."""
    # Strip whitespace
    text = text.strip()

    text = re.sub(r"\s*```$", "", text)
    return text

# ==========================================
# 4. The Planner Node 
# ==========================================
def planner_node(state: CompilerState) -> dict:
    query = state["input"]
    tool_desc = "\n".join([f"- {t.name}: {t.description}" for t in tools])
    
    # --- NEW: Extract history and feedback ---
    # We use the accumulated results as the history of what was tried
    history_str = json.dumps(state.get("results", {}), indent=2)
    # If it's the first run, there won't be feedback yet
    feedback = state.get("feedback", "No previous feedback. This is the first iteration.")
    
    # --- UPDATE: Add history and feedback to the format call ---
    prompt = PLANNER_PROMPT.format(
        tool_descriptions=tool_desc, 
        query=query,
        history=history_str,
        feedback=feedback
    )
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        clean_text = extract_json_from_llm(response.content)
        plan = json.loads(clean_text)
        if isinstance(plan, dict):
            plan = plan.get("plan", plan.get("tasks", []))
        if not isinstance(plan, list):
            print(f"⚠️ Warning: Expected plan to be a list, got {type(plan).__name__}. Defaulting to empty plan.")
            plan = []
    except json.JSONDecodeError:
        print("⚠️ Warning: Planner failed to output valid JSON. Defaulting to empty plan.")
        plan = [] 
        
    return {"plan": plan}


# ==========================================
# 5. The Executor Node (Task Fetching Unit)
# ==========================================
def execute_node(state: CompilerState):
    plan = state.get("plan", [])
    # We make a copy of results so we don't accidentally mutate state directly
    results = dict(state.get("results", {}))
    
    # Iterate through the DAG plan
    for task in plan:
        # Guard clause: Ensure the task is actually a dictionary before calling .get()
        if not isinstance(task, dict):
            print(f"⚠️ Warning: Invalid task format (expected dict, got {type(task).__name__}). Skipping: {task}")
            continue
            
        task_id = str(task.get("id", "unknown"))
        
        # Skip if already executed in a previous loop
        if task_id in results:
            continue
            
        tool_name = task.get("tool")
        args = task.get("args", {})
        
        resolved_args = {}
        
        # Guard clause: Ensure args is a dictionary before iterating
        if isinstance(args, dict):
            # Resolve Dependencies (Variable Substitution)
            for key, val in args.items():
                if isinstance(val, str) and val.startswith("$"):
                    dep_id = val[1:]  # Extract ID (e.g., "$1" -> "1")
                    # Substitute the previous tool's output into this argument
                    resolved_args[key] = results.get(dep_id, val)
                else:
                    resolved_args[key] = val
        else:
            # If the LLM generated a string/list instead of a dict, pass it as is
            resolved_args = args
                
        # Execute the Tool
        if tool_name in tool_map:
            print(f"⚙️ Executing Task {task_id}: {tool_name} with args: {resolved_args}")
            try:
                tool_output = tool_map[tool_name].invoke(resolved_args)
                # Cast to string to ensure json.dumps() in joiner_node won't crash
                results[task_id] = str(tool_output)
            except Exception as e:
                results[task_id] = f"Error executing {tool_name}: {str(e)}"
        else:
            results[task_id] = f"Error: Tool '{tool_name}' not found."
            
    return {"results": results}

# ==========================================
# 6. The Joiner Node 
# ==========================================
def joiner_node(state: CompilerState) -> dict:
    query = state["input"]
    results_str = json.dumps(state.get("results", {}), indent=2)
    
    # --- NEW: Setup Iteration Tracking ---
    current_iteration = state.get("iteration", 1)
    MAX_ITERATIONS = 5 # You can adjust this limit
    
    # --- UPDATE: Add current_iteration and max_iterations to format ---
    prompt = JOINER_PROMPT.format(
        query=query, 
        results=results_str,
        current_iteration=current_iteration,
        max_iterations=MAX_ITERATIONS
    )
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    try:
        clean_text = extract_json_from_llm(response.content)
        decision = json.loads(clean_text)
    except json.JSONDecodeError:
        decision = {"action": "finish", "answer": response.content}
        
    if not isinstance(decision, dict):
        decision = {"action": "finish", "answer": str(decision)}
        
    if decision.get("action") == "finish":
        return {"final_answer": decision.get("answer")}
    
        # --- UPDATE: Pass feedback and increment iteration on replan ---
    reason = decision.get("reason", "No specific reason provided.")
    print(f"🔄 Replanning triggered (Iteration {current_iteration}/{MAX_ITERATIONS}). Reason: {reason}")
        
    return {
        "plan": [], 
        "iteration": current_iteration + 1, 
        "feedback": reason
    }

# ==========================================
# 7. Condition Function 
# ==========================================
def should_continue(state: CompilerState):
    if state.get("final_answer"):
        return "end"
    return "planner"


workflow = StateGraph(CompilerState)

workflow.add_node("planner", planner_node)
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("joiner", joiner_node)

workflow.set_entry_point("planner")

workflow.add_edge("planner", "supervisor")
workflow.add_edge("supervisor", "joiner")
workflow.add_conditional_edges(
    "joiner",
    should_continue,
    {
        "end": END,
        "planner": "planner"
    }
)

planner_app = workflow.compile()

# Plan ends 

'''
@tool
def complex_attack_planner(objective: str) -> str:
    """
    Use this tool to plan complex, multi-step penetration testing attacks 
    that require planning, dependency injection, and chained tool execution.
    Input should be the specific security objective or attack path to investigate.
    """
    print(f"\n[Supervisor] 🚨 Delegating heavy-lifting to complex_attack_planner...")
    print(f"[Supervisor] Objective: {objective}\n")
    
    inputs = {"input": objective, "plan": [], "results": {}}
    
    try:
        # UPGRADE 1: Set a strict recursion limit to prevent infinite replanning loops
        config = {"recursion_limit": 10} 
        
        # Run the nested graph
        final_state = planner_app.invoke(inputs, config=config)
        
        # UPGRADE 2: Extract the plan to show the supervisor *how* we got the answer
        executed_plan = final_state.get("plan", [])
        plan_summary = ", ".join([task.get("tool", "unknown") for task in executed_plan])
        
        final_answer = final_state.get("final_answer", "No definitive conclusion reached.")
        
        print(f"\n[Supervisor] 🏁 Attack planner completed its execution.")
        
        # Return a richer context to the supervisor
        return f"Execution Path Used: [{plan_summary}]\n\nFinal Report: {final_answer}"

    except GraphRecursionError:
        return "Error: The attack planner got stuck in an infinite loop and was terminated to save resources."
    except Exception as e:
        return f"Error: The complex attack planner encountered a critical failure: {str(e)}"
    '''
# Planning end 

exit_conditions = ["end","quit","exit","stop","done","finished"]
print(f"Welcome to the Multi-Agentic AI Pentesting Framework. Type your commands to start the pentesting process. Type any of the following to finish: {exit_conditions}")
query = input("Enter->: ")

while query not in exit_conditions:

    for step in planner_app.stream(
        {"input": query},config=config):
        for update in step.values():
            if type(update) == type(None):
                update = {"messages": [AIMessage(content="No response from LLM.")]}
            for message in update.get("messages", []):
                message.pretty_print()

    query = input("Enter->: ")