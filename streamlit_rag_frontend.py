import queue
import uuid

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from langraph_rag_backend import (
    chatbot,
    ingest_pdf,
    retrieve_all_threads,
    thread_document_metadata,
    submit_async_task,
)


# =========================== Utilities ===========================
def generate_thread_id():
    return uuid.uuid4()


def reset_chat():
    thread_id = generate_thread_id()
    st.session_state["thread_id"] = thread_id
    add_thread(thread_id)
    st.session_state["message_history"] = []


def add_thread(thread_id):
    if thread_id not in st.session_state["chat_threads"]:
        st.session_state["chat_threads"].append(thread_id)


def load_conversation(thread_id):
    state = chatbot.get_state(config={"configurable": {"thread_id": thread_id}})
    return state.values.get("messages", [])


def get_thread_title(thread_id):
    if "chat_titles" not in st.session_state:
        st.session_state["chat_titles"] = {}
    if thread_id in st.session_state["chat_titles"] and st.session_state["chat_titles"][thread_id] != "New Chat":
        return st.session_state["chat_titles"][thread_id]

    messages = load_conversation(thread_id)
    title = "New Chat"
    for msg in messages:
        if isinstance(msg, HumanMessage) and msg.content:
            content = msg.content.strip()
            title = content[:28] + "…" if len(content) > 28 else content
            break
    st.session_state["chat_titles"][thread_id] = title
    return title


# ======================= Session Initialization ===================
if "message_history" not in st.session_state:
    st.session_state["message_history"] = []

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = generate_thread_id()

if "chat_threads" not in st.session_state:
    st.session_state["chat_threads"] = retrieve_all_threads()

if "chat_titles" not in st.session_state:
    st.session_state["chat_titles"] = {}

if "ingested_docs" not in st.session_state:
    st.session_state["ingested_docs"] = {}

add_thread(st.session_state["thread_id"])

thread_key = str(st.session_state["thread_id"])
thread_docs = st.session_state["ingested_docs"].setdefault(thread_key, {})
threads = st.session_state["chat_threads"][::-1]
selected_thread = None

# ============================ Sidebar ============================
st.sidebar.title("LangGraph Chatbot")

if st.sidebar.button("➕ New Chat", use_container_width=True):
    reset_chat()
    st.rerun()

if thread_docs:
    latest_doc = list(thread_docs.values())[-1]
    st.sidebar.success(
        f"Using `{latest_doc.get('filename')}` "
        f"({latest_doc.get('chunks')} chunks from {latest_doc.get('documents')} pages/slides)"
    )
else:
    st.sidebar.info("No document indexed for current chat.")

uploaded_doc = st.sidebar.file_uploader("Upload a PDF or PPTX for this chat", type=["pdf", "pptx", "ppt"])
if uploaded_doc:
    if uploaded_doc.name in thread_docs:
        st.sidebar.info(f"`{uploaded_doc.name}` already processed for this chat.")
    else:
        with st.sidebar.status("Indexing Document…", expanded=True) as status_box:
            summary = ingest_pdf(
                uploaded_doc.getvalue(),
                thread_id=thread_key,
                filename=uploaded_doc.name,
            )
            thread_docs[uploaded_doc.name] = summary
            status_box.update(label="✅ Document indexed", state="complete", expanded=False)

st.sidebar.divider()
st.sidebar.subheader("Recent Conversations")
if not threads:
    st.sidebar.write("No past conversations yet.")
else:
    for thread_id in threads:
        title = get_thread_title(thread_id)
        is_current = (thread_id == st.session_state["thread_id"])
        btn_label = f"💬 {title}" if not is_current else f"🔹 {title}"
        if st.sidebar.button(
            btn_label,
            key=f"side-thread-{thread_id}",
            use_container_width=True,
            type="primary" if is_current else "secondary",
        ):
            selected_thread = thread_id

# ============================ Main Layout ========================
st.title("Multi Utility Chatbot")

# Chat area
for message in st.session_state["message_history"]:
    with st.chat_message(message["role"]):
        st.text(message["content"])

user_input = st.chat_input("Ask about your document or use tools")

if user_input:
    # Update title dynamically if it's currently "New Chat"
    curr_tid = st.session_state["thread_id"]
    if get_thread_title(curr_tid) == "New Chat":
        clean_input = user_input.strip()
        new_title = clean_input[:28] + "…" if len(clean_input) > 28 else clean_input
        st.session_state["chat_titles"][curr_tid] = new_title
    st.session_state["message_history"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.text(user_input)

    CONFIG = {
        "configurable": {"thread_id": thread_key},
        "metadata": {"thread_id": thread_key},
        "run_name": "chat_turn",
    }

    with st.chat_message("assistant"):
        status_holder = {"box": None}

        def ai_only_stream():
            event_queue: queue.Queue = queue.Queue()

            async def run_stream():
                try:
                    async for message_chunk, metadata in chatbot.astream(
                        {"messages": [HumanMessage(content=user_input)]},
                        config=CONFIG,
                        stream_mode="messages",
                    ):
                        event_queue.put((message_chunk, metadata))
                except Exception as exc:
                    event_queue.put(("error", exc))
                finally:
                    event_queue.put(None)

            submit_async_task(run_stream())

            while True:
                item = event_queue.get()
                if item is None:
                    break
                message_chunk, metadata = item
                if message_chunk == "error":
                    raise metadata

                if isinstance(message_chunk, ToolMessage):
                    tool_name = getattr(message_chunk, "name", "tool")
                    if status_holder["box"] is None:
                        status_holder["box"] = st.status(
                            f"🔧 Using `{tool_name}` …", expanded=True
                        )
                    else:
                        status_holder["box"].update(
                            label=f"🔧 Using `{tool_name}` …",
                            state="running",
                            expanded=True,
                        )

                if isinstance(message_chunk, AIMessage):
                    yield message_chunk.content

        ai_message = st.write_stream(ai_only_stream())

        if status_holder["box"] is not None:
            status_holder["box"].update(
                label="✅ Tool finished", state="complete", expanded=False
            )

    st.session_state["message_history"].append(
        {"role": "assistant", "content": ai_message}
    )

    doc_meta = thread_document_metadata(thread_key)
    if doc_meta:
        st.caption(
            f"Document indexed: {doc_meta.get('filename')} "
            f"(chunks: {doc_meta.get('chunks')}, pages: {doc_meta.get('documents')})"
        )

st.divider()

if selected_thread:
    st.session_state["thread_id"] = selected_thread
    messages = load_conversation(selected_thread)

    temp_messages = []
    for msg in messages:
        role = "user" if isinstance(msg, HumanMessage) else "assistant"
        temp_messages.append({"role": role, "content": msg.content})
    st.session_state["message_history"] = temp_messages
    st.session_state["ingested_docs"].setdefault(str(selected_thread), {})
    st.rerun()