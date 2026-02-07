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
from langgraph.graph import StateGraph, END

# subprocess is used to run system commands and capture their outputs.
import subprocess

# json for serializing/deserializing the conversation memory to disk.
import json

# Path from pathlib provides filesystem-safe handling for file paths.
from pathlib import Path
from IPython.display import display,Image
from typing_extensions import NotRequired, Literal
from Enumeration_module.Enumeration import enum_call
from Recon_module.Recon import recon_call
from Post_Exploitation_module.post_exploitation import post_exp_call
from Exploitation_module.Exploitation import exp_call
from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


# --- Simple file-backed conversation memory settings ---
MEMORY_FILE = Path("supervisor_memory.json")  # Path to the file used to persist chat memory
MAX_MEMORY_MESSAGES = 200  # Maximum number of past messages to keep to prevent file bloat

selected_model_supervisor = None  # Global variable to hold the user-selected Ollama model for the supervisor agent

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
# AgentState: defines the graph’s state type, containing message sequence
# ---------------------------------------------------------------------
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]  # Annotated list of BaseMessages tracked by LangGraph

    next:NotRequired[str]  # Added field to track the next agent/role to invoke based on supervisor's decision


graph = StateGraph(AgentState)  # Initialize graph with defined state type

# ---------------------------------------------------------------------
# Creating the supervisor module
# ---------------------------------------------------------------------

agents = ["Recon_agent","Enumeration_agent", "Exploitation_agent", "Post_Exploitation_agent"]

options = ["Objectives_met"] + agents

class RouteOut(BaseModel):
    next: Literal["Objectives_met", "Recon_agent","Enumeration_agent","Exploitation_agent","Post_Exploitation_agent"]


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

def supervisor_call(state: AgentState) -> AgentState:
    """
    Main callable node in the LangGraph. 
    Loads memory, adds new input messages, calls the LLM, saves the updated memory, 
    and returns the new state.
    """
    # Load previously saved conversation memory
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


# ---------------------------------------------------------------------
# Create and connect the LangGraph execution graph
# ---------------------------------------------------------------------

agentic_flow = StateGraph(AgentState)
agentic_flow.add_node("supervisor",supervisor_call)
agentic_flow.add_node("Recon_agent",recon_call)
agentic_flow.add_node("Enumeration_agent",enum_call)
agentic_flow.add_node("Exploitation_agent",exp_call)
agentic_flow.add_node("Post_Exploitation_agent",post_exp_call)

# Events: Worker -> Supervisor
for agent in agents:
    agentic_flow.add_edge(agent, "supervisor")


# Events: Supervisor -> Worker (Conditional)
conditional_map = {j: j for j in agents}
conditional_map["Objectives_met"] = END
agentic_flow .add_conditional_edges("supervisor", lambda x: x["next"], conditional_map)

agentic_flow.set_entry_point("supervisor")

app = agentic_flow.compile()
# ---------------------------------------------------------------------
# Stream printing + interactive loop (single loop; passes HumanMessage)
# ---------------------------------------------------------------------

def save_graph(filename):
    png_bytes = agentic_flow.get_graph().draw_mermaid_png()
    # Try to display if running in an environment that supports it
    try:
        display(Image(png_bytes))
    except Exception:
        pass
    # Always save to file
    with open(filename, "wb") as f:
        f.write(png_bytes)
    print(f"Graph saved as {filename}")


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

    selected_model_supervisor = select_model_func()
    
    # Prompt user for first input
    user_input = input("\nEnter: ")
    # Continue session until user types "exit"
    while user_input != 'exit':
        # Wrap user input into a HumanMessage and pass it to the graph
        human_msg = HumanMessage(content=user_input)
        # Stream responses and print them as they arrive
        _ = print_stream(app.stream({"messages": [human_msg]}, stream_mode="values"))
        # Ask for next user input
        user_input = input("\nEnter: ")


