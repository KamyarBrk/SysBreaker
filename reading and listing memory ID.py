import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

def read_saved_memory(db_path: str = "memory.db"):
    """Loads and displays LangGraph memory without needing the Graph code."""
    
    # 1. Connect to your existing database
    # Make sure 'db_path' points to the same file your main graph uses
    with sqlite3.connect(db_path, check_same_thread=False) as conn:
        
        # 2. Initialize the checkpointer independently
        memory = SqliteSaver(conn)
        
        # 3. Ask the user which memory to load
        thread_id = input("Enter the thread ID to load memory for: ").strip()
        config = {"configurable": {"thread_id": thread_id}}
        
        # 4. Fetch the checkpoint data directly from SQLite
        checkpoint_tuple = memory.get_tuple(config)
        
        if not checkpoint_tuple:
            print(f"\nNo memory found for thread ID: {thread_id}")
            return
            
        # 5. Extract the state
        # LangGraph stores the actual graph state inside 'channel_values'
        saved_state = checkpoint_tuple.checkpoint.get("channel_values", {})
        
        print(f"\n--- Memory Loaded for {thread_id} ---")
        
        # 6. Display the messages (Assuming your state uses a "messages" key)
        if "messages" in saved_state:
            for msg in saved_state["messages"]:
                # 'msg' is usually a LangChain message object (HumanMessage, AIMessage)
                # If they are serialized dicts, you'd use msg['type'] and msg['content']
                try:
                    role = msg.__class__.__name__.replace("Message", "")
                    content = msg.content
                    print(f"[{role}]: {content}\n")
                except AttributeError:
                    # Fallback if they are raw dictionaries
                    print(f"{msg}\n")
        else:
            # If your graph state doesn't use 'messages', just print the raw state
            print("Raw State Dictionary:")
            print(saved_state)



def list_saved_threads(db_path: str = r"C:\Users\George\Documents\CYSE492\CYSE492-Group-22\Supervisor_Memory\my_agent_memory.db"):
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



def clear_thread_memory(db_path: str, thread_id: str):
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

