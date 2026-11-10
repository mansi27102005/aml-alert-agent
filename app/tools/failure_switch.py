import os

def is_tool_unavailable(tool_name: str) -> bool:
    failed_tools = os.getenv(
        "AML_FAIL_TOOLS", ""
    ).split(",")

    return tool_name.lower() in [
        tool.strip().lower()
        for tool in failed_tools
        if tool.strip()
    ]