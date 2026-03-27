import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain.tools import tool
from langchain.agents import create_agent
from nmap import nmap
from langchain_ollama.embeddings import OllamaEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
import telnetlib3
import subprocess
import requests
import ftplib
from pathlib import Path
from langchain_chroma import Chroma
from VectorDB_creator import create_vector_db
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
import datetime