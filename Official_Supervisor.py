
import os
from dotenv import load_dotenv
load_dotenv(dotenv_path='.env', override=True)
vulners_api = os.getenv("VULNERS_API_KEY")

from langchain_ollama import ChatOllama
from langchain.tools import tool
from langchain.agents import create_agent
from nmap import nmap
import vulners

from Recon_module.Recon import tools

llm = ChatOllama(model='qwen3.5:397b-cloud')

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


Recon_agent_Prompt = (
    "You are an AI model that performs the reconnaissance phase of a penetration test."
        "Use the given tools provided to better complete the reconnaissance tasks."
)

recon_agent = create_agent(
    llm,
    tools=[port_scanner],
    system_prompt=Recon_agent_Prompt,
)



Enum_Agent_Prompt = ("You are an AI model that performs the enumeration phase of a penetration test. "
                     "If there is no vulnerability found tell the user there is no vulnerability found for now")

enumeration_agent = create_agent(
    llm,
    tools=[cve_lookup],
    system_prompt=Enum_Agent_Prompt
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

SUPERVISOR_PROMPT = (
    "You are the supervisor of a pentest."
    "You currently can do a portscan and enumerate possible threats"
    "Make the appropriate tool calls and if multiple are needed use multiple tools"
)

supervisor_agent = create_agent(
    llm,
    tools=[recon_node, enum_node],
    system_prompt=SUPERVISOR_PROMPT,
)

query = "Run as much of a pentest as you can on 127.0.0.1"


for step in supervisor_agent.stream(
    {"messages": [{"role": "user", "content": query}]}
):
    for update in step.values():
        for message in update.get("messages", []):
            message.pretty_print()
