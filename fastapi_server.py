# fastapi_server.py

import json
import logging
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# Import chatbot, thread retrieve and PDF ingestion from the RAG backend
from langraph_rag_backend import (
    chatbot, 
    retrieve_all_threads, 
    ingest_pdf, 
    thread_document_metadata, 
    thread_has_document
)
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fastapi_server")

app = FastAPI(title="LangGraph Chatbot API")

# Enable CORS for local testing if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    thread_id: str

@app.get("/api/threads")
def get_threads():
    """Retrieve all available chat threads."""
    try:
        threads = retrieve_all_threads()
        # Return unique threads, sorted so newer or recently active are easy to manage.
        # Since threads are UUIDs or strings, we serialize them to strings.
        serialized_threads = sorted([str(t) for t in threads], reverse=True)
        return {"threads": serialized_threads}
    except Exception as e:
        logger.error(f"Error retrieving threads: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str):
    """Retrieve all messages for a specific thread."""
    try:
        state = await chatbot.aget_state(config={"configurable": {"thread_id": thread_id}})
        messages = state.values.get("messages", [])
        
        serialized = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                serialized.append({
                    "role": "user",
                    "content": msg.content
                })
            elif isinstance(msg, AIMessage):
                tool_calls = []
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls.append({
                            "name": tc["name"],
                            "args": tc["args"]
                        })
                serialized.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": tool_calls
                })
            elif isinstance(msg, ToolMessage):
                serialized.append({
                    "role": "tool",
                    "name": getattr(msg, "name", "tool"),
                    "content": msg.content
                })
        return {"messages": serialized}
    except Exception as e:
        logger.error(f"Error retrieving messages for thread {thread_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    thread_id: str = Form(...)
):
    """Upload and ingest a document (PDF or PPTX) for RAG querying on a thread."""
    try:
        logger.info(f"Ingesting file '{file.filename}' for thread_id '{thread_id}'")
        file_bytes = await file.read()
        metadata = ingest_pdf(file_bytes, thread_id=thread_id, filename=file.filename)
        return {"status": "success", "metadata": metadata}
    except Exception as e:
        logger.error(f"Error in upload_document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/threads/{thread_id}/document")
def get_thread_document(thread_id: str):
    """Check if the thread has an ingested document and return metadata."""
    try:
        has_doc = thread_has_document(thread_id)
        if has_doc:
            meta = thread_document_metadata(thread_id)
            return {"has_document": True, "metadata": meta}
        return {"has_document": False}
    except Exception as e:
        logger.error(f"Error getting thread document status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def sse_chat_generator(user_input: str, thread_id: str):
    """Generate Server-Sent Events from the LangGraph chatbot stream."""
    config = {
        "configurable": {"thread_id": thread_id},
        "metadata": {"thread_id": thread_id},
        "run_name": "chat_turn",
    }
    
    try:
        # Run chatbot stream asynchronously.
        async for message_chunk, metadata in chatbot.astream(
            {"messages": [HumanMessage(content=user_input)]},
            config=config,
            stream_mode="messages",
        ):
            # 1. Tool Execution output
            if isinstance(message_chunk, ToolMessage):
                tool_name = getattr(message_chunk, "name", "tool")
                output_str = message_chunk.content
                yield f"event: tool_end\ndata: {json.dumps({'name': tool_name, 'output': output_str})}\n\n"
            
            # 2. AI Message tokens and Tool Calls
            elif isinstance(message_chunk, AIMessage):
                if message_chunk.tool_calls:
                    for tc in message_chunk.tool_calls:
                        yield f"event: tool_start\ndata: {json.dumps({'name': tc['name'], 'args': tc['args']})}\n\n"
                
                if message_chunk.content:
                    yield f"event: token\ndata: {json.dumps(message_chunk.content)}\n\n"
                    
    except Exception as e:
        logger.error(f"Error in sse_chat_generator: {e}")
        yield f"event: error\ndata: {json.dumps(str(e))}\n\n"
    finally:
        yield "event: done\ndata: {}\n\n"

@app.post("/api/chat")
def chat_endpoint(request: ChatRequest):
    """Stream chat responses and tool execution metadata."""
    return StreamingResponse(
        sse_chat_generator(request.message, request.thread_id),
        media_type="text/event-stream"
    )

# Mount the static directory to serve the frontend web page
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fastapi_server:app", host="127.0.0.1", port=8000, reload=True)
