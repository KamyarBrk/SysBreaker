
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
    "Do not provide security recommendations that is the job of the enumeration agent, your job is exclusively identifying ports"
)

recon_agent = create_agent(
    llm,
    tools=[port_scanner],
    system_prompt=Recon_agent_Prompt,
)



Enum_Agent_Prompt = ("You are an AI model that performs the enumeration phase of a penetration test. "
                     "If there is no vulnerability found tell the user there is no vulnerability found for now"
                     "You are to only find the vulnerabilities using the cve_lookup tool"
                     "Your only job is to enumerate the information given to you nothing else, you should always respond to the supervisor whether a vulnerability was found or not")

enumeration_agent = create_agent(
    llm,
    tools=[cve_lookup],
    system_prompt=Enum_Agent_Prompt
)

Expl_Agent_Prompt = ("You have the role of exploiting found vulnerabilities in the target."
                     "If there are no vulnerabilities reported you do not need to do anything"
                     "Use the tools provided to exploit found vulnerabilities."
                     "If you succeeded in exploiting the vulnerability you should list how you did it report you were successful")
expl_agent = create_agent(
    llm,
    tools=[]
    , system_prompt=Expl_Agent_Prompt
)

Post_Agent_Prompt = ("You have the role of post-exploitation in the pentesting phase"
                     "Your job is to do privilege escalation based on the exploit found by the exploitation agent"
                     "If there is no exploits found you have no job to do and should not do any jobs")
post_agent = create_agent(
    llm,
    tools=[],
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

supervisor_agent = create_agent(
    llm,
    tools=[recon_node, enum_node, expl_node],
    system_prompt=SUPERVISOR_PROMPT,
)

query = "Run as much of a pentest as you can on 127.0.0.1"


for step in supervisor_agent.stream(
    {"messages": [{"role": "user", "content": query}]}
):
    for update in step.values():
        for message in update.get("messages", []):
            message.pretty_print()
