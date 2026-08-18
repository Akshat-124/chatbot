from __future__ import annotations

import os
import sqlite3
import tempfile
import subprocess
import sys
import urllib.parse
from html.parser import HTMLParser
from typing import Annotated, Any, Dict, Optional, TypedDict
from langchain_core.runnables import RunnableConfig

from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.vectorstores import FAISS
from langchain_core.messages import BaseMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
import requests

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
import asyncio
import threading

load_dotenv()

# Dedicated async loop for backend tasks
_ASYNC_LOOP = asyncio.new_event_loop()
_ASYNC_THREAD = threading.Thread(target=_ASYNC_LOOP.run_forever, daemon=True)
_ASYNC_THREAD.start()


def _submit_async(coro):
    return asyncio.run_coroutine_threadsafe(coro, _ASYNC_LOOP)


def run_async(coro, timeout=5):
    try:
        return _submit_async(coro).result(timeout=timeout)
    except Exception as e:
        print(f"Async execution timed out or failed: {e}")
        return None


def submit_async_task(coro):
    """Schedule a coroutine on the backend event loop."""
    return _submit_async(coro)


# -------------------
# 1. LLM + embeddings
# -------------------
llm = ChatGroq(
    model="llama-3.1-8b-instant"
)
embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# -------------------
# 2. PDF retriever store (per thread)
# -------------------
_THREAD_RETRIEVERS: Dict[str, Any] = {}
_THREAD_METADATA: Dict[str, dict] = {}


def _get_retriever(thread_id: Optional[str]):
    """Fetch the retriever for a thread if available."""
    if thread_id and thread_id in _THREAD_RETRIEVERS:
        return _THREAD_RETRIEVERS[thread_id]
    return None


from langchain_core.documents import Document
import pptx


def _load_pptx(file_path: str) -> list[Document]:
    """Parse slides, shape text, tables, and notes from a PPTX file into LangChain Documents."""
    prs = pptx.Presentation(file_path)
    docs = []
    for i, slide in enumerate(prs.slides, start=1):
        text_parts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                text = shape.text_frame.text.strip()
                if text:
                    text_parts.append(text)
            elif shape.has_table:
                table = shape.table
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        text_parts.append(row_text)
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                text_parts.append(f"Speaker Notes: {notes}")

        slide_text = "\n".join(text_parts).strip()
        if slide_text:
            docs.append(Document(page_content=slide_text, metadata={"page": i, "source": os.path.basename(file_path)}))
    return docs


def ingest_document(file_bytes: bytes, thread_id: str, filename: Optional[str] = None) -> dict:
    """
    Build a FAISS retriever for the uploaded PDF or PPTX document and store it for the thread.

    Returns a summary dict that can be surfaced in the UI.
    """
    if not file_bytes:
        raise ValueError("No bytes received for ingestion.")

    fname = filename or "document.pdf"
    ext = os.path.splitext(fname)[1].lower()
    if not ext:
        ext = ".pdf"

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
        temp_file.write(file_bytes)
        temp_path = temp_file.name

    try:
        if ext in [".pptx", ".ppt"]:
            docs = _load_pptx(temp_path)
        else:
            loader = PyPDFLoader(temp_path)
            docs = loader.load()

        if not docs:
            raise ValueError("No readable text content found in document.")

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200, separators=["\n\n", "\n", " ", ""]
        )
        chunks = splitter.split_documents(docs)

        vector_store = FAISS.from_documents(chunks, embedding_model)
        retriever = vector_store.as_retriever(
            search_type="similarity", search_kwargs={"k": 4}
        )

        _THREAD_RETRIEVERS[str(thread_id)] = retriever
        _THREAD_METADATA[str(thread_id)] = {
            "filename": fname,
            "documents": len(docs),
            "chunks": len(chunks),
        }

        return {
            "filename": fname,
            "documents": len(docs),
            "chunks": len(chunks),
        }
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


ingest_pdf = ingest_document


# -------------------
# 3. Tools
# -------------------
search_tool = DuckDuckGoSearchRun(region="us-en")

try:
    from exa_py import Exa
    _exa_key = os.getenv("EXA_API_KEY")
    exa_client = Exa(api_key=_exa_key) if _exa_key else None
except Exception:
    exa_client = None


@tool
def exa_search_tool(query: str) -> str:
    """
    Perform a neural web search using Exa AI search engine.
    Use this for searching real-time web information, latest news, recent events, articles, and research.
    """
    if not exa_client:
        return "Exa API key is not configured."
    try:
        res = exa_client.search(query, num_results=5)
        results = []
        for r in res.results:
            title = getattr(r, 'title', 'No Title')
            url = getattr(r, 'url', '')
            text = getattr(r, 'text', '')
            results.append(f"Title: {title}\nURL: {url}\nContent: {text[:1000] if text else 'N/A'}")
        return "\n---\n".join(results) if results else "No relevant search results found."
    except Exception as e:
        return f"Exa search error: {str(e)}"



@tool
def calculator(first_num: float, second_num: float, operation: str) -> dict:
    """
    Perform a basic arithmetic operation on two numbers.
    Supported operations: add, sub, mul, div
    """
    try:
        if operation == "add":
            result = first_num + second_num
        elif operation == "sub":
            result = first_num - second_num
        elif operation == "mul":
            result = first_num * second_num
        elif operation == "div":
            if second_num == 0:
                return {"error": "Division by zero is not allowed"}
            result = first_num / second_num
        else:
            return {"error": f"Unsupported operation '{operation}'"}

        return {
            "first_num": first_num,
            "second_num": second_num,
            "operation": operation,
            "result": result,
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def get_stock_price(symbol: str) -> dict:
    """
    Fetch latest stock price for a given symbol (e.g. 'AAPL', 'TSLA') 
    using Yahoo Finance API (no key required).
    """
    try:
        symbol = symbol.strip().upper()
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=5)
        
        if r.status_code != 200:
            return {
                "error": f"Yahoo Finance API returned status code {r.status_code}.",
                "message": "Yahoo Finance API is rate-limiting or blocking requests from this hosting provider's IP range. Please use the search tool to find the current stock price."
            }
            
        data = r.json()
        chart_data = data.get("chart", {})
        if chart_data.get("error") is not None:
            err_desc = chart_data["error"].get("description", "Unknown error")
            return {"error": f"Yahoo Finance API error for symbol '{symbol}': {err_desc}"}
            
        results = chart_data.get("result")
        if not results:
            return {"error": f"No data found for symbol '{symbol}'."}
            
        meta = results[0].get("meta", {})
        if "regularMarketPrice" not in meta:
            suggestion = ""
            if symbol == "APPL":
                suggestion = " Did you mean AAPL?"
            return {"error": f"Symbol '{symbol}' has no current market price data.{suggestion}"}
            
        price = meta["regularMarketPrice"]
        currency = meta.get("currency", "USD")
        
        return {
            "symbol": symbol,
            "price": price,
            "currency": currency,
            "message": f"The current price of {symbol} is {price} {currency}."
        }
    except Exception as e:
        return {
            "error": f"Could not retrieve stock price: {str(e)}",
            "message": "Failed to connect to Yahoo Finance. If this persists, please use the web search tool."
        }



@tool
def rag_tool(query: str, config: RunnableConfig) -> dict:
    """
    Retrieve relevant information from the uploaded PDF or PowerPoint document for this chat thread.
    """
    thread_id = config.get("configurable", {}).get("thread_id")
    retriever = _get_retriever(thread_id)
    if retriever is None:
        return {
            "error": "No document indexed for this chat. Upload a PDF or PowerPoint file first.",
            "query": query,
        }

    result = retriever.invoke(query)
    context = [doc.page_content for doc in result]
    metadata = [doc.metadata for doc in result]

    return {
        "query": query,
        "context": context,
        "metadata": metadata,
        "source_file": _THREAD_METADATA.get(str(thread_id), {}).get("filename"),
    }


class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []
        self.ignore = False

    def handle_starttag(self, tag, attrs):
        if tag in ["script", "style", "head", "meta", "link", "noscript"]:
            self.ignore = True

    def handle_endtag(self, tag):
        if tag in ["script", "style", "head", "meta", "link", "noscript"]:
            self.ignore = False

    def handle_data(self, data):
        if not self.ignore:
            cleaned = data.strip()
            if cleaned:
                self.result.append(cleaned)

    def get_text(self):
        return " ".join(self.result)


@tool
def python_code_executor(code: str) -> dict:
    """
    Execute python code dynamically and return the stdout, stderr and exit code.
    Use this tool to solve complex math, run algorithms, analyze data, or run python scripts.
    Ensure code prints the final results or values to stdout.
    """
    try:
        # Run code in a subprocess with a timeout of 5 seconds
        res = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=5
        )
        return {
            "stdout": res.stdout,
            "stderr": res.stderr,
            "exit_code": res.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "error": "Execution timed out after 5 seconds.",
            "stdout": "",
            "stderr": ""
        }
    except Exception as e:
        return {
            "error": str(e),
            "stdout": "",
            "stderr": ""
        }


@tool
def scrape_url_tool(url: str) -> dict:
    """
    Scrape and extract readable text content from a given website URL.
    Use this to read articles, documentations, and blog posts provided by the user.
    """
    try:
        url = url.strip()
        # Add scheme if missing
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme:
            url = "https://" + url
            
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(url, headers=headers, timeout=10)
        
        if r.status_code != 200:
            return {"error": f"Failed to fetch URL. HTTP status code {r.status_code}."}
            
        # Parse text content
        parser = HTMLTextExtractor()
        parser.feed(r.text)
        text = parser.get_text()
        
        # Limit text content to 8000 characters to prevent context window overflow
        truncated = text[:8000]
        if len(text) > 8000:
            truncated += "\n\n[Content truncated due to length...]"
            
        return {
            "url": url,
            "title": r.reason,
            "content": truncated
        }
    except Exception as e:
        return {"error": f"Failed to scrape URL: {str(e)}"}


client = MultiServerMCPClient(
    {
        "expense": {
            "transport": "streamable_http",  # if this fails, try "sse"
            "url": "https://splendid-gold-dingo.fastmcp.app/mcp"
        }
    }
)


def load_mcp_tools() -> list[BaseTool]:
    try:
        tools = run_async(client.get_tools(), timeout=5)
        return tools if tools is not None else []
    except Exception as e:
        print(f"Error loading MCP tools: {e}")
        return []


mcp_tools = load_mcp_tools()

tools = [exa_search_tool, search_tool, get_stock_price, calculator, rag_tool, python_code_executor, scrape_url_tool, *mcp_tools]
llm_with_tools = llm.bind_tools(tools)

# -------------------
# 4. State
# -------------------
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


# -------------------
# 5. Nodes
# -------------------
async def chat_node(state: ChatState, config=None):
    """LLM node that may answer or request a tool call."""
    thread_id = None
    if config and isinstance(config, dict):
        thread_id = config.get("configurable", {}).get("thread_id")

    system_message = SystemMessage(
        content=(
            "You are a helpful assistant. You have access to real-time web search (`exa_search_tool`), stock price, "
            "calculator, expense tracking, Python code execution (`python_code_executor`), and URL scraping (`scrape_url_tool`) tools. "
            "IMPORTANT FOR SEARCH: For any questions asking for real-time web information, recent news, current events, "
            "facts, or internet research, you MUST call the `exa_search_tool` tool to retrieve up-to-date information. "
            "IMPORTANT FOR CODE EXECUTION: If the user asks you to write code, solve algorithms, calculate math that requires loops, "
            "or do code logic testing, you MUST write the python script and execute it using `python_code_executor`. Ensure your script prints results to stdout. "
            "IMPORTANT FOR WEBSITES: If the user provides a website URL, you MUST call `scrape_url_tool` to read and summarize it. "
            "If the user asks a question about an uploaded document, PDF, or PowerPoint presentation, "
            "you MUST call the `rag_tool` tool with their question. Do not attempt to answer questions about the document without calling `rag_tool`. "
            "If the user asks questions about a document, PDF, or presentation, but no document has been uploaded yet, politely "
            "instruct them to upload a PDF or PPTX file in the sidebar first. For general queries that require real-time search, "
            "always prefer calling `exa_search_tool`."
        )
    )

    # Optimize conversation history to fit within Groq's TPM (Tokens Per Minute) limit
    raw_messages = state["messages"]
    optimized_messages = []
    
    # Keep only the last 10 messages for conversational context
    history_limit = 10
    recent_messages = raw_messages[-history_limit:] if len(raw_messages) > history_limit else list(raw_messages)
    
    from copy import copy
    for i, msg in enumerate(recent_messages):
        msg_copy = copy(msg)
        
        # Truncate large tool outputs and AI texts in older turns (older than the last 3 messages)
        # to save thousands of tokens while preserving conversational flow
        is_older = i < (len(recent_messages) - 3)
        if is_older:
            if isinstance(msg_copy, ToolMessage) and len(msg_copy.content) > 400:
                msg_copy.content = msg_copy.content[:150] + "... [Truncated old tool output to save tokens]"
            elif isinstance(msg_copy, AIMessage) and len(msg_copy.content) > 400:
                msg_copy.content = msg_copy.content[:150] + "... [Truncated old response]"
                
        optimized_messages.append(msg_copy)

    messages = [system_message] + optimized_messages
    response = await llm_with_tools.ainvoke(messages, config=config)
    return {"messages": [response]}


tool_node = ToolNode(tools)

# -------------------
# 6. Checkpointer
# -------------------
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


async def _init_checkpointer():
    conn = await aiosqlite.connect(database="chatbot.db")
    return AsyncSqliteSaver(conn)


checkpointer = run_async(_init_checkpointer())

# -------------------
# 7. Graph
# -------------------
graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_node("tools", tool_node)

graph.add_edge(START, "chat_node")
graph.add_conditional_edges("chat_node", tools_condition)
graph.add_edge("tools", "chat_node")

chatbot = graph.compile(checkpointer=checkpointer)

# -------------------
# 8. Helpers
# -------------------
async def _alist_threads():
    all_threads = set()
    async for checkpoint in checkpointer.alist(None):
        all_threads.add(checkpoint.config["configurable"]["thread_id"])
    return list(all_threads)


def retrieve_all_threads():
    return run_async(_alist_threads())


def thread_has_document(thread_id: str) -> bool:
    return str(thread_id) in _THREAD_RETRIEVERS


def thread_document_metadata(thread_id: str) -> dict:
    return _THREAD_METADATA.get(str(thread_id), {})