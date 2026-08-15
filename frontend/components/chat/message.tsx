"use client";

import type { UIMessage } from "ai";
import { ChartRenderer } from "./chart-renderer";

interface MessageProps {
  role: string;
  parts: UIMessage["parts"];
}

export function ChatMessage({ role, parts }: MessageProps) {
  const isUser = role === "user";
  const text = parts
    .filter((part) => part.type === "text")
    .map((part) => (part as { type: "text"; text: string }).text)
    .join("");
  const toolParts = parts
    .filter((part) => part.type.startsWith("tool-") || part.type === "dynamic-tool")
    .map((part) => part as unknown as Record<string, unknown>);

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-secondary text-secondary-foreground"
        }`}
      >
        {text && (
          <div className="whitespace-pre-wrap text-sm leading-relaxed">
            {text}
          </div>
        )}

        {toolParts.map((part, i) => {
          const type = String(part.type || "");
          const toolName =
            type === "dynamic-tool"
              ? String(part.toolName || "tool")
              : type.replace(/^tool-/, "");
          const state = String(part.state || "");
          const output = part.output;

          return (
          <div key={`${toolName}-${i}`}>
            {state !== "output-available" && state !== "output-error" && (
              <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                <div className="h-2 w-2 animate-pulse rounded-full bg-primary" />
                Running {formatToolName(toolName)}...
              </div>
            )}

            {state === "output-available" && toolName === "render_chart" && (
              <ChartRenderer chart={output as any} />
            )}

            {state === "output-available" &&
              toolName !== "render_chart" &&
              output !== undefined &&
              output !== null && (
                <ToolResult toolName={toolName} result={output} />
              )}
            {state === "output-error" && (
              <ToolResult
                toolName={toolName}
                result={{ error: String(part.errorText || "Tool failed") }}
              />
            )}
          </div>
          );
        })}
      </div>
    </div>
  );
}

function ToolResult({
  toolName,
  result,
}: {
  toolName: string;
  result: unknown;
}) {
  const data = result as Record<string, unknown>;

  if (data?.error) {
    return (
      <div className="mt-2 rounded border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive">
        {String(data.error)}
      </div>
    );
  }

  return null;
}

function formatToolName(name: string): string {
  return name
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
