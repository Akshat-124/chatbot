# LangGraph Streamlit Chatbot

A modern, conversational LLM chatbot application built with [LangGraph](https://github.com/langchain-ai/langgraph) and [Streamlit](https://streamlit.io/). It supports conversational memory, message streaming, multiple concurrent chat threads, and persistent storage via SQLite database checkpointing.

---

## 🚀 Features

- **Conversational Memory**: Powered by LangGraph's state management and checkpointer systems.
- **Multiple Chat Threads**: Switch between conversations easily from the sidebar.
- **Dynamic Titles**: Conversation thread titles are automatically generated from the first user sentence.
- **Message Streaming**: Stream response tokens block-by-block directly from the ChatGroq model.
- **Database Persistence**: Persists conversations locally using a SQLite database (`chatbot.db`) so chat history is saved between sessions.

---

## 🛠️ Project Structure

- `langgraph_database_backend.py`: Backend containing the LangGraph compilations and state checkpointers utilizing SQLite for persistent memory.
- `streamlit_frontend_database.py`: Database-backed user interface featuring persistent chat threads, customized sidebar titles, and optimized message streaming.
- `streamlit_frontend_threading.py`: Threading-enabled UI that uses in-memory checks for fast testing of multi-chat capabilities.
- `streamlit_frontend_streaming.py`: Single-session UI showcasing real-time token streaming.
- `streamlit_frontend.py`: Basic layout showcasing the invocation pattern of the chatbot model.
- `requirements.txt`: Package dependencies.
- `.env`: Environment configurations for the model API key.

---

## 🔧 Installation & Setup

1. **Clone the Repository**
   ```bash
   git clone https://github.com/Akshat-124/chatbot.git
   cd chatbot
   ```

2. **Configure Environment Variables**
   Create a `.env` file in the root directory and add your Groq API key:
   ```env
   GROQ_API_KEY="your_groq_api_key_here"
   ```

3. **Install Dependencies**
   It is recommended to use a virtual environment:
   ```bash
   python -m venv myenv
   myenv\Scripts\activate  # On Windows
   # source myenv/bin/activate  # On macOS/Linux

   pip install -r requirements.txt
   ```

4. **Run the Chatbot**
   To run the database-backed persistent threads version:
   ```bash
   streamlit run streamlit_frontend_database.py
   ```

---

## 🗺️ Upcoming Features (Roadmap)

To elevate this into a fully-featured, production-ready AI companion, the following features are on the roadmap:

- **🔍 RAG (Retrieval-Augmented Generation)**: Integrate vector stores (e.g., ChromaDB, FAISS) to load documents (PDFs, text files) and query against local knowledge repositories.
- **👁️ Image Recognition (Multimodal capabilities)**: Add support for vision-based LLMs to allow image uploads and real-time visual analysis.
- **🎙️ Speech & Voice Interaction**: Integrations for Text-to-Speech (TTS) and Speech-to-Text (STT) enabling users to converse via voice commands and hear responses spoken back.
- **🛠️ Advanced Tool Use (Agents)**: Equipping the chatbot with tools to perform web search, run Python scripts, and fetch external API data.
