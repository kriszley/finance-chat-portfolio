import { anthropic } from "@ai-sdk/anthropic";
import {
  convertToModelMessages,
  stepCountIs,
  streamText,
  tool,
  type UIMessage,
} from "ai";
import { z } from "zod";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

// Cache tool schemas from backend
let cachedSchemas: Record<string, unknown>[] | null = null;

async function getToolSchemas() {
  if (cachedSchemas) return cachedSchemas;
  try {
    const res = await fetch(`${BACKEND_URL}/api/tools/schema`);
    const data = await res.json();
    cachedSchemas = data.tools;
    return cachedSchemas;
  } catch {
    return [];
  }
}

async function getSystemPrompt() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/status`);
    const status = await res.json();

    if (!status.has_data) {
      return `You are a personal finance assistant. No transaction data has been uploaded yet. Ask the user to upload a bank CSV file using the upload button (paperclip icon). Supported banks: Scotiabank, BMO.`;
    }

    return `You are a personal finance assistant. You have access to the user's processed bank transaction data.

Available data:
- Months: ${JSON.stringify(status.available_months)}
- Accounts: ${JSON.stringify(status.accounts)}
- Total transactions: ${status.total_transactions}
- Categories: ${JSON.stringify(status.categories)}

Use the query_transactions and get_spending_breakdown tools to answer questions with real data. Never guess amounts, always query first. When a visual would help the user understand the data, use render_chart to show a bar, pie, or line chart inline.

If the user uploads a CSV, use upload_and_process_csv to run the pipeline and report the results.

If the user wants to correct a category, use correct_category to update the transaction and create a rule for future transactions.

Be concise and specific with numbers. Format currency as $X,XXX.XX CAD.`;
  } catch {
    return "You are a personal finance assistant. The backend is not available. Please ensure the backend server is running on port 8000.";
  }
}

async function executeBackendTool(toolName: string, args: Record<string, unknown>) {
  const res = await fetch(`${BACKEND_URL}/api/tools/${toolName}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ arguments: args }),
  });
  const data = await res.json();
  if (data.error) {
    return { error: data.error };
  }
  return data.result;
}

export async function POST(req: Request) {
  if (process.env.ENABLE_CLOUD_LLM !== "true") {
    return Response.json(
      {
        error:
          "Cloud AI is disabled. Set ENABLE_CLOUD_LLM=true only after reviewing PRIVACY.md.",
      },
      { status: 503 }
    );
  }

  const { messages }: { messages: UIMessage[] } = await req.json();

  const systemPrompt = await getSystemPrompt();

  const result = streamText({
    model: anthropic(
      process.env.ANTHROPIC_MODEL || "claude-sonnet-4-20250514"
    ),
    system: systemPrompt,
    messages: await convertToModelMessages(messages),
    tools: {
      query_transactions: tool({
        description:
          "Filter and search transactions by category, merchant, month, amount range, or direction.",
        inputSchema: z.object({
          category: z.string().optional().describe("Filter by category"),
          subcategory: z.string().optional().describe("Filter by subcategory"),
          month: z.string().optional().describe("YYYY-MM format"),
          merchant: z.string().optional().describe("Search by merchant name"),
          min_amount: z.number().optional().describe("Minimum amount"),
          max_amount: z.number().optional().describe("Maximum amount"),
          direction: z.enum(["debit", "credit"]).optional(),
          limit: z.number().optional().default(50),
        }),
        execute: async (args) => executeBackendTool("query_transactions", args),
      }),
      get_spending_breakdown: tool({
        description:
          "Category-level spending summary for a given month, showing totals and percentages.",
        inputSchema: z.object({
          month: z.string().optional().describe("YYYY-MM format"),
        }),
        execute: async (args) =>
          executeBackendTool("get_spending_breakdown", args),
      }),
      get_monthly_comparison: tool({
        description: "Compare spending across two or more months.",
        inputSchema: z.object({
          months: z
            .array(z.string())
            .describe("Months to compare in YYYY-MM format"),
        }),
        execute: async (args) =>
          executeBackendTool("get_monthly_comparison", args),
      }),
      upload_and_process_csv: tool({
        description:
          "Run the full finance pipeline on an uploaded CSV. Parses, normalizes, deduplicates, and categorizes.",
        inputSchema: z.object({
          file_path: z.string().describe("Opaque upload token returned by the server"),
        }),
        execute: async (args) =>
          executeBackendTool("upload_and_process_csv", args),
      }),
      get_pipeline_status: tool({
        description:
          "Check what data has been loaded, available months, and transaction counts.",
        inputSchema: z.object({}),
        execute: async () => executeBackendTool("get_pipeline_status", {}),
      }),
      correct_category: tool({
        description:
          "Fix a miscategorized transaction and add a rule for future transactions.",
        inputSchema: z.object({
          transaction_id: z.string().describe("Transaction ID to correct"),
          category: z.string().describe("Correct category"),
          subcategory: z.string().optional().describe("Correct subcategory"),
          expense_type: z
            .enum([
              "fixed",
              "variable",
              "transfer",
              "investment",
              "income",
              "savings",
            ])
            .describe("Correct expense type"),
        }),
        execute: async (args) =>
          executeBackendTool("correct_category", args),
      }),
      render_chart: tool({
        description:
          "Return structured chart data for inline rendering. Supports bar, pie, and line charts.",
        inputSchema: z.object({
          type: z.enum(["bar", "pie", "line"]).describe("Chart type"),
          title: z.string().describe("Chart title"),
          xKey: z.string().describe("Key for x-axis / labels"),
          yKey: z.string().describe("Key for y-axis / values"),
          data: z
            .array(z.record(z.string(), z.unknown()))
            .describe("Array of data points"),
        }),
        execute: async (args) => args,
      }),
    },
    stopWhen: stepCountIs(5),
  });

  return result.toUIMessageStreamResponse();
}
