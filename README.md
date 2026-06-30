# LangGraph Streamlit RAG Chatbot & Agent

A modern, containerized, conversational AI agent built with **LangGraph**, **LangChain**, and **Streamlit**. It supports conversational memory, message streaming, multiple concurrent chat threads, persistent SQLite storage, and a dynamic Retrieval-Augmented Generation (RAG) pipeline for PDF document querying.

---

## 🚀 Features

- **📂 Dynamic PDF RAG**: Upload any PDF directly in the sidebar. The application will chunk the document, generate embeddings (`all-MiniLM-L6-v2`), store them in a local **FAISS** vector database, and call a retrieval tool dynamically to answer context-specific questions.
- **🔧 Agentic Tool Orchestration**: Powered by LangGraph's state machine, the LLM can call external tools on the fly:
  - `rag_tool`: Query context from the uploaded PDF document.
  - `DuckDuckGo Search`: Access live web information.
  - `calculator`: Perform basic math operations (`add`, `sub`, `mul`, `div`).
  - `get_stock_price`: Look up real-time stock quotes.
- **💾 Conversational Memory & Persistence**: Uses a SQLite checkpointer database (`chatbot.db`) to preserve state, allowing users to switch between past conversations without losing context.
- **💬 Streamlit UI with Token Streaming**: High-fidelity user interface featuring real-time assistant responses, sidebar thread navigation, and automatic conversation title generation based on the first user message.
- **🐳 Docker Ready**: Configured for simple containerized execution and deployment.

---

## 📂 Project Structure

- **`streamlit_rag_frontend.py`**: The Streamlit interface featuring thread switching, PDF upload/indexing status, and assistant token streaming.
- **`langraph_rag_backend.py`**: LangGraph compilation defining state schemas, tool integrations, and SQLite persistence.
- **`Dockerfile`**: Docker configuration optimized for local container runs or cloud platforms (e.g., Hugging Face Spaces).
- **`requirements.txt`**: Complete Python package requirements frozen to match the working environment.
- **`chatbot.db`**: Local SQLite database storing conversation checkpoints.

---

## 🔧 Local Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/Akshat-124/chatbot.git
cd chatbot
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory:
```env
GROQ_API_KEY="your_groq_api_key"
LANGCHAIN_TRACING_V2="true"
LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
LANGCHAIN_API_KEY="your_langchain_api_key"
LANGCHAIN_PROJECT="Chatbot Project"
```

### 3. Setup Virtual Environment & Install Packages
```bash
python -m venv myenv
myenv\Scripts\activate  # On Windows
# source myenv/bin/activate  # On macOS/Linux

pip install -r requirements.txt
```

### 4. Run the RAG Chatbot Locally
```bash
streamlit run streamlit_rag_frontend.py
```

---

## 🐳 Docker Execution

To build and run the application locally inside a Docker container:
```bash
# Build the image
docker build -t langgraph-rag-chatbot .

# Run the container (make sure to pass your .env file variables or use --env-file)
docker run -p 7860:7860 --env-file .env langgraph-rag-chatbot
```
Access the application at `http://localhost:7860`.

---

## ☁️ Deployment (Hugging Face Spaces)

This repository is ready to be deployed on **Hugging Face Spaces** using the **Docker SDK**:

1. Create a **New Space** on Hugging Face.
2. Select **Docker** as the SDK and choose the **Blank** template.
3. In the Space **Settings**, add your API keys under **Secrets** (e.g., `GROQ_API_KEY`, `LANGCHAIN_API_KEY`).
4. Upload `Dockerfile`, `streamlit_rag_frontend.py`, `langraph_rag_backend.py`, and `requirements.txt` directly to the Space Files repository.
5. Hugging Face will build the Docker container automatically and host your live demo.
