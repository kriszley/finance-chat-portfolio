"""
Tool definitions for the finance chat agent.
Python is the single source of truth. Next.js fetches these via GET /api/tools/schema.
"""

TOOL_DEFINITIONS = [
    {
        "name": "query_transactions",
        "description": "Filter and search transactions by category, merchant, month, amount range, or direction. Returns matching transactions and summary statistics.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by category name (e.g., 'Food & Dining', 'Transportation')"
                },
                "subcategory": {
                    "type": "string",
                    "description": "Filter by subcategory (e.g., 'Coffee', 'Mortgage')"
                },
                "month": {
                    "type": "string",
                    "description": "Filter by month in YYYY-MM format (e.g., '2026-03')"
                },
                "merchant": {
                    "type": "string",
                    "description": "Search by merchant name (partial match)"
                },
                "min_amount": {
                    "type": "number",
                    "description": "Minimum transaction amount"
                },
                "max_amount": {
                    "type": "number",
                    "description": "Maximum transaction amount"
                },
                "direction": {
                    "type": "string",
                    "enum": ["debit", "credit"],
                    "description": "Filter by transaction direction"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of transactions to return (default 50)",
                    "default": 50
                }
            },
            "required": []
        }
    },
    {
        "name": "get_spending_breakdown",
        "description": "Get a category-level spending summary for a given month, showing totals and percentages per category. Only includes debit transactions (spending).",
        "parameters": {
            "type": "object",
            "properties": {
                "month": {
                    "type": "string",
                    "description": "Month in YYYY-MM format (e.g., '2026-03'). If omitted, uses the most recent month."
                }
            },
            "required": []
        }
    },
    {
        "name": "get_monthly_comparison",
        "description": "Compare spending across two or more months, showing the delta by category.",
        "parameters": {
            "type": "object",
            "properties": {
                "months": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of months to compare in YYYY-MM format (e.g., ['2026-02', '2026-03'])"
                }
            },
            "required": ["months"]
        }
    },
    {
        "name": "upload_and_process_csv",
        "description": "Run the full finance pipeline on an uploaded CSV file. Parses, normalizes, deduplicates, detects transfers, and categorizes transactions. Results are saved to the database.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Opaque token returned by the upload endpoint"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "get_pipeline_status",
        "description": "Check what data has been loaded, which months are available, and how many transactions exist.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "correct_category",
        "description": "Fix a miscategorized transaction. Updates the transaction and adds a new rule to merchant_rules.csv so future transactions from the same merchant are categorized correctly.",
        "parameters": {
            "type": "object",
            "properties": {
                "transaction_id": {
                    "type": "string",
                    "description": "The transaction_id of the transaction to correct"
                },
                "category": {
                    "type": "string",
                    "description": "The correct category"
                },
                "subcategory": {
                    "type": "string",
                    "description": "The correct subcategory (optional)"
                },
                "expense_type": {
                    "type": "string",
                    "enum": ["fixed", "variable", "transfer", "investment", "income", "savings"],
                    "description": "The correct expense type"
                }
            },
            "required": ["transaction_id", "category", "expense_type"]
        }
    },
]

# render_chart is a client-side tool handled by the frontend.
# It's included here for documentation but not sent to FastAPI.
RENDER_CHART_DEFINITION = {
    "name": "render_chart",
    "description": "Return structured chart data for the frontend to render inline in the chat. Supports bar, pie, and line charts.",
    "parameters": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["bar", "pie", "line"],
                "description": "Chart type"
            },
            "title": {
                "type": "string",
                "description": "Chart title"
            },
            "xKey": {
                "type": "string",
                "description": "Key for x-axis / labels"
            },
            "yKey": {
                "type": "string",
                "description": "Key for y-axis / values"
            },
            "data": {
                "type": "array",
                "items": {"type": "object"},
                "description": "Array of data points"
            }
        },
        "required": ["type", "title", "xKey", "yKey", "data"]
    }
}


def get_all_tool_schemas():
    """Return all tool definitions including render_chart for the frontend."""
    return TOOL_DEFINITIONS + [RENDER_CHART_DEFINITION]
