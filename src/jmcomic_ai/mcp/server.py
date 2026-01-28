import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, Literal, cast

from mcp.server.fastmcp import FastMCP

from jmcomic_ai.core import JmcomicService


def _is_public_method(name: str, method: Any) -> bool:
    """判断是否为需要暴露的公共方法"""
    # 排除私有方法、内部方法和特殊方法
    if name.startswith("_"):
        return False

    # 排除非方法
    if not callable(method):
        return False

    # 排除注释里有约定非工具的方法
    if method.__doc__ and "[not a tool]" in method.__doc__:
        return False

    return True


def _create_tool_wrapper(method_name: str, method: Callable) -> Callable:
    """为 service 方法创建一个 tool 包装器"""

    if inspect.iscoroutinefunction(method):

        @wraps(method)
        async def async_wrapper(*args, **kwargs):
            return await method(*args, **kwargs)

        wrapper = async_wrapper
    else:

        @wraps(method)
        def sync_wrapper(*args, **kwargs):
            return method(*args, **kwargs)

        wrapper = sync_wrapper

    # 保留原方法的签名和文档
    wrapper.__name__ = method_name
    wrapper.__doc__ = method.__doc__
    wrapper.__annotations__ = method.__annotations__
    wrapper.__signature__ = inspect.signature(method)  # type: ignore

    return wrapper


def _register_service_tools(mcp_server: FastMCP, service: JmcomicService):
    """动态注册 service 的所有公共方法为 MCP tools"""

    # 获取 JmcomicService 类的所有方法
    for name, method in inspect.getmembers(service, predicate=inspect.ismethod):
        # 只处理公共业务方法
        if not _is_public_method(name, method):
            continue

        # 创建绑定到 service 实例的包装器
        # 注意：method 已经是绑定方法，直接使用即可
        tool_func = _create_tool_wrapper(name, method)

        # 注册为 MCP tool
        mcp_server.tool()(tool_func)

        service.logger.info(f"Registered tool: {name}")


def _register_resources(mcp_server: FastMCP, service: JmcomicService):
    """注册 MCP Resources，让 AI 可以查阅配置文档"""
    from pathlib import Path

    skills_dir = Path(__file__).parent.parent / "skills" / "jmcomic"

    @mcp_server.resource("jmcomic://option/schema")
    def get_option_schema() -> str:
        """Return the JSON Schema for JmOption"""
        schema_path = skills_dir / "assets" / "option_schema.json"
        if schema_path.exists():
            return schema_path.read_text(encoding="utf-8")
        return "{}"

    @mcp_server.resource("jmcomic://option/reference")
    def get_option_reference() -> str:
        """Return the option reference documentation"""
        ref_path = skills_dir / "references" / "reference.md"
        if ref_path.exists():
            return ref_path.read_text(encoding="utf-8")
        return "No reference documentation available"

    @mcp_server.resource("jmcomic://skill")
    def get_skill_doc() -> str:
        """Return the SKILL.md for AI guidance"""
        skill_path = skills_dir / "SKILL.md"
        if skill_path.exists():
            return skill_path.read_text(encoding="utf-8")
        return "No skill documentation available"

    service.logger.info("Registered 3 MCP resources")


def run_server(transport: str, service: JmcomicService, host: str = "127.0.0.1", port: int = 8000):
    """启动 MCP 服务器，自动注册 service 的所有公共方法为 tools"""

    mcp_server = FastMCP("jmcomic-ai")

    # 动态注册所有 service 方法为 tools
    _register_service_tools(mcp_server, service)

    # 注册 MCP Resources
    _register_resources(mcp_server, service)

    # 映射 transport 参数
    # CLI 使用简短的 "stdio"/"sse"/"http"，FastMCP 需要完整的 "stdio"/"streamable-http"
    transport_map = {
        "stdio": "stdio",
        "sse": "sse",
        "http": "streamable-http",
    }

    mapped_transport = transport_map.get(transport)
    if not mapped_transport:
        raise ValueError(f"Unsupported transport: {transport}. Use {list(transport_map.keys())}")

    # stdio 传输不需要 host/port 配置
    if mapped_transport != "stdio":
        mcp_server.settings.host = host
        mcp_server.settings.port = port
    
    # 启动服务器
    mcp_server.run(transport=cast(Literal["stdio", "sse", "streamable-http"], mapped_transport))
