# =============================
# IMPORTS
# =============================

# Importing type annotations and helpers from Python's typing module.
# - TypedDict: used to define a dictionary type with specific key/value types.
# - List, Iterable, Annotated, Sequence: used for static type checking of lists, iterables, annotated types, etc.
from typing import TypedDict, List, Iterable, Annotated, Sequence

# Importing message classes from LangChain’s message system.
# These represent structured messages exchanged between human, AI, and tools.
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_core.messages import HumanMessage, AIMessage

# The @tool decorator marks a Python function as an LLM tool (executable command).
from langchain_core.tools import tool

# ChatOllama is the LangChain wrapper around the Ollama model runtime.
from langchain_ollama import ChatOllama

# add_messages is a LangGraph helper function that merges and propagates messages in graph states.
from langgraph.graph.message import add_messages

# Import LangGraph’s core graph components for constructing conversational state graphs.
from langgraph.graph import MessagesState, END

# subprocess is used to run system commands and capture their outputs.
import subprocess

# json for serializing/deserializing the conversation memory to disk.
import json

from dotenv import load_dotenv
load_dotenv(dotenv_path='.env', override=True)

# Path from pathlib provides filesystem-safe handling for file paths.
from pathlib import Path
from IPython.display import display,Image
from typing_extensions import NotRequired, Literal
#from Enumeration_module.Enumeration import enum_call
#from Recon_module.Recon import recon_call
#from Post_Exploitation_module.post_exploitation import post_exp_call
#from Exploitation_module.Exploitation import exp_call
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import create_agent
from langgraph.types import Command
from langgraph.graph import START, StateGraph
from langsmith import traceable


# --- Simple file-backed conversation memory settings ---
MEMORY_FILE = Path("supervisor_memory.json")  # Path to the file used to persist chat memory
MAX_MEMORY_MESSAGES = 200  # Maximum number of past messages to keep to prevent file bloat

selected_model_supervisor = 'qwen3.5:397b-cloud'  # Global variable to hold the user-selected Ollama model for the supervisor agent
llm = ChatOllama(model=selected_model_supervisor)

# Helper function to determine message "role" string
def _msg_role(m: BaseMessage) -> str:
    """
    Return a string representing the role of a BaseMessage object.
    """
    if isinstance(m, SystemMessage):  # If the message is from system
        return "system"
    if isinstance(m, HumanMessage):  # If message is from user
        return "human"
    if isinstance(m, AIMessage):  # If message is from AI
        return "ai"
    # fallback for unknown message types (like ToolMessage)
    return m.__class__.__name__.lower()

# Save conversation memory to disk
def save_memory(messages: Iterable[BaseMessage], memory_file: Path = MEMORY_FILE):
    """
    Save a sequence of messages to a JSON file on disk.
    Each message is represented as a dictionary containing 'role' and 'content'.
    """
    out = []  # Container for serializable messages
    for m in messages:
        # Attempt to get message content directly
        try:
            content = m.content
        except Exception:
            # Fallback: convert whole message to string if .content missing
            content = str(m)
        out.append({"role": _msg_role(m), "content": content})  # Store role-content pair
    # Keep only the most recent MAX_MEMORY_MESSAGES
    out = out[-MAX_MEMORY_MESSAGES:]
    # Write the JSON-formatted list to the file
    memory_file.write_text(json.dumps(out, indent=2), encoding="utf-8")

# Load messages from disk into memory
def load_memory(memory_file: Path = MEMORY_FILE, max_messages: int = MAX_MEMORY_MESSAGES) -> List[BaseMessage]:
    """
    Load messages from the memory file and recreate them as BaseMessage objects.
    Returns an empty list if the file doesn't exist or is invalid.
    """
    if not memory_file.exists():  # If file doesn’t exist, return empty memory
        return []
    try:
        data = json.loads(memory_file.read_text(encoding="utf-8"))  # Load JSON content
    except Exception:
        return []  # On any read/parse error, return empty
    msgs: List[BaseMessage] = []  # Will hold reconstructed message objects
    for item in data[-max_messages:]:  # Only take the last 'max_messages' entries
        role = item.get("role", "human")  # Default to 'human' role if missing
        content = item.get("content", "") or ""  # Ensure content is non-null string
        # Reconstruct the appropriate message type based on role
        if role == "system":
            msgs.append(SystemMessage(content=content))
        elif role == "human":
            msgs.append(HumanMessage(content=content))
        elif role == "ai":
            msgs.append(AIMessage(content=content))
        else:
            # Unknown roles become HumanMessages to remain interpretable
            msgs.append(HumanMessage(content=content))
    return msgs

# Prompt user to select an Ollama model interactively
def select_model_func():
    """Interactively let the user select which Ollama model to use."""
    # Run shell command `ollama list` to get all installed models
    proc = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=True)

    # Extract available model names from command output
    installed_models = []
    for line in proc.stdout.splitlines():  # Iterate through each line of output
        if line.strip():  # Skip empty lines
            model_name = line.split()[0]  # Extract first token as model name
            installed_models.append(model_name)  # Store model name
    
    # Dictionary of numbered model options
    model_dict = {
        1: "llama3.2:latest",
        2: "gpt-oss:20b",
        3: "gpt-oss:20b-cloud",
        4: "gpt-oss:120b-cloud",
    }
    
    while True:
        # Display menu of available models
        print("\nSelect a model for Supervisor phase:")
        print("1: llama3.2:latest (less powerful)\n2: gpt-oss:20b (more powerful)\n3: gpt-oss:20b-cloud (more powerful)\n4: gpt-oss:120b-cloud (most powerful, largest)")
        print('')
        try:
            # Get user input for model choice
            model_option = input("Enter model option (number) -> ")
            if model_option.lower() == "exit":  # Allow exiting selection
                print("Goodbye!")
                exit()
            model_option = int(model_option)  # Convert to integer

            if not model_option in model_dict:
                raise  # Trigger exception for invalid number
            else:
                # Ensure selected model is installed locally
                while model_dict[model_option] not in installed_models:
                    print("The selected model is not available. Please choose from the list above.")
                    print(f"Installed Models: {installed_models[1:]}")  # Display installed models
                    model_option = int(input("Enter model option-> "))  # Prompt again
                break  # Valid model found
        except Exception:
            print("What you entered was invalid. Please enter a valid number.")
    
    # Determine which model was selected
    selected_model = None
    for k, v in model_dict.items():
        if model_option == k:
            selected_model = v
            break

    print(f"Selected model: {selected_model}")  # Confirmation output
    return selected_model  # Return selected model name

# ---------------------------------------------------------------------
# Define a callable "tool" that can execute shell commands from AI requests
# ---------------------------------------------------------------------
@tool
def commands(command: str):
    """
    Tool that allows the AI model to run shell commands on the host system.
    Returns the command's stdout, stderr, and exit code.
    """
    result = subprocess.run(
        command,  # The shell command to execute
        shell=isinstance(command, str),  # Run in shell mode if command is a string
        capture_output=True,  # Capture stdout and stderr
        text=True  # Decode output as text instead of bytes
    )
    # Return a tuple of stdout, stderr, and exit code
    return result.stdout.strip(), result.stderr.strip(), result.returncode



recon_agent = create_agent(
                        model=ChatOllama(model=selected_model_supervisor),
                        tools=[commands],
                        system_prompt = "You are the reconnisance agent conducting a pentest, you are only to do reconnisance on the inforamtion given to you by the supervisor agent to find information, return your output to the supervisor"
                )
'''
enum_agent = create_agent(
    llm=selected_model_supervisor,
    tools = commands,
    system_prompt = "You are the enumeration agent conducting a pentest, you are only to do enumeration on the inforamtion given to you by the recon/supervisor agents to find vulnerabilities, return your output to the supervisor"
)

exploit_agent = create_agent(
    llm=selected_model_supervisor,
    tools = commands,
    system_prompt = "You are the exploitation agent conducting a pentest, you are only to do exploitation on the inforamtion given to you by the enumeration/supervisor agents to exploit vulnerabilities, return your output to the supervisor"
)

post_agent = create_agent(
    llm=selected_model_supervisor,
    tools = commands,
    system_prompt = "You are the post exploitation agent conducting a pentest, you are only to do priviledge escalation and keep persistance on the inforamtion given to you by the exploitation/supervisor agents to exploit further vulnerabilities, return your output to the supervisor"
)
'''


#def enum_node(state: AgentState):
#    result = enum_agent.invoke(state)
#    return Command(
#        update={
#            "messages": state["messages"] + [
#                AIMessage(content=result["messages"][-1].content, name="enum_node")
#            ]
#        },
#        goto="supervisor"
#    )

#def exploit_node(state: AgentState):
#    result = exploit_agent.invoke(state)
#    return Command(
#        update={
#            "messages": state["messages"] + [
#                AIMessage(content=result["messages"][-1].content, name="exploit_node")
#            ]
#        },
#        goto="supervisor"
#    )

#def post_node(state: AgentState):
#    result = post_agent.invoke(state)
#    return Command(
#        update={
#            "messages": state["messages"] + [
#                AIMessage(content=result["messages"][-1].content, name="post_node")
#            ]
#        },
#        goto="supervisor"
#    )


# ---------------------------------------------------------------------
# AgentState: defines the graph’s state type, containing message sequence
# ---------------------------------------------------------------------
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]  # Annotated list of BaseMessages tracked by LangGraph

    next:NotRequired[str]  # Added field to track the next agent/role to invoke based on supervisor's decision


graph = StateGraph(AgentState)  # Initialize graph with defined state type

# ---------------------------------------------------------------------
# Creating the supervisor module
# ---------------------------------------------------------------------
@traceable
def recon_node(state:AgentState):
    result = recon_agent.invoke(state)
    return Command(
        update={
            "messages": state["messages"] + [
                AIMessage(content=result["messages"][-1].content, name="recon_node")
            ]
        },
        goto="supervisor"
    )



agents = {'recon_node': 'specialized agent for reconnisance in the penetration test workflow'}

options = list(agents.keys()) + ["FINISH"]

worker_info = '\n\n'.join([f'WORKER: {member} \nDESCRIPTION: {description}' for member, description in agents.items()]) + '\n\nWORKER: FINISH \nDESCRIPTION: If User Query is answered and route to Finished'

system_prompt = (
    f"You are the supervisor of AI agents responsible for overseeing their tasks to complete a penetration test. "
    f"Managing a conversation between the following workers: {agents}. "
    f"Given the user request, respond with the worker to act next. "
    f"You MUST respond ONLY with a valid JSON object in this exact format, nothing else:\n"
    f'{{ "next": "<worker_name>", "reasoning": "<your reasoning>" }}\n'
    f"Valid values for 'next' are: {options}"
)

class Router(TypedDict):
    """Worker to route to next. If no workers needed, route to FINISH. and provide reasoning for the routing"""

    next: Annotated[Literal[*options], ..., "worker to route to next, route to FINISH"]
    reasoning: Annotated[str, ..., "Support proper reasoning for routing to the worker"]

'''
route_tool = {
  "type": "function",
  "function": {
    "name": "route",
    "description": "Select the next role.",
    "parameters": {
      "type": "object",
      "properties": {
        "next": {
          "type": "string",
          "description": "Next role",
          "enum": options,        
        }
      },
      "required": ["next"],
      "additionalProperties": False,
    },
  },
}

tools = [route_tool]
'''

keys = list(agents.keys())
@traceable
def supervisor_node(state: AgentState) -> Command[Literal[*keys, "__end__"]]:
    """
    Main callable node in the LangGraph. 
    Loads memory, adds new input messages, calls the LLM, saves the updated memory, 
    and returns the new state.
    """
    messages = [
        {"role": "system", "content": system_prompt},
    ] + [state["messages"][-1]]
    query = ''
    if len(state['messages'])==1:
        query = state['messages'][0].content
    response = llm.with_structured_output(Router, method="json_mode").invoke(messages)
    goto = response.next
    if goto == "FINISH":
        goto = END
    if query:
        return Command(goto=goto, update={"next": goto,'query':query,'cur_reasoning':response.reasoning,
                        })
    return Command(goto=goto, update={"next": goto,'cur_reasoning':response["reasoning"]})

'''    # Load previously saved conversation memory
    mem_msgs = load_memory()

    # Normalize input messages from state into BaseMessage objects
    incoming: List[BaseMessage] = []
    for m in state["messages"]:
        if isinstance(m, BaseMessage):  # Already a message object
            incoming.append(m)
        else:
            incoming.append(HumanMessage(content=str(m)))  # Coerce non-message input into HumanMessage

    # Define the system-level prompt for this LLM call
    
    system_text =f"You are the supervisor of AI agents responsible for overseeing their tasks to complete a penetration test."\
        f"managing a conversation between the following workers: {agents}. Given the following user request, respond with the worker to act next.\
      Each worker will perform a task and respond with their results and status. When finished, respond with Objectives_met."
    

    # Compose full input prompt: system message + memory + current input

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_text),
        MessagesPlaceholder(variable_name="messages"),
        ("system", f"Pick exactly one: {', '.join(options)}")
    ])


    llm = ChatOllama(model=selected_model_supervisor)
    supervisor_chain = prompt | llm.with_structured_output(RouteOut)

    routed: RouteOut = supervisor_chain.invoke({"messages": mem_msgs + incoming})
    next_role = routed.next

    ai_msg = AIMessage(content=f"ROUTE={next_role}")
    save_memory(mem_msgs + incoming + [ai_msg])

    return {"messages": [ai_msg], "next": next_role}
    
    #response = supervisor_chain.invoke({"messages": incoming})

    #next_role = response["args"]["next"]
    #full_prompt = [system_prompt] + mem_msgs + incoming

    # Invoke LLM with full prompt
    #response = llm.invoke(full_prompt)

    # Update stored memory with new interaction (adds human + AI messages)
    #updated_memory = mem_msgs + incoming + [response]
    #save_memory(updated_memory)  # Persist updated memory to disk

    # Return new graph state containing only the model's response
    #return {"messages": [response], "next": next_role}
'''

# ---------------------------------------------------------------------
# Create and connect the LangGraph execution graph
# ---------------------------------------------------------------------

agent = StateGraph(AgentState)
agent.add_edge(START, "supervisor")
agent.add_node("supervisor", supervisor_node)
agent.add_node("recon_node", recon_node)
graph  =agent.compile()

app = agent.compile()
# ---------------------------------------------------------------------
# Stream printing + interactive loop (single loop; passes HumanMessage)
# ---------------------------------------------------------------------
'''
def save_graph(filename):
    png_bytes = agent.get_graph().draw_mermaid_png()
    # Try to display if running in an environment that supports it
    try:
        display(Image(png_bytes))
    except Exception:
        pass
    # Always save to file
    with open(filename, "wb") as f:
        f.write(png_bytes)
    print(f"Graph saved as {filename}")

save_graph('graph.png')
'''
# ---------------------------------------------------------------------
# Streaming output printer: handles incremental message printing
# ---------------------------------------------------------------------
def print_stream(stream):
    """
    Iterates over a streaming LangGraph output and prints each message nicely.
    """
    for s in stream:  # Iterate over message stream events
        message = s["messages"][-1]  # Get the most recent message
        if isinstance(message, tuple):  # If it's a tuple (e.g. command output)
            print(message)
        else:
            try:
                message.pretty_print()  # Use LangChain’s formatted print method
            except Exception:
                print(message)  # Fallback: print raw message

# ---------------------------------------------------------------------
# Main entry point for interactive session
# ---------------------------------------------------------------------
if __name__ == "__main__":
    # Clear memory file at startup by opening and closing it in write mode
    open("supervisor_memory.json", 'w').close()
    # Ask user to select model, then initialize ChatOllama LLM bound with tools

    
    # Prompt user for first input
    user_input = input("\nEnter: ")
    inputs = [
        HumanMessage(content=user_input)
    ]
    config = {"configurable": {"thread_id": "1", "recursion_limit": 10}} 
    
    state = {'messages': inputs}
    result = graph.invoke(input=state)
    # Continue session until user types "exit"
''' while user_input != 'exit':
        # Wrap user input into a HumanMessage and pass it to the graph
        human_msg = HumanMessage(content=user_input)
        # Stream responses and print them as they arrive
        _ = print_stream(app.stream({"messages": [human_msg]}, stream_mode="values"))
        # Ask for next user input
        user_input = input("\nEnter: ")'''



