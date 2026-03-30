import json
import re
from typing import Annotated, Any, Dict, List, TypedDict
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, END

# 1. State Definition
class CompilerState(TypedDict):
    input: str
    plan: List[Dict[str, Any]]
    results: Dict[str, str]
    final_answer: str
    # --- ADD THESE NEW FIELDS ---
    iteration: int
    feedback: str

# 2. Prompts (Unchanged, as they were already well-structured for JSON)
PLANNER_PROMPT = """You are a highly efficient planning agent. Given a user query, create a plan to solve it with maximum parallelizability. 

You have access to the following tools:
{tool_descriptions}

Previous Execution History (Do NOT repeat failed steps):
{history}

Feedback from Red Team Lead (Joiner):
{feedback}

Output your plan strictly as a JSON object containing a "tasks" array. Each task MUST have:
1. "id": A unique string ID starting from "1".
2. "tool": The name of the tool to use.
3. "args": A dictionary of arguments for the tool.

IMPORTANT - DEPENDENCY INJECTION: 
If an argument depends on the output of a previous task, use the format "$ID" (e.g., "$1") as the value. This allows parallel execution!

Example Output Format:
{{
  "tasks": [
    {{"id": "1", "tool": "search_cve", "args": {{"query": "latest exploit POCs for CVE-2023-38408"}}}},
    {{"id": "2", "tool": "calculate_cvss", "args": {{"expression": "10.0 - 1.5"}}}} 
  ]
}}

User Query: {query}
"""

JOINER_PROMPT = """You are the Red Team Lead (Joiner agent). Your job is to evaluate the results of the executed penetration testing plan and decide if you have successfully gathered enough actionable intelligence to fulfill the objective, OR if you have exhausted all viable options.

Target/Objective: {query}

Current Iteration: {current_iteration} of {max_iterations}

Execution Results from Security Tools:
{results}

Evaluate the results and choose one of the following actions. Output strictly as a JSON object:

1. OBJECTIVE ACHIEVED (OR TARGET SECURE):
If you have confirmed a vulnerability path, found the exploit, OR definitively proven that the target is not vulnerable based on the available tools, output:
{{"action": "finish", "answer": "Your comprehensive vulnerability summary, final attack path, OR conclusion that no viable attack path exists."}}

2. DEAD END / EXHAUSTED OPTIONS:
If the tools yield no new information, if you are stuck in a loop, or if {current_iteration} has reached {max_iterations}, you MUST terminate the operation. Output:
{{"action": "finish", "answer": "Operation terminated. Exhausted all available enumeration vectors without finding a viable exploit path. Summary of findings: ..."}}

3. PIVOT AND REPLAN (PROCEED WITH CAUTION):
If you DO NOT have enough information but see a CLEAR, UNTRIED, and SPECIFIC new vector to explore, output:
{{"action": "replan", "reason": "Explain exactly what new specific intelligence is needed so the planner can formulate a NEW attack path. Do not request steps that have already failed."}}
"""

# 3. Initialize LLM strictly in JSON mode
# Note: Ensure you have a model pulled that supports this well, like llama3.1
#llm = ChatOllama(model="qwen3.5:397b-cloud", format="json", temperature=0)
