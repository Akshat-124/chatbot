// static/app.js

document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const sidebar = document.getElementById('sidebar');
    const toggleSidebarBtn = document.getElementById('toggle-sidebar');
    const newChatBtn = document.getElementById('new-chat-btn');
    const threadsList = document.getElementById('threads-list');
    const activeThreadTitle = document.getElementById('active-thread-title');
    const messagesArea = document.getElementById('messages-area');
    const welcomeScreen = document.getElementById('welcome-screen');
    const chatForm = document.getElementById('chat-form');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const toastContainer = document.getElementById('toast-container');
    const attachBtn = document.getElementById('attach-btn');
    const fileInput = document.getElementById('file-input');
    const activeDocBadge = document.getElementById('active-doc-badge');
    const activeDocName = document.getElementById('active-doc-name');
    const activeDocDetails = document.getElementById('active-doc-details');

    // App State
    let currentThreadId = null;
    let isGenerating = false;

    // Helper: Generate UUID (v4)
    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    // Helper: Show notification toast
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerText = message;
        toastContainer.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // Toggle Sidebar collapse
    toggleSidebarBtn.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
    });

    // Auto-grow textarea height
    userInput.addEventListener('input', () => {
        userInput.style.height = 'auto';
        userInput.style.height = (userInput.scrollHeight) + 'px';
        sendBtn.disabled = !userInput.value.trim() || isGenerating;
    });

    // Handle suggestion query click
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('query-suggestion')) {
            const query = e.target.getAttribute('data-query');
            userInput.value = query;
            userInput.style.height = 'auto';
            userInput.style.height = (userInput.scrollHeight) + 'px';
            sendBtn.disabled = false;
            userInput.focus();
        }
    });

    // Load all threads from backend
    async function loadThreads() {
        try {
            const response = await fetch('/api/threads');
            if (!response.ok) throw new Error('Failed to fetch threads');
            const data = await response.json();
            
            threadsList.innerHTML = '';
            
            if (data.threads.length === 0) {
                threadsList.innerHTML = '<div class="thread-placeholder">No conversations yet.</div>';
                return;
            }

            data.threads.forEach(threadId => {
                const threadItem = document.createElement('div');
                threadItem.className = `thread-item ${threadId === currentThreadId ? 'active' : ''}`;
                threadItem.dataset.id = threadId;

                // Create thread list entry layout
                threadItem.innerHTML = `
                    <div class="thread-info">
                        <span class="thread-icon">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                            </svg>
                        </span>
                        <span class="thread-name">${threadId.slice(0, 8)}...</span>
                    </div>
                `;

                threadItem.addEventListener('click', () => {
                    if (isGenerating) {
                        showToast('Please wait for the current message to finish.', 'error');
                        return;
                    }
                    switchThread(threadId);
                });

                threadsList.appendChild(threadItem);
            });
        } catch (error) {
            console.error('Error loading threads:', error);
            showToast('Error loading threads list', 'error');
        }
    }

    // Check and update thread document metadata
    async function updateThreadDocumentStatus(threadId) {
        try {
            const response = await fetch(`/api/threads/${threadId}/document`);
            if (response.ok) {
                const data = await response.json();
                if (data.has_document && data.metadata && data.metadata.filename) {
                    activeDocName.innerText = data.metadata.filename;
                    activeDocDetails.innerText = `(${data.metadata.chunks} chunks)`;
                    activeDocBadge.style.display = 'flex';
                } else {
                    activeDocBadge.style.display = 'none';
                }
            } else {
                activeDocBadge.style.display = 'none';
            }
        } catch (error) {
            console.error('Error fetching document status:', error);
            activeDocBadge.style.display = 'none';
        }
    }

    // Switch to another thread
    async function switchThread(threadId) {
        currentThreadId = threadId;
        activeThreadTitle.innerText = `Chat: ${threadId.slice(0, 8)}...`;
        
        // Highlight active thread in list
        document.querySelectorAll('.thread-item').forEach(item => {
            item.classList.toggle('active', item.dataset.id === threadId);
        });

        // Hide welcome screen
        welcomeScreen.style.display = 'none';
        
        // Update document attachment indicator
        updateThreadDocumentStatus(threadId);
        
        // Show loader or clear messages
        messagesArea.innerHTML = '<div class="thread-placeholder">Loading history...</div>';

        try {
            const response = await fetch(`/api/threads/${threadId}/messages`);
            if (!response.ok) throw new Error('Failed to load thread messages');
            const data = await response.json();
            
            messagesArea.innerHTML = '';
            
            if (data.messages.length === 0) {
                // If thread is empty, show welcome screen
                welcomeScreen.style.display = 'flex';
                return;
            }

            let lastAssistantBubble = null;

            data.messages.forEach(msg => {
                if (msg.role === 'user') {
                    appendUserMessage(msg.content);
                    lastAssistantBubble = null;
                } else if (msg.role === 'assistant') {
                    lastAssistantBubble = appendAssistantMessage(msg.content);
                    
                    // Render any associated tool calls within the bubble if we got history
                    if (msg.tool_calls && msg.tool_calls.length > 0) {
                        msg.tool_calls.forEach(tc => {
                            const tcLog = createToolLog(tc.name, tc.args);
                            lastAssistantBubble.insertBefore(tcLog, lastAssistantBubble.firstChild);
                        });
                    }
                } else if (msg.role === 'tool') {
                    // Find corresponding tool execution card and update with results
                    // Or if no card, just render a standalone output log
                    if (lastAssistantBubble) {
                        const tcLog = updateOrAddToolLog(lastAssistantBubble, msg.name, msg.content);
                    }
                }
            });
            
            scrollToBottom();
        } catch (error) {
            console.error('Error switching thread:', error);
            showToast('Failed to load message history', 'error');
            messagesArea.innerHTML = '<div class="thread-placeholder">Failed to load messages.</div>';
        }
    }

    // Start a new chat session
    function startNewChat() {
        if (isGenerating) {
            showToast('Please wait for the current message to finish.', 'error');
            return;
        }
        currentThreadId = generateUUID();
        activeThreadTitle.innerText = 'New Conversation';
        
        // Hide document status badge
        activeDocBadge.style.display = 'none';
        
        // Remove active class from list
        document.querySelectorAll('.thread-item').forEach(item => {
            item.classList.remove('active');
        });

        messagesArea.innerHTML = '';
        welcomeScreen.style.display = 'flex';
        userInput.value = '';
        userInput.style.height = 'auto';
        sendBtn.disabled = true;
        userInput.focus();
    }

    newChatBtn.addEventListener('click', startNewChat);

    // Simple markdown formatting function
    function formatMarkdown(text) {
        if (window.marked && typeof window.marked.parse === 'function') {
            return window.marked.parse(text);
        }
        
        // Fallback simple parsing
        let formatted = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            // Code blocks
            .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
            // Inline code
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            // Bold
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            // Lists
            .replace(/^\s*-\s+(.+)/gm, '<li>$1</li>')
            .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
            // Linebreaks
            .replace(/\n/g, '<br>');
            
        return formatted;
    }

    // Append user message
    function appendUserMessage(content) {
        const wrapper = document.createElement('div');
        wrapper.className = 'message-wrapper user';
        
        wrapper.innerHTML = `
            <div class="message-bubble">${escapeHtml(content)}</div>
            <div class="avatar">U</div>
        `;
        
        messagesArea.appendChild(wrapper);
        scrollToBottom();
    }

    // Append empty assistant message for streaming
    function appendAssistantMessage(content = '') {
        const wrapper = document.createElement('div');
        wrapper.className = 'message-wrapper assistant';
        
        wrapper.innerHTML = `
            <div class="avatar">AI</div>
            <div class="message-bubble markdown-body">${content ? formatMarkdown(content) : '<div class="typing-bubble"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>'}</div>
        `;
        
        messagesArea.appendChild(wrapper);
        scrollToBottom();
        return wrapper.querySelector('.message-bubble');
    }

    // Tool Invocation components
    function createToolLog(name, args) {
        const container = document.createElement('div');
        container.className = 'tool-logs-container';
        container.dataset.toolName = name;
        
        container.innerHTML = `
            <div class="tool-log-header">
                <span class="tool-name-tag">
                    <span class="tool-status-dot running"></span>
                    <span>🔧 Using tool: <code>${name}</code></span>
                </span>
                <span class="tool-arrow">▶</span>
            </div>
            <div class="tool-log-body">
                <strong>Arguments:</strong>
                <pre>${JSON.stringify(args, null, 2)}</pre>
            </div>
        `;

        // Toggle toggle body collapse
        container.querySelector('.tool-log-header').addEventListener('click', () => {
            container.classList.toggle('expanded');
        });

        return container;
    }

    function updateOrAddToolLog(bubble, name, output) {
        // Search for existing logs that are not completed
        let logContainer = bubble.querySelector(`.tool-logs-container[data-tool-name="${name}"]:not(.completed)`);
        
        if (!logContainer) {
            // If none, create it
            logContainer = createToolLog(name, {});
            bubble.insertBefore(logContainer, bubble.firstChild);
        }

        logContainer.classList.add('completed');
        const dot = logContainer.querySelector('.tool-status-dot');
        dot.className = 'tool-status-dot completed';
        
        const headerText = logContainer.querySelector('.tool-name-tag span:nth-child(2)');
        headerText.innerHTML = `✅ Tool finished: <code>${name}</code>`;

        const body = logContainer.querySelector('.tool-log-body');
        
        let parsedOutput = output;
        try {
            parsedOutput = JSON.parse(output);
        } catch (e) {
            // Not JSON, continue with string
        }

        // Add formatted output details
        const outputPre = document.createElement('pre');
        outputPre.innerHTML = `<strong>Output:</strong>\n${escapeHtml(typeof parsedOutput === 'object' ? JSON.stringify(parsedOutput, null, 2) : parsedOutput)}`;
        body.appendChild(outputPre);

        // Add custom graphical UI card based on tool types
        renderCustomToolCard(bubble, name, parsedOutput);
        
        return logContainer;
    }

    function renderCustomToolCard(bubble, name, data) {
        // Stock Price Widget
        if (name === 'get_stock_price' && data && !data.error) {
            const card = document.createElement('div');
            card.className = 'stock-price-card';
            card.innerHTML = `
                <div class="stock-left">
                    <span class="stock-symbol">${data.symbol}</span>
                    <span class="stock-currency">Market Quote (${data.currency})</span>
                </div>
                <div class="stock-right">
                    <span class="stock-price">${data.price}</span>
                    <span class="stock-msg">${data.message || ''}</span>
                </div>
            `;
            bubble.appendChild(card);
        }
        // Calculator formula widget
        else if (name === 'calculator' && data && !data.error) {
            const card = document.createElement('div');
            card.className = 'calculator-card';
            
            let opSymbol = '';
            if (data.operation === 'add') opSymbol = '+';
            else if (data.operation === 'sub') opSymbol = '-';
            else if (data.operation === 'mul') opSymbol = '×';
            else if (data.operation === 'div') opSymbol = '÷';

            card.innerHTML = `
                <div class="calc-expression">${data.first_num} ${opSymbol} ${data.second_num}</div>
                <div class="calc-result">Result: ${data.result}</div>
            `;
            bubble.appendChild(card);
        }
        // Python Sandbox Terminal Widget
        else if (name === 'python_code_executor' && data) {
            const card = document.createElement('div');
            card.className = 'terminal-card';
            
            let termLines = '';
            if (data.error) {
                termLines = `<div class="terminal-line stderr">${escapeHtml(data.error)}</div>`;
            } else {
                if (data.stdout) {
                    termLines += `<div class="terminal-line stdout">${escapeHtml(data.stdout)}</div>`;
                }
                if (data.stderr) {
                    termLines += `<div class="terminal-line stderr">${escapeHtml(data.stderr)}</div>`;
                }
                if (!data.stdout && !data.stderr) {
                    termLines = `<div class="terminal-line empty">Process exited with code ${data.exit_code} (no output)</div>`;
                }
            }

            card.innerHTML = `
                <div class="terminal-header">
                    <div class="terminal-dots">
                        <span class="terminal-dot red"></span>
                        <span class="terminal-dot yellow"></span>
                        <span class="terminal-dot green"></span>
                    </div>
                    <span class="terminal-title">python-code-executor - terminal</span>
                </div>
                <div class="terminal-body">${termLines}</div>
            `;
            bubble.appendChild(card);
        }
        // URL Web Scraper Preview Widget
        else if (name === 'scrape_url_tool' && data) {
            const card = document.createElement('div');
            card.className = 'scrape-card';
            
            if (data.error) {
                card.innerHTML = `
                    <div class="scrape-icon">⚠️</div>
                    <div class="scrape-details">
                        <span class="scrape-title">Scraper Error</span>
                        <span class="scrape-preview">${escapeHtml(data.error)}</span>
                    </div>
                `;
            } else {
                const domain = new URL(data.url).hostname;
                card.innerHTML = `
                    <div class="scrape-icon">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="2" y1="12" x2="22" y2="12"></line>
                            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                        </svg>
                    </div>
                    <div class="scrape-details">
                        <span class="scrape-title">${escapeHtml(data.title || 'Page Scraped')}</span>
                        <a class="scrape-url" href="${escapeHtml(data.url)}" target="_blank">${escapeHtml(domain)}</a>
                        <p class="scrape-preview">${escapeHtml(data.content || '')}</p>
                    </div>
                `;
            }
            bubble.appendChild(card);
        }
    }

    // Scroll chat area to bottom
    function scrollToBottom() {
        messagesArea.scrollTop = messagesArea.scrollHeight;
    }

    // HTML sanitizer
    function escapeHtml(text) {
        return text
            .toString()
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Handle Form Submit (Message Transmission)
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const text = userInput.value.trim();
        if (!text || isGenerating) return;

        // If no active thread, start one
        if (!currentThreadId) {
            currentThreadId = generateUUID();
            activeThreadTitle.innerText = `Chat: ${currentThreadId.slice(0, 8)}...`;
        }

        // Lock form inputs
        isGenerating = true;
        userInput.value = '';
        userInput.style.height = 'auto';
        sendBtn.disabled = true;
        welcomeScreen.style.display = 'none';

        // Add user bubble
        appendUserMessage(text);

        // Add assistant bubble with typing bubble
        const assistantBubble = appendAssistantMessage();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, thread_id: currentThreadId })
            });

            if (!response.ok) throw new Error('API server returned error');

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            let responseText = '';
            let buffer = '';
            let isFirstToken = true;

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep partial line in buffer

                for (const line of lines) {
                    if (line.startsWith('event:')) {
                        currentEvent = line.substring(6).trim();
                    } else if (line.startsWith('data:')) {
                        const dataStr = line.substring(5).trim();
                        if (!dataStr) continue;
                        
                        try {
                            const data = JSON.parse(dataStr);
                            
                            if (currentEvent === 'token') {
                                if (isFirstToken) {
                                    // Remove typing spinner
                                    assistantBubble.innerHTML = '';
                                    isFirstToken = false;
                                }
                                responseText += data;
                                assistantBubble.innerHTML = formatMarkdown(responseText);
                                scrollToBottom();
                            } 
                            else if (currentEvent === 'tool_start') {
                                if (isFirstToken) {
                                    assistantBubble.innerHTML = '';
                                    isFirstToken = false;
                                }
                                const toolContainer = createToolLog(data.name, data.args);
                                assistantBubble.appendChild(toolContainer);
                                scrollToBottom();
                            } 
                            else if (currentEvent === 'tool_end') {
                                updateOrAddToolLog(assistantBubble, data.name, data.output);
                                scrollToBottom();
                            } 
                            else if (currentEvent === 'error') {
                                showToast(`Agent Error: ${data}`, 'error');
                            }
                        } catch (err) {
                            console.error('Failed to parse SSE data block:', err, line);
                        }
                    }
                }
            }

            // Fallback if no text tokens were streamed
            if (isFirstToken) {
                assistantBubble.innerHTML = formatMarkdown(responseText || 'No response details generated.');
            }

        } catch (error) {
            console.error('Streaming error:', error);
            showToast('Failed to connect to assistant stream.', 'error');
            assistantBubble.innerHTML = '<span class="status-error">Connection to server lost. Please retry.</span>';
        } finally {
            isGenerating = false;
            sendBtn.disabled = !userInput.value.trim();
            loadThreads(); // Refresh thread sidebar to show active/new items
        }
    });

    // ==========================================================================
    // File Upload Event Listeners
    // ==========================================================================
    
    // Trigger file selection window
    attachBtn.addEventListener('click', () => {
        if (isGenerating) {
            showToast('Cannot upload files while message is generating.', 'error');
            return;
        }
        fileInput.click();
    });

    // Handle file selection and upload
    fileInput.addEventListener('change', async () => {
        const file = fileInput.files[0];
        if (!file) return;

        // Ensure we have a thread ID before uploading
        if (!currentThreadId) {
            currentThreadId = generateUUID();
            activeThreadTitle.innerText = `Chat: ${currentThreadId.slice(0, 8)}...`;
            welcomeScreen.style.display = 'none';
            messagesArea.innerHTML = '';
        }

        // Validate file extension
        const allowedExtensions = ['.pdf', '.pptx', '.ppt'];
        const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
        if (!allowedExtensions.includes(fileExtension)) {
            showToast('Only PDF and PPTX/PPT files are supported.', 'error');
            fileInput.value = '';
            return;
        }

        // Set UI to uploading state
        attachBtn.classList.add('uploading');
        attachBtn.disabled = true;
        attachBtn.title = 'Uploading and indexing document...';
        showToast(`Indexing "${file.name}"... This might take a few seconds.`, 'info');

        const formData = new FormData();
        formData.append('file', file);
        formData.append('thread_id', currentThreadId);

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Upload failed');
            }

            const data = await response.json();
            showToast(`✅ "${file.name}" indexed successfully!`, 'info');
            
            // Refresh document badge
            updateThreadDocumentStatus(currentThreadId);
            
            // Refresh thread list in sidebar to make sure this thread is registered
            loadThreads();

        } catch (error) {
            console.error('File upload error:', error);
            showToast(`Upload failed: ${error.message}`, 'error');
        } finally {
            // Restore UI state
            attachBtn.classList.remove('uploading');
            attachBtn.disabled = false;
            attachBtn.title = 'Upload Document (PDF, PPTX)';
            fileInput.value = ''; // Reset file input
        }
    });

    // Initialize application state
    loadThreads();
});
