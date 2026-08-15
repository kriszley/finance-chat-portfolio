const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export async function backendFetch(path: string, options?: RequestInit) {
  const url = `${BACKEND_URL}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(`Backend error (${res.status}): ${error}`);
  }
  return res.json();
}

export async function uploadFile(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BACKEND_URL}/api/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(`Upload failed (${res.status}): ${error}`);
  }
  return res.json();
}

export async function getToolSchemas() {
  return backendFetch("/api/tools/schema");
}

export async function getStatus() {
  return backendFetch("/api/status");
}

export async function executeTool(toolName: string, args: Record<string, unknown>) {
  return backendFetch(`/api/tools/${toolName}`, {
    method: "POST",
    body: JSON.stringify({ arguments: args }),
  });
}

// Conversation CRUD
export async function listConversations() {
  return backendFetch("/api/conversations");
}

export async function createConversation(title = "New Conversation") {
  return backendFetch("/api/conversations", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export async function getMessages(conversationId: string) {
  return backendFetch(`/api/conversations/${conversationId}/messages`);
}

export async function saveMessage(
  conversationId: string,
  role: string,
  content: string,
  toolCalls?: string
) {
  return backendFetch(`/api/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({ role, content, tool_calls: toolCalls }),
  });
}

export async function deleteConversation(conversationId: string) {
  return backendFetch(`/api/conversations/${conversationId}`, {
    method: "DELETE",
  });
}
