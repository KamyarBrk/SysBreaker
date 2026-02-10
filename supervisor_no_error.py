# =============================
# IMPORTS
# =============================

# Importing type annotations and helpers from Python's typing module.
# - TypedDict: used to define a dictionary type with specific key/value types.
# - List, Iterable, Annotated, Sequence: used for static type checking of lists, iterables, annotated types, etc.
from typing import TypedDict, List, Iterable, Annotated, Sequence

# Importing message classes from LangChain’s message system.
# These represent structured messages exchanged between human, AI, and tools.
from langchain_core.messages import BaseMessage, SystemMessage,HumanMessage, AIMessage


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
from langchain_core.messages import messages_to_dict, messages_from_dict
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.exceptions import OutputParserException

try:
    current_dir = Path(__file__).parent
except NameError:
    current_dir = Path.cwd()
MEMORY_FILE =  current_dir / "supervisor_memory.json"  # Path to the file used to persist chat memory
MAX_MEMORY_MESSAGES = 200  # Maximum number of past messages to keep to prevent file bloat

selected_model_supervisor = "gpt-oss:120b-cloud"  # Global variable to hold the user-selected Ollama model for the supervisor agent

# Save conversation memory to disk
def save_memory(messages: Iterable[BaseMessage], memory_file: Path = MEMORY_FILE):
    msgs = list(messages)[-MAX_MEMORY_MESSAGES:]
    memory_file.write_text(
        json.dumps(messages_to_dict(msgs), indent=2),
        encoding="utf-8"
    )

def load_memory(memory_file: Path = MEMORY_FILE, max_messages: int = MAX_MEMORY_MESSAGES) -> List[BaseMessage]:
    if not memory_file.exists():
        return []
    try:
        data = json.loads(memory_file.read_text(encoding="utf-8"))
        msgs = messages_from_dict(data)
        return msgs[-max_messages:]
    except Exception:
        return []

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

# ---------------------------------------------------------------------
# Creating the supervisor module
# ---------------------------------------------------------------------

agents = ["Recon_agent","Enumeration_agent", "Exploitation_agent", "Post_Exploitation_agent"]

options = ["Objectives_met"] + agents

class RouteOut(BaseModel):
    next: Literal["Objectives_met", "Recon_agent","Enumeration_agent","Exploitation_agent","Post_Exploitation_agent"]

parser = PydanticOutputParser(pydantic_object=RouteOut)
def supervisor_call(state: AgentState) -> AgentState:
    """
    Routes to exactly one worker (or Objectives_met) based on current penetration testing progress.
    """
    incoming = list(state["messages"])
    
    system_text =f"You are the supervisor of AI agents responsible for overseeing their tasks to complete a penetration test."\
        f"managing a conversation between the following workers: {agents}. Given the following user request, respond with the worker to act next.\
      Each worker will perform a task and respond with their results and status. When finished, respond with Objectives_met."
    

    # Compose full input prompt: system message + memory + current input

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_text),
        MessagesPlaceholder(variable_name="messages"),
        ("system",
         "Pick exactly one of: " + ", ".join(options) + "\n"
         "Return ONLY JSON that matches the schema below.\n"
         "{format_instructions}")
    ]).partial(format_instructions=parser.get_format_instructions())


    llm = ChatOllama(model=selected_model_supervisor, temperature=0, format="json")

    chain = prompt | llm | parser

    routed: RouteOut = chain.invoke({"messages": incoming})
  
    next_role = routed.next # Extract the next role/agent to invoke from the structured output of the supervisor's response

    decision_msg = AIMessage(content=f"[supervisor] next={next_role}") # Create a message representing the supervisor's decision for logging and memory purposes

    return {"messages": [decision_msg], "next": next_role} # Return updated state with the supervisor's decision message and the next role to route to, which will be used by the graph's conditional edges to determine the next node to execute.
    

# ---------------------------------------------------------------------
# Create and connect the LangGraph execution graph
# ---------------------------------------------------------------------

agentic_flow = StateGraph(AgentState)
agentic_flow.add_node("supervisor",supervisor_call) # Add the supervisor node to the graph, which will route to workers based on the current state of messages and the supervisor's logic. The supervisor node takes the current conversation messages as input and outputs a decision on which worker to invoke next.
agentic_flow.add_node("Recon_agent",recon_call) # Add the Recon_agent node to the graph, which will perform reconnaissance tasks. This node will be invoked by the supervisor when it determines that reconnaissance is the next step needed in the penetration testing process.
agentic_flow.add_node("Enumeration_agent",enum_call) # Add the Enumeration_agent node to the graph, which will perform enumeration tasks. This node will be invoked by the supervisor when it determines that enumeration is the next step needed in the penetration testing process.
agentic_flow.add_node("Exploitation_agent",exp_call) # Add the Exploitation_agent node to the graph, which will perform exploitation tasks. This node will be invoked by the supervisor when it determines that exploitation is the next step needed in the penetration testing process.
agentic_flow.add_node("Post_Exploitation_agent",post_exp_call) # Add the Post_Exploitation_agent node to the graph, which will perform post-exploitation tasks. This node will be invoked by the supervisor when it determines that post-exploitation is the next step needed in the penetration testing process.

# Events: Worker -> Supervisor
for agent in agents: # Loop through each worker agent and connect it back to the supervisor node in the graph. This allows each worker to report its results and status back to the supervisor after performing its assigned tasks. By connecting each worker to the supervisor, we enable a feedback loop where the supervisor can evaluate the outcomes of each worker's actions and make informed decisions on which worker should act next based on the updated information from the workers.
    agentic_flow.add_edge(agent, "supervisor") # Connect each worker node back to the supervisor node, allowing the workers to report their results and status back to the supervisor after they perform their tasks. This way, after each worker completes its assigned task, it can trigger the supervisor to evaluate the current state of the penetration test and decide which worker should act next based on the updated information.


# Events: Supervisor -> Worker (Conditional)
conditional_map = {j: j for j in agents}
conditional_map["Objectives_met"] = END # If the supervisor determines that the objectives have been met, we route to the END node to terminate the graph execution.
agentic_flow .add_conditional_edges("supervisor", lambda x: x["next"], conditional_map)

agentic_flow.set_entry_point("supervisor") # Set the supervisor as the entry point of the graph, meaning that when we invoke the graph, it will start execution at the supervisor node. The supervisor will then determine which worker to route to based on the current state of messages and the logic defined in the supervisor_call function. By setting the supervisor as the entry point, we ensure that all interactions with the graph begin with the supervisor's decision-making process, allowing it to effectively manage and coordinate the actions of the worker agents throughout the penetration testing workflow.

supervisor_app = agentic_flow.compile() # Compile the graph into an executable application. This step processes the defined nodes, edges, and conditional logic in the graph to create a runnable application that we can invoke with input data. By compiling the graph, we transform our high-level definition of the supervisor-worker interactions into a concrete implementation that can be executed to perform the desired tasks in an organized and efficient manner.
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
    for s in stream:
        message = s["messages"][-1]
        
        # FIX: prevent echoing the user's input back to the console
        if isinstance(message, HumanMessage):
            continue

        try:
            message.pretty_print()
        except Exception:
            print(message)

# ---------------------------------------------------------------------
# Main entry point for interactive session
# ---------------------------------------------------------------------
if __name__ == "__main__":
    
    if not MEMORY_FILE.exists():
        MEMORY_FILE.write_text("[]", encoding="utf-8")  # Initialize with empty list to ensure valid JSON structure
     

    # Ask user to select model, then initialize ChatOllama LLM bound with tools
    selected_model_supervisor = select_model_func()
    
    history = load_memory()  # Load any existing conversation history from disk
    # Prompt user for first input
    user_input = input("\nEnter: ")
    # Continue session until user types "exit"
    while user_input != 'exit':
        # Wrap user input into a HumanMessage and pass it to the graph
        human_msg = HumanMessage(content=user_input)
        # Stream responses and print them as they arrive
        
        final_state = None
        for s in supervisor_app.stream( 
            {"messages": history + [human_msg]},
            stream_mode="values"
        ):    # Stream the graph's output, which will yield intermediate states as the supervisor and workers process the input. We will print each message as it arrives and keep track of the final state after the graph finishes processing.
            final_state = s
            print_stream([s])

        if final_state is not None:
            history = list(final_state["messages"])[-MAX_MEMORY_MESSAGES:] # Update conversation history with the latest messages from the graph's final state, keeping only the most recent ones to prevent memory bloat.
            save_memory(history)  # Save updated conversation history to disk
        # Ask for next user input
        user_input = input("\nEnter: ") # Prompt the user for the next input, allowing them to continue the conversation and interact with the supervisor and worker agents until they choose to exit by typing "exit".
