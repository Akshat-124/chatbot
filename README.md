# LangGraph Agentic AI Chatbot & RAG Platform

A full-stack, autonomous, agentic AI platform built with **LangGraph**, **FastAPI**, **LangChain**, and **Vanilla JS/CSS**. 

It features a custom dark-mode web interface with live terminal widgets, document upload previews, conversational memory checkpointing, and a rich suite of autonomous tools (Python Code Execution Sandbox, Direct URL Web Scraper, Document RAG for PDF/PPTX, Real-time Web Search, Financial Quotes, and Model Context Protocol MCP integration).

---

## 🌟 Key Features

### 1. 🤖 Multi-Agent Orchestration & Stateful Memory
- **LangGraph Workflows**: Orchestrates state transitions, loop controls, and conditional tool routing.
- **SQLite Checkpointing (`SqliteSaver`)**: Thread-level persistent memory allowing seamless session switching, history recovery, and state preservation.

### 2. ⚡ FastAPI Backend & Real-Time SSE Streaming
- **FastAPI Async Engine**: High-performance asynchronous backend (`fastapi_server.py`) with streaming Server-Sent Events (SSE).
- **Live Tool Progress**: Streams tool execution states (`tool_start`, `tool_end`) and token-by-token LLM responses directly to the client interface.

### 3. 🎨 Premium Custom Dark-Mode UI
- **Vanilla JS & CSS Frontend**: Zero heavy framework overhead (`static/index.html`, `static/style.css`, `static/app.js`).
- **Interactive UI Widgets**:
  - 🐍 **Terminal Console**: Monospaced terminal card rendering Python execution `stdout` (green) and `stderr` (red).
  - 🌐 **Web Scrape Cards**: Styled website preview cards displaying scraped domain headers and article excerpts.
  - 📈 **Stock Market Widgets**: Live financial price quote capsules.
  - 📁 **Active Document Indicator**: Real-time badge tracking uploaded file name and indexed vector chunks.

### 4. 🛠️ Autonomous Tool Suite
- 📄 **Multi-Format Document RAG (`rag_tool`)**: Upload **PDF** or **PowerPoint (PPTX)** files. Uses **FAISS Vector Database** and **HuggingFace Embeddings (`all-MiniLM-L6-v2`)** for document Q&A and ATS resume scoring. Automatically resolves thread metadata via LangChain `RunnableConfig`.
- 🐍 **Live Python Code Sandbox (`python_code_executor`)**: Executes Python code in a safe local subprocess (`sys.executable`), enforcing execution timeouts and capturing terminal output logs.
- 🌐 **Direct Web Page Scraper (`scrape_url_tool`)**: Built-in HTML text parsing engine that strips navigation markup and extracts clean article text.
- 🔎 **Real-Time Web Search (`exa_search_tool` & `duckduckgo_search`)**: Access up-to-date news, current events, and web research.
- 📈 **Financial Quotes & Math Calculator**: Real-time stock lookups (`get_stock_price`) and arithmetic operations (`calculator`).
- 🔌 **Model Context Protocol (MCP)**: Native connection to remote **FastMCP** HTTP/SSE servers for external tools (e.g., expense tracking).

### 5. 🧹 Token Optimization & Observability
- **Dynamic Context Trimmer**: Automated message history compressor inside `chat_node` that restricts prompt history to the 10 most recent messages and truncates old raw tool outputs. Reduces payload sizes by **90%+** (from 12k+ to <1k tokens) to prevent Groq `413 Request Too Large` (TPM) limit errors.
- **LangSmith Tracing**: Integrated with **LangSmith** for full-stack LLM observability, latency tracking, and prompt debugging.

---

## 📂 Project Structure

```
chatbot_in_langgraph/
├── fastapi_server.py           # FastAPI server with SSE streaming endpoints & upload handlers
├── langraph_rag_backend.py     # LangGraph compilation, tool definitions, & RAG workflow
├── static/                     # Premium custom frontend interface
│   ├── index.html              # Modern glassmorphic chat layout & sidebar
│   ├── style.css              # Dark-mode UI tokens, terminal cards, & scraper styles
│   └── app.js                 # SSE streaming client & custom tool card renderers
├── chatbot.db                  # Local SQLite database storing conversation checkpoints
├── requirements.txt            # Python dependencies
├── .env                        # API keys & configuration
└── Dockerfile                  # Container deployment configuration
```

---

## 🔧 Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/Akshat-124/chatbot.git
cd chatbot
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory:
```env
GROQ_API_KEY="your_groq_api_key"
EXA_API_KEY="your_exa_api_key"
LANGCHAIN_TRACING_V2="true"
LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
LANGCHAIN_API_KEY="your_langchain_api_key"
LANGCHAIN_PROJECT="Chatbot Project"
```

### 3. Install Dependencies
```bash
# Create and activate virtual environment
python -m venv myenv
myenv\Scripts\activate  # On Windows
# source myenv/bin/activate  # On macOS/Linux

# Install requirements
pip install -r requirements.txt
```

### 4. Run the Platform
Start the FastAPI server:
```bash
python -m uvicorn fastapi_server:app --port 8000
```
Open your browser and navigate to: **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**

---

## 🐳 Docker Execution

Build and run using Docker:
```bash
# Build Docker image
docker build -t langgraph-agentic-chatbot .

# Run container with environment file
docker run -p 8000:8000 --env-file .env langgraph-agentic-chatbot
```
Access the application at `http://localhost:8000`.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for details.
