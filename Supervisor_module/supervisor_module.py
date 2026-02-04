# =============================
# IMPORTS
# =============================

# Importing type annotations and helpers from Python's typing module.
# - TypedDict: used to define a dictionary type with specific key/value types.
# - List, Iterable, Annotated, Sequence: used for static type checking of lists, iterables, annotated types, etc.
from typing import TypedDict, List, Iterable, Annotated, Sequence

# Importing message classes from LangChain’s message system.
# These represent structured messages exchanged between human, AI, and tools.
from langchain_core.messages import BaseMessage, ToolMessage, SystemMessage
from langchain_core.messages import HumanMessage, AIMessage

# The @tool decorator marks a Python function as an LLM tool (executable command).
from langchain_core.tools import tool

# ChatOllama is the LangChain wrapper around the Ollama model runtime.
from langchain_ollama import ChatOllama

# add_messages is a LangGraph helper function that merges and propagates messages in graph states.
from langgraph.graph.message import add_messages

# ToolNode is a predefined LangGraph node type that automatically handles tool execution.
from langgraph.prebuilt import ToolNode

# Import LangGraph’s core graph components for constructing conversational state graphs.
from langgraph.graph import StateGraph, START, END

# subprocess is used to run system commands and capture their outputs.
import subprocess

# json for serializing/deserializing the conversation memory to disk.
import json

from langchain_chroma import Chroma

# Path from pathlib provides filesystem-safe handling for file paths.
from pathlib import Path

from IPython.display import display, Markdown,Image
from langchain_ollama.embeddings import OllamaEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os

# --- Simple file-backed conversation memory settings ---
MEMORY_FILE = Path("supervisor_memory.json")  # Path to the file used to persist chat memory
MAX_MEMORY_MESSAGES = 200  # Maximum number of past messages to keep to prevent file bloat


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
    system_prompt = SystemMessage(
        content="You are the supervisor of AI agents responsible for overseeing their tasks. "
    )

    # Compose full input prompt: system message + memory + current input
    full_prompt = [system_prompt] + mem_msgs + incoming

    # Invoke LLM with full prompt
    response = llm.invoke(full_prompt)

    # Update stored memory with new interaction (adds human + AI messages)
    updated_memory = mem_msgs + incoming + [response]
    save_memory(updated_memory)  # Persist updated memory to disk

    # Return new graph state containing only the model's response
    return {"messages": [response]}

# ---------------------------------------------------------------------
# Define control logic to determine graph continuation
# ---------------------------------------------------------------------
def should_continue(state: AgentState):
    """
    Determines whether the graph should continue (invoke a tool) 
    or stop (end conversation).
    """
    messages = state["messages"]  # Extract message list from current state
    last_message = messages[-1]  # Get the last message in the sequence
    # Check if model returned any tool calls
    if not getattr(last_message, "tool_calls", None):
        return "end"  # No tool call: finish execution
    else:
        return "continue"  # Tool call found: continue to tool node

# ---------------------------------------------------------------------
# Create and connect the LangGraph execution graph
# ---------------------------------------------------------------------
graph = StateGraph(AgentState)  # Initialize graph with defined state type
graph.add_node("super_agent", supervisor_call)  # Add exploitation node (LLM interaction)

#tool_node = ToolNode(tools=tools)  # Node that executes tool calls
#graph.add_node("tools", tool_node)  # Add the tool node to the graph
#graph.add_node("retriever_agent", tool_node)

# Define conditional flow between nodes based on should_continue()
graph.add_conditional_edges(
    "super_agent",
    should_continue,
    {
        "continue": "retriever_agent",  # If tool call exists, go to tools node
        "end": END,  # If not, stop execution
    },
)

#graph.add_edge("retriever_agent", "exp_agent")  # After running a tool, go back to LLM node

graph.set_entry_point("super_agent")

exp = graph.compile()  # Compile graph into runnable pipeline

# ---------------------------------------------------------------------
# Stream printing + interactive loop (single loop; passes HumanMessage)
# ---------------------------------------------------------------------

def save_graph(filename):
    png_bytes = exp.get_graph().draw_mermaid_png()
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
    llm = ChatOllama(model=select_model_func())
    # Prompt user for first input
    user_input = input("\nEnter: ")
    # Continue session until user types "exit"
    while user_input != 'exit':
        # Wrap user input into a HumanMessage and pass it to the graph
        human_msg = HumanMessage(content=user_input)
        # Stream responses and print them as they arrive
        _ = print_stream(exp.stream({"messages": [human_msg]}, stream_mode="values"))
        # Ask for next user input
        user_input = input("\nEnter: ")


