import operator
from typing import Annotated, List, Tuple, TypedDict, Union
from pydantic import BaseModel, Field
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from langchain.agents import create_agent 
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
# --- UPDATED IMPORT ---
from langchain_ollama import ChatOllama

# -----------------------------------------------------------------------
# 1. Define the State
# -----------------------------------------------------------------------


critical_instructions = "CRITICAL INSTRUCTIONS: You must respond strictly in raw JSON format. Do not include markdown code blocks (like ```json). Do not include any conversational text before or after the JSON"

class PlanExecuteState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    plan: List[str]
    past_steps: Annotated[List[Tuple], operator.add]
    response: str

# -----------------------------------------------------------------------
# 2. Define Output Schemas
# -----------------------------------------------------------------------
class Plan(BaseModel):
    """Plan to follow in future"""
    steps: List[str] = Field(description="Different steps to follow, should be in sorted order")

class Response(BaseModel):
    """Response to user."""
    response: str

class Act(BaseModel):
    """Action to perform."""
    action: Union[Response, Plan] = Field(
        description="Action to perform. If you want to respond to user, use Response. "
                    "If you need to further use tools to get the answer, use Plan."
    )

# -----------------------------------------------------------------------
# 3. Initialize LLM and Tools
# -----------------------------------------------------------------------
# Make sure your TAVILY_API_KEY is set in your environment
# Ensure you have pulled the model in Ollama (e.g., `ollama run llama3.1`)
#llm = ChatOllama(model='qwen3.5:397b-cloud',temperature=0)


# -----------------------------------------------------------------------
# 4. Create the Planner
# -----------------------------------------------------------------------
planner_prompt = ChatPromptTemplate.from_messages([
    ("system", "For the given objective, come up with a simple step by step plan. "
               "This plan should involve individual tasks, that if executed correctly will yield the correct answer. "
               "Do not add any superfluous steps. The result of the final step should be the final answer. "
               "Make sure that each step has all the information needed - do not skip steps. {}".format(critical_instructions)),
    ("user", "{objective}")
])



# -----------------------------------------------------------------------
# 5. Create the Executor
# -----------------------------------------------------------------------


# -----------------------------------------------------------------------
# 6. Create the Replanner
# -----------------------------------------------------------------------
replanner_prompt = ChatPromptTemplate.from_messages([
    ("system", "For the given objective, come up with a simple step by step plan. "
               "This plan should involve individual tasks, that if executed correctly will yield the correct answer. "
               "Do not add any superfluous steps. The result of the final step should be the final answer. "
               "Make sure that each step has all the information needed - do not skip steps.\n\n"
               "Your objective was this: {input}\n\n"
               "Your original plan was this: {plan}\n\n"
               "You have currently done the following steps:\n{past_steps}\n\n"
               "Update your plan accordingly. If no more steps are needed and you can return to the user, then respond with that. "
               "Otherwise, fill out the plan. Only add steps to the plan that still NEED to be done. Do not return previously done steps as part of the plan."),
    ("user", "Update the plan or respond. ")
])



# -----------------------------------------------------------------------
# 7. Build the Graph
# -----------------------------------------------------------------------


# -----------------------------------------------------------------------
# 8. Execute the Agent
# -----------------------------------------------------------------------

'''
if __name__ == "__main__":
    config = {"recursion_limit": 50} 
    inputs = {"input": "Who is the winner of the 2024 US Open tennis tournament, and what is their hometown?"}
    
    for event in app.stream(inputs, config=config):
        for k, v in event.items():
            if k != "__end__":
                print(f"\n--- Output from {k} ---")
                print(v)

                '''