This is CYSE 492 Group 22's repo for their agentic penetration testing AI. It is written entirely in Python, and uses existing AI models to carry out its tasks. Retrieval Augmented Generation (RAG) is used to provide additional information to the models without the need to retrain them. 

The overall system is built out of several different modules to carry out the steps of penetration testing. These modules are designed to run sequentially, and pass information to each other. They are centered around two open-source tools: Langgraph and Ollama. Langgraph allows for the easy construction of stateful, multi-agent programs by creating workflows as graphs. Ollama allows us to interact with different AI models using the same API (Application programming interface). This means we can easily switch between AI models without rewriting code.

Rundown of the modules

	**Recon**
	Uses common tools in Kali Linux such as nmap to discover information about the environment that is being tested. 

	**Enumeration**
	Using information gathered by the recon module and instructions in PDF files regarding the tools it needs to use, it identifies
	vulnerabilities in the environment. It runs commands via the command-line tool. 

	**Exploitation**
	Attempts to exploit the identified vulnerabilities by the Enumeration module.

	**Post-Exploitation**
	Analyzes the results of the exploitation module and suggests fixes to the environment.

**AI Model Setup Instructions**

Before running any scripts, Ollama must be downloaded. You can get it from https://ollama.com/download

**Local Python Environment Setup Instructions**

1. Clone the repo locally in VS code
2. Open the folder in VS Code
3. Run `.\setup.ps1` (Windows) or `chmod +x setup.sh` & `./setup.sh` (macOS/Linux) in the terminal. Note you need Python 3.11 or 3.12. 

Make sure you are in the virtual environment before attempting to run any modules!
