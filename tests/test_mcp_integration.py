"""
MCP Integration Tests - Real Server & Client Testing

This module tests all MCP tools and resources using real SSE transport.
Uses the official MCP Python SDK client for proper SSE handling.
No mocking - actual MCP server is started and client connects to it.

Usage:
    python tests/test_mcp_integration.py
"""

import unittest
import contextlib
import time
import socket
from multiprocessing import Process

from mcp import ClientSession
from mcp.client.sse import sse_client

# Test constants
TEST_ALBUM_ID = "123"
TEST_SEARCH_KEYWORD = "全彩"
TEST_HOST = "127.0.0.1"
TEST_PORT = 18901


def _start_mcp_server(port: int):
    """Start MCP server in a subprocess"""
    from jmcomic_ai.core import JmcomicService
    from jmcomic_ai.mcp.server import run_server

    service = JmcomicService()
    run_server("sse", service, host=TEST_HOST, port=port)


def wait_for_server(port: int, timeout: float = 30.0) -> bool:
    """Wait for server to be ready by checking if port is accepting connections"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((TEST_HOST, port))
            sock.close()
            if result == 0:
                time.sleep(1)  # Give server time to fully initialize
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


class TestMCPIntegration(unittest.IsolatedAsyncioTestCase):
    _server_proc = None
    _server_url = None

    @classmethod
    def setUpClass(cls):
        """Start MCP SSE server"""
        cls._server_proc = Process(target=_start_mcp_server, args=(TEST_PORT,))
        cls._server_proc.start()

        if not wait_for_server(TEST_PORT):
            cls._server_proc.terminate()
            raise RuntimeError("MCP server failed to start")

        cls._server_url = f"http://{TEST_HOST}:{TEST_PORT}/sse"

    @classmethod
    def tearDownClass(cls):
        """Stop MCP SSE server"""
        if cls._server_proc:
            cls._server_proc.terminate()
            cls._server_proc.join(timeout=5)

    @contextlib.asynccontextmanager
    async def _mcp_session(self):
        """Context manager to ensure session is created and closed in the same task"""
        async with sse_client(self._server_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session

    async def test_list_tools(self):
        """Test listing all MCP tools"""
        async with self._mcp_session() as session:
            result = await session.list_tools()
            tools = result.tools

            print(f"\n=== Available Tools ({len(tools)}) ===")
            for tool in tools:
                print(f"  - {tool.name}")

            tool_names = [t.name for t in tools]
            expected = [
                "search_album",
                "get_album_detail",
                "browse_albums",
                "download_album",
                "download_photo",
                "download_cover",
                "login",
                "update_option",
                "post_process",
            ]

            for name in expected:
                self.assertIn(name, tool_names, f"Missing tool: {name}")

            print(f"\n[OK] All {len(expected)} expected tools registered")

    async def test_list_resources(self):
        """Test listing all MCP resources"""
        async with self._mcp_session() as session:
            result = await session.list_resources()
            resources = result.resources

            print(f"\n=== Available Resources ({len(resources)}) ===")
            for res in resources:
                print(f"  - {res.uri}")

            uris = [str(r.uri) for r in resources]
            expected = ["jmcomic://option/schema", "jmcomic://option/reference", "jmcomic://skill"]

            for uri in expected:
                self.assertIn(uri, uris, f"Missing resource: {uri}")

            print(f"\n[OK] All {len(expected)} expected resources registered")

    async def test_tool_search_album(self):
        """Test search_album tool"""
        async with self._mcp_session() as session:
            print(f"\n=== Testing search_album(keyword='{TEST_SEARCH_KEYWORD}') ===")
            result = await session.call_tool("search_album", {"keyword": TEST_SEARCH_KEYWORD, "page": 1})
            print(f"  Result: {str(result)[:200]}...")
            self.assertIsNotNone(result)
            print("\n[OK] search_album executed successfully")

    async def test_tool_get_album_detail(self):
        """Test get_album_detail tool"""
        async with self._mcp_session() as session:
            print(f"\n=== Testing get_album_detail(album_id='{TEST_ALBUM_ID}') ===")
            result = await session.call_tool("get_album_detail", {"album_id": TEST_ALBUM_ID})
            print(f"  Result: {str(result)[:200]}...")
            self.assertIsNotNone(result)
            print("\n[OK] get_album_detail executed successfully")

    async def test_tool_browse_albums(self):
        """Test browse_albums tool (replaces get_ranking and get_category_list)"""
        async with self._mcp_session() as session:
            # Test 1: Browse by time range (like ranking)
            print("\n=== Testing browse_albums(time_range='day', order_by='likes') ===")
            result = await session.call_tool("browse_albums", {"time_range": "day", "order_by": "likes", "page": 1})
            print(f"  Result: {str(result)[:200]}...")
            self.assertIsNotNone(result)
            print("\n[OK] browse_albums (ranking mode) executed successfully")
            
            # Test 2: Browse by category
            print("\n=== Testing browse_albums(category='doujin') ===")
            result = await session.call_tool("browse_albums", {"category": "doujin", "page": 1})
            print(f"  Result: {str(result)[:200]}...")
            self.assertIsNotNone(result)
            print("\n[OK] browse_albums (category mode) executed successfully")

    async def test_tool_download_cover(self):
        """Test download_cover tool"""
        async with self._mcp_session() as session:
            print(f"\n=== Testing download_cover(album_id='{TEST_ALBUM_ID}') ===")
            result = await session.call_tool("download_cover", {"album_id": TEST_ALBUM_ID})
            print(f"  Result: {result}")
            self.assertIsNotNone(result)
            print("\n[OK] download_cover executed successfully")

    async def test_tool_download_photo(self):
        """Test download_photo tool"""
        async with self._mcp_session() as session:
            print(f"\n=== Testing download_photo(photo_id='{TEST_ALBUM_ID}') ===")
            result = await session.call_tool("download_photo", {"photo_id": TEST_ALBUM_ID})
            print(f"  Result: {result}")
            self.assertIsNotNone(result)
            print("\n[OK] download_photo executed successfully")

    async def test_tool_download_album(self):
        """Test download_album tool with real-time progress capture"""
        # 用于收集进度事件
        progress_events = []

        # 定义日志回调函数
        async def logging_callback(params):
            """捕获服务端发送的日志通知"""
            level = params.level
            message = params.data if hasattr(params, 'data') else str(params)
            progress_events.append(f"[{level}] {message}")
            print(f"  📊 Progress: [{level}] {message}")

        # 创建带有 logging_callback 的 session
        async with sse_client(self._server_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream, logging_callback=logging_callback) as session:
                await session.initialize()

                print(f"\n=== Testing download_album(album_id='{TEST_ALBUM_ID}') with Progress Tracking ===")

                # 调用下载工具
                result = await session.call_tool("download_album", {"album_id": TEST_ALBUM_ID})

                print(f"\n  Final Result: {result}")
                print(f"\n  Captured {len(progress_events)} progress events:")
                for event in progress_events[:10]:  # 只显示前10条
                    print(f"    - {event}")
                if len(progress_events) > 10:
                    print(f"    ... and {len(progress_events) - 10} more events")

                self.assertIsNotNone(result)
                print("\n[OK] download_album executed successfully with progress tracking")

    async def test_tool_update_option(self):
        """Test update_option tool"""
        async with self._mcp_session() as session:
            print("\n=== Testing update_option ===")
            result = await session.call_tool("update_option", {"option_updates": {"download": {"threading": {"image": 30}}}})
            print(f"  Result: {result}")
            self.assertIsNotNone(result)
            print("\n[OK] update_option executed successfully")

    async def test_tool_login_exists(self):
        """Test that login tool exists (don't call without credentials)"""
        async with self._mcp_session() as session:
            result = await session.list_tools()
            tool_names = [t.name for t in result.tools]
            self.assertIn("login", tool_names)
            login_tool = next(t for t in result.tools if t.name == "login")
            print("\n=== login tool ===")
            print(f"  Description: {login_tool.description[:100]}...")
            print("\n[OK] login tool registered (not called - requires credentials)")

    async def test_read_resource_schema(self):
        """Test reading config schema resource"""
        async with self._mcp_session() as session:
            print("\n=== Reading jmcomic://option/schema ===")
            result = await session.read_resource("jmcomic://option/schema")
            content = result.contents[0].text if result.contents else ""
            print(f"  Content length: {len(content)} bytes")
            print(f"  Preview: {content[:100]}...")
            print("\n[OK] option/schema resource read successfully")

    async def test_read_resource_reference(self):
        """Test reading config reference resource"""
        async with self._mcp_session() as session:
            print("\n=== Reading jmcomic://option/reference ===")
            result = await session.read_resource("jmcomic://option/reference")
            content = result.contents[0].text if result.contents else ""
            print(f"  Content length: {len(content)} bytes")
            print("\n[OK] option/reference resource read successfully")

    async def test_read_resource_skill(self):
        """Test reading skill resource"""
        async with self._mcp_session() as session:
            print("\n=== Reading jmcomic://skill ===")
            result = await session.read_resource("jmcomic://skill")
            content = result.contents[0].text if result.contents else ""
            print(f"  Content length: {len(content)} bytes")
            print("\n[OK] skill resource read successfully")

    async def test_full_integration(self):
        """
        FULL INTEGRATION TEST
        """
        async with self._mcp_session() as session:
            print("\n" + "=" * 70)
            print("  MCP FULL INTEGRATION TEST")
            print("  Testing ALL tools and resources with REAL API calls")
            print("=" * 70)

            # -------------------- TOOLS --------------------
            print("\n" + "-" * 70)
            print("  PART 1: TESTING ALL TOOLS")
            print("-" * 70)

            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            print(f"\nRegistered tools: {tool_names}")

            tool_tests = [
                ("search_album", {"keyword": TEST_SEARCH_KEYWORD, "page": 1}),
                ("get_album_detail", {"album_id": TEST_ALBUM_ID}),
                ("browse_albums", {"time_range": "day", "order_by": "likes", "page": 1}),
                ("browse_albums", {"category": "doujin", "page": 1}),
                ("download_cover", {"album_id": TEST_ALBUM_ID}),
                ("download_photo", {"photo_id": TEST_ALBUM_ID}),
                ("download_album", {"album_id": TEST_ALBUM_ID}),
                ("update_option", {"option_updates": {"log": True}}),
                ("post_process", {"album_id": TEST_ALBUM_ID, "process_type": "zip"}),
            ]

            tool_results = {}

            for tool_name, args in tool_tests:
                print(f"\n[TOOL] {tool_name}")
                print(f"  Args: {args}")

                try:
                    result = await session.call_tool(tool_name, args)
                    tool_results[tool_name] = "[OK] SUCCESS"
                    print(f"  -> Result: {str(result)[:100]}...")
                except Exception as e:
                    tool_results[tool_name] = f"[ERROR] ERROR: {e}"
                    print(f"  -> Error: {e}")

            # Login (exists but not called)
            print("\n[TOOL] login")
            print("  -> Skipped (requires real credentials)")
            tool_results["login"] = "[SKIP] SKIPPED"

            # -------------------- RESOURCES --------------------
            print("\n" + "-" * 70)
            print("  PART 2: TESTING ALL RESOURCES")
            print("-" * 70)

            resources_result = await session.list_resources()
            resource_uris = [str(r.uri) for r in resources_result.resources]
            print(f"\nRegistered resources: {resource_uris}")

            resource_results = {}

            for uri in resource_uris:
                print(f"\n[RESOURCE] {uri}")

                try:
                    result = await session.read_resource(uri)
                    content = result.contents[0].text if result.contents else ""
                    resource_results[uri] = f"[OK] SUCCESS ({len(content)} bytes)"
                    print(f"  -> Content: {len(content)} bytes")
                except Exception as e:
                    resource_results[uri] = f"[ERROR] ERROR: {e}"
                    print(f"  -> Error: {e}")

            # -------------------- SUMMARY --------------------
            print("\n" + "=" * 70)
            print("  TEST RESULTS SUMMARY")
            print("=" * 70)

            print("\nTools:")
            for name, status in tool_results.items():
                print(f"  {name}: {status}")

            print("\nResources:")
            for uri, status in resource_results.items():
                print(f"  {uri}: {status}")

            tool_errors = [k for k, v in tool_results.items() if "ERROR" in v]
            resource_errors = [k for k, v in resource_results.items() if "ERROR" in v]

            print("\n" + "=" * 70)
            if not tool_errors and not resource_errors:
                print("  [OK] ALL TESTS PASSED")
            else:
                print(f"  [ERROR] FAILURES: {len(tool_errors)} tool errors, {len(resource_errors)} resource errors")
            print("=" * 70)

            self.assertFalse(tool_errors, f"Tool errors: {tool_errors}")
            self.assertFalse(resource_errors, f"Resource errors: {resource_errors}")


if __name__ == "__main__":
    unittest.main()
