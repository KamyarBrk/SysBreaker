

from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader

from langchain_ollama.embeddings import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pathlib import Path
from langchain_chroma import Chroma
import os 



def create_vector_db():
    

    embeddings = OllamaEmbeddings(
        model="nomic-embed-text"  # use the ollama run nomic-embed-text the first time you run this code
    )

    try:
        #training_data_path = Path(__file__).resolve().with_name("Training_documents")
        training_data_path = Path(__file__).resolve().with_name("Test_doc")
    except Exception as e:
        print(f"Error determining training data path: {e}")
        raise




    pdf_loader = DirectoryLoader(
        path=training_data_path,
        glob="**/*.pdf",         # The "**/" tells it to search all subfolders
        loader_cls=PyPDFLoader,  # Tells it to process the files it finds as PDFs
        show_progress=True       # Gives you a nice progress bar in the terminal
    )

    try:
        print("Scanning directories and loading PDFs. This might take a moment...")
        # This will now load every page from every PDF across all 4 subfolders
        pages = pdf_loader.load()
        print(f"Loaded a total of {len(pages)} pages across all PDFs in the directories.")
    except Exception as e:
        print(f"Error loading PDFs: {e}")
        raise


    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    pages_split = text_splitter.split_documents(pages)

    persist_directory = r"./vector"  # Update this path accordingly
    collection_name = "vector_storage"  # Update this accordingly

    # If our collection does not exist in the directory, we create using the os command
    if not os.path.exists(persist_directory):
        os.makedirs(persist_directory)

    try:
        # Here, we actually create the chroma database using our embeddigns model
        vectorstore = Chroma.from_documents(
            documents=pages_split,
            embedding=embeddings,
            persist_directory=persist_directory,
            collection_name=collection_name
        )
        print(f"Created ChromaDB vector store!")

    except Exception as e:
        print(f"Error setting up ChromaDB: {str(e)}")
        raise

