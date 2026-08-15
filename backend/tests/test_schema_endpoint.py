"""Tests for the tool schema endpoint."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.tool_definitions import get_all_tool_schemas, TOOL_DEFINITIONS


class TestToolSchemas:
    def test_schema_count(self):
        schemas = get_all_tool_schemas()
        # 6 backend tools + 1 client-side render_chart
        assert len(schemas) == 7

    def test_all_have_required_fields(self):
        for schema in get_all_tool_schemas():
            assert "name" in schema
            assert "description" in schema
            assert "parameters" in schema
            assert schema["parameters"]["type"] == "object"

    def test_tool_names(self):
        names = [t["name"] for t in get_all_tool_schemas()]
        assert "query_transactions" in names
        assert "get_spending_breakdown" in names
        assert "get_monthly_comparison" in names
        assert "upload_and_process_csv" in names
        assert "get_pipeline_status" in names
        assert "correct_category" in names
        assert "render_chart" in names

    def test_backend_tools_exclude_render_chart(self):
        names = [t["name"] for t in TOOL_DEFINITIONS]
        assert "render_chart" not in names
