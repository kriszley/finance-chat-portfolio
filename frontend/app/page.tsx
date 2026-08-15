"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, type UIMessage } from "ai";
import { useEffect, useRef, useState } from "react";
import { Send, Plus, Trash2, MessageSquare } from "lucide-react";
import { ChatMessage } from "@/components/chat/message";
import { FileUpload } from "@/components/chat/file-upload";
import {
  listConversations,
  createConversation,
  getMessages,
  saveMessage,
  deleteConversation,
} from "@/lib/api";

interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

const chatTransport = new DefaultChatTransport({ api: "/api/chat" });

function messageText(message: UIMessage): string {
  return message.parts
    .filter((part) => part.type === "text")
    .map((part) => (part as { type: "text"; text: string }).text)
    .join("");
}

function messageToolParts(message: UIMessage) {
  return message.parts.filter(
    (part) => part.type.startsWith("tool-") || part.type === "dynamic-tool"
  );
}

export default function Home() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<
    string | null
  >(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  const { messages, sendMessage, setMessages, status } = useChat({
    transport: chatTransport,
    onFinish: async ({ message }) => {
      if (activeConversationId) {
        await saveMessage(
          activeConversationId,
          message.role,
          messageText(message),
          messageToolParts(message).length
            ? JSON.stringify(messageToolParts(message))
            : undefined
        );
      }
    },
  });
  const isLoading = status === "submitted" || status === "streaming";

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, []);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  async function loadConversations() {
    try {
      const convos = await listConversations();
      setConversations(convos);
    } catch {
      // Backend not running
    }
  }

  async function handleNewConversation() {
    try {
      const conv = await createConversation();
      setConversations((prev) => [conv, ...prev]);
      setActiveConversationId(conv.id);
      setMessages([]);
    } catch {
      // Backend not running, still allow chat
      setActiveConversationId(null);
      setMessages([]);
    }
  }

  async function handleSelectConversation(id: string) {
    setActiveConversationId(id);
    try {
      const msgs = await getMessages(id);
      setMessages(
        msgs.map((m: { id: string; role: string; content: string }) => ({
          id: m.id,
          role: m.role as "user" | "assistant",
          parts: [{ type: "text" as const, text: m.content }],
        }))
      );
    } catch {
      setMessages([]);
    }
  }

  async function handleDeleteConversation(id: string) {
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeConversationId === id) {
        setActiveConversationId(null);
        setMessages([]);
      }
    } catch {
      // ignore
    }
  }

  function handleUploadComplete(filename: string, filePath: string) {
    sendMessage({
      text: `I just uploaded a bank CSV file: ${filename}. Please process it using upload_and_process_csv with file_path "${filePath}" and tell me what you found.`,
    });
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const submittedText = input.trim();
    if (!submittedText) return;

    // Auto-create conversation if none active
    if (!activeConversationId) {
      try {
        const conv = await createConversation(
          submittedText.slice(0, 50) || "New Conversation"
        );
        setConversations((prev) => [conv, ...prev]);
        setActiveConversationId(conv.id);
        await saveMessage(conv.id, "user", submittedText);
      } catch {
        // Backend not running
      }
    } else {
      await saveMessage(activeConversationId, "user", submittedText);
    }

    setInput("");
    sendMessage({ text: submittedText });
  }

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      {sidebarOpen && (
        <div className="flex w-64 flex-col border-r border-border bg-card">
          <div className="flex items-center justify-between p-4">
            <h1 className="text-sm font-semibold">Finance Chat</h1>
            <button
              onClick={handleNewConversation}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              title="New conversation"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-2">
            {conversations.map((conv) => (
              <div
                key={conv.id}
                className={`group mb-1 flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors cursor-pointer ${
                  activeConversationId === conv.id
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
                }`}
                onClick={() => handleSelectConversation(conv.id)}
              >
                <MessageSquare className="h-4 w-4 shrink-0" />
                <span className="flex-1 truncate">{conv.title}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteConversation(conv.id);
                  }}
                  className="hidden h-6 w-6 items-center justify-center rounded text-muted-foreground hover:text-destructive group-hover:flex"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main chat area */}
      <div className="flex flex-1 flex-col">
        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="mb-4 text-4xl">💰</div>
              <h2 className="mb-2 text-lg font-medium">
                Personal Finance Assistant
              </h2>
              <p className="max-w-md text-sm text-muted-foreground">
                Upload a bank CSV (Scotiabank or BMO) to get started, or ask
                questions about your transaction data. I can show spending
                breakdowns, charts, and help categorize transactions.
              </p>
            </div>
          ) : (
            messages.map((message) => (
              <ChatMessage
                key={message.id}
                role={message.role}
                parts={message.parts}
              />
            ))
          )}

          {isLoading && messages[messages.length - 1]?.role === "user" && (
            <div className="mb-4 flex justify-start">
              <div className="rounded-2xl bg-secondary px-4 py-3">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <div className="h-2 w-2 animate-pulse rounded-full bg-primary" />
                  Thinking...
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="border-t border-border p-4">
          <form onSubmit={onSubmit} className="mx-auto flex max-w-3xl gap-2">
            <FileUpload
              onUploadComplete={handleUploadComplete}
              disabled={isLoading}
            />
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask about your finances..."
              className="flex-1 rounded-lg border border-input bg-background px-4 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
