"""Purpose: MCP integration surfaces for governed Mullu capability access.
Governance scope: MCP server runtime and capability import/export bridges.
Dependencies: mcoi_runtime.mcp.server and capability bridge modules.
Invariants: external tools must pass through governed capability contracts
before execution.
"""

from .capability_bridge import (
    MCPToolDescriptor,
    MCPToolExport,
    export_capability_as_mcp_tool,
    import_mcp_tool_as_capability,
    mcp_capability_id,
)
from .governed_executor import (
    GovernedMCPExecutionContext,
    GovernedMCPExecutionAudit,
    GovernedMCPExecutionReceipt,
    GovernedMCPExecutionResult,
    GovernedMCPExecutor,
    MCPToolCallResult,
)

__all__ = [
    "GovernedMCPExecutionContext",
    "GovernedMCPExecutionAudit",
    "GovernedMCPExecutionReceipt",
    "GovernedMCPExecutionResult",
    "GovernedMCPExecutor",
    "MCPToolDescriptor",
    "MCPToolExport",
    "MCPToolCallResult",
    "export_capability_as_mcp_tool",
    "import_mcp_tool_as_capability",
    "mcp_capability_id",
]
