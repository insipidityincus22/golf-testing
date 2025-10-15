import asyncio
import os
import signal
import threading
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import httpx

try:
    from mcp import ClientSession
    from mcp.client.auth import OAuthClientProvider, TokenStorage
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp.client.streamable_http import streamablehttp_client
    from mcp.shared.auth import (
        OAuthClientInformationFull,
        OAuthClientMetadata,
        OAuthToken,
    )
    from mcp.types import Implementation
    from pydantic import AnyUrl
except ImportError:
    raise ImportError(
        "MCP SDK with OAuth support required. Install with: pip install mcp"
    ) from None


class InMemoryTokenStorage(TokenStorage):
    """In-memory token storage implementation for OAuth."""

    def __init__(self):
        self.tokens: OAuthToken | None = None
        self.client_info: OAuthClientInformationFull | None = None

    async def get_tokens(self) -> OAuthToken | None:
        """Get stored tokens."""
        return self.tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        """Store tokens."""
        self.tokens = tokens

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        """Get stored client information."""
        return self.client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        """Store client information."""
        self.client_info = client_info


class SharedTokenStorage(TokenStorage):
    """Shared token storage that persists across multiple MCP client instances."""

    _instances: dict[str, "SharedTokenStorage"] = {}

    def __init__(self, server_url: str):
        self.server_url = server_url
        self.tokens: OAuthToken | None = None
        self.client_info: OAuthClientInformationFull | None = None

    @classmethod
    def get_instance(cls, server_url: str) -> "SharedTokenStorage":
        """Get or create a shared token storage instance for the given server URL."""
        if server_url not in cls._instances:
            cls._instances[server_url] = cls(server_url)
        return cls._instances[server_url]

    @classmethod
    def clear_all(cls) -> None:
        """Clear all shared token storage instances."""
        cls._instances.clear()

    async def get_tokens(self) -> OAuthToken | None:
        """Get stored tokens."""
        return self.tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        """Store tokens."""
        self.tokens = tokens

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        """Get stored client information."""
        return self.client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        """Store client information."""
        self.client_info = client_info

    def has_valid_tokens(self) -> bool:
        """Check if we have valid tokens stored."""
        return self.tokens is not None


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback."""

    def do_GET(self):
        """Handle GET requests to the callback endpoint."""
        parsed_path = urlparse(self.path)

        if parsed_path.path == "/callback":
            # Parse query parameters
            params = parse_qs(parsed_path.query)

            # Store callback data on the server
            self.server.callback_data = {
                "code": params.get("code", [None])[0],
                "state": params.get("state", [None])[0],
                "error": params.get("error", [None])[0],
                "error_description": params.get("error_description", [None])[0],
            }

            # Send response to browser
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            if self.server.callback_data["error"]:
                html_content = f"""
                <html>
                <head><title>Authorization Error</title></head>
                <body>
                    <h2>Authorization Failed</h2>
                    <p>Error: {self.server.callback_data["error"]}</p>
                    <p>Description: {self.server.callback_data.get("error_description", "Unknown error")}</p>
                    <p>You can close this window.</p>
                </body>
                </html>
                """
            else:
                html_content = """
                <html>
                <head><title>Authorization Successful</title></head>
                <body>
                    <h2>Authorization Successful!</h2>
                    <p>You can close this window and return to the MCP Testing Framework.</p>
                    <script>setTimeout(() => window.close(), 2000);</script>
                </body>
                </html>
                """

            self.wfile.write(html_content.encode())
        else:
            # 404 for other paths
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default HTTP server logs."""
        pass


class CallbackServer:
    """Local HTTP server to handle OAuth callbacks."""

    def __init__(self, port: int = 3030):
        self.port = port
        self.server = None
        self.thread = None
        self.callback_data = None

    def start(self):
        """Start the callback server in a background thread."""
        self.server = HTTPServer(("localhost", self.port), CallbackHandler)
        self.server.callback_data = None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the callback server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1)

    def wait_for_callback(self, timeout: float = 120.0) -> dict[str, Any] | None:
        """Wait for OAuth callback with timeout."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.server and self.server.callback_data:
                return self.server.callback_data
            time.sleep(0.1)

        return None  # Timeout


@dataclass
class MCPServerConnection:
    """Represents a connection to an MCP server"""

    server_id: str
    session: ClientSession | None
    tools: list[dict[str, Any]]
    resources: list[dict[str, Any]]
    prompts: list[dict[str, Any]]
    server_config: dict[str, Any]
    # Store the context manager for proper cleanup
    _context_stack: Any = None
    _is_healthy: bool = True


class MCPClientManager:
    """
    Centralized MCP client manager that handles all server connections.
    This is independent of any LLM provider and can be used by any agent.
    Uses proper async context managers to avoid task group issues.
    """

    def __init__(self):
        self.connections: dict[str, MCPServerConnection] = {}
        self._active_contexts: dict[str, Any] = {}
        self._connection_locks: dict[str, asyncio.Lock] = {}
        self._stdio_processes: dict[str, Any] = {}  # Track stdio subprocesses

    def _parse_command(self, command_str: str) -> tuple[str, list[str]]:
        """
        Parse command string into command and args.

        Args:
            command_str: Command string (e.g., "npx -y @modelcontextprotocol/server-time")

        Returns:
            Tuple of (command, args)
        """
        parts = command_str.split()
        if not parts:
            raise ValueError("Command string cannot be empty")
        return parts[0], parts[1:]

    async def _handle_oauth_redirect(self, auth_url: str) -> None:
        """Handle OAuth redirect with enhanced URL presentation."""
        from rich.console import Console
        from rich.panel import Panel

        console = Console()

        # Create authorization panel
        auth_panel = Panel(
            f"""[bold green]🌐 Browser Authorization Required[/bold green]

Please visit this URL to authorize the MCP Testing Framework:

[cyan][link={auth_url}]{auth_url}[/link][/cyan]

[dim]• A new browser window should open automatically[/dim]
[dim]• Complete the authorization process[/dim]
[dim]• Return here to continue[/dim]""",
            title="🔐 OAuth Authorization",
            border_style="green",
            padding=(1, 2),
        )

        console.print()
        console.print(auth_panel)
        console.print()

        # Try to open browser automatically
        try:
            import webbrowser

            webbrowser.open(auth_url)
            console.print(
                "[dim]🔗 Opening authorization URL in your default browser...[/dim]"
            )
        except Exception:
            console.print(
                "[yellow]⚠️  Could not open browser automatically. Please copy the URL above.[/yellow]"
            )

        console.print()

    async def _handle_oauth_callback(self) -> tuple[str, str | None]:
        """Handle OAuth callback using local callback server."""
        # Import Rich components for better UI
        from rich.console import Console
        from rich.panel import Panel

        console = Console()

        # Create waiting panel
        waiting_panel = Panel(
            """[green]🔄 Waiting for OAuth Authorization[/green]

The authorization process is in progress:

• [dim]Complete the authorization in your browser window[/dim]
• [dim]The callback will be handled automatically[/dim]
• [dim]You can close the browser window after authorization[/dim]
• [dim]🔗 Local callback server started on http://localhost:3030/callback[/dim]

[yellow]💡 This may take up to 2 minutes to complete[/yellow]""",
            title="🔐 OAuth Authorization in Progress",
            border_style="blue",
            padding=(1, 2),
        )

        console.print()
        console.print(waiting_panel)
        console.print()

        # Start callback server
        callback_server = CallbackServer(port=3030)

        try:
            callback_server.start()

            # Wait for callback with timeout
            callback_data = callback_server.wait_for_callback(timeout=120.0)

            if not callback_data:
                console.print(
                    "[red]❌ OAuth callback timeout. Authorization may have failed or taken too long.[/red]"
                )
                raise RuntimeError("OAuth callback timeout")

            if callback_data.get("error"):
                error_msg = callback_data.get(
                    "error_description", callback_data.get("error")
                )
                console.print(f"[red]❌ OAuth authorization failed: {error_msg}[/red]")
                raise RuntimeError(f"OAuth authorization error: {error_msg}")

            if not callback_data.get("code"):
                console.print(
                    "[red]❌ No authorization code received in callback[/red]"
                )
                raise RuntimeError("No authorization code in OAuth callback")

            return callback_data["code"], callback_data.get("state")

        except KeyboardInterrupt:
            console.print("\n[yellow]⏹️  OAuth flow cancelled by user[/yellow]")
            raise
        finally:
            # Always clean up the callback server
            callback_server.stop()

    async def _discover_oauth_metadata(self, server_url: str) -> dict[str, Any]:
        """
        Discover OAuth configuration from server's .well-known endpoints.

        Args:
            server_url: Base URL of the server (e.g., http://localhost:3000)

        Returns:
            Combined metadata from authorization server and resource server
        """
        # Extract base URL (remove /mcp path if present)
        if server_url.endswith("/mcp"):
            base_url = server_url[:-4]  # Remove "/mcp"
        else:
            base_url = server_url.rstrip("/")

        async with httpx.AsyncClient() as client:
            try:
                # Fetch OAuth authorization server metadata
                auth_server_url = urljoin(
                    base_url + "/", ".well-known/oauth-authorization-server"
                )
                auth_response = await client.get(auth_server_url)
                auth_response.raise_for_status()
                auth_metadata = auth_response.json()

                # Fetch OAuth resource server metadata (optional)
                resource_url = urljoin(
                    base_url + "/", ".well-known/oauth-protected-resource"
                )
                try:
                    resource_response = await client.get(resource_url)
                    resource_response.raise_for_status()
                    resource_metadata = resource_response.json()
                except httpx.HTTPError:
                    # Resource server metadata is optional - many OAuth providers don't provide it
                    resource_metadata = {}

                # Combine both metadata sets
                return {
                    **auth_metadata,
                    "resource_metadata": resource_metadata,
                    "scopes_supported": resource_metadata.get(
                        "scopes_supported", auth_metadata.get("scopes_supported", [])
                    ),
                }

            except httpx.HTTPError as e:
                print(f"   ❌ Failed to discover OAuth metadata: {e}")
                raise RuntimeError(
                    f"Cannot discover OAuth metadata from {base_url}: {e}"
                ) from e

    def _build_client_metadata(
        self, oauth_metadata: dict | None = None
    ) -> OAuthClientMetadata:
        """Build OAuth client metadata using hardcoded testing defaults"""

        # Hardcoded values for testing framework
        redirect_uri = "http://localhost:3030/callback"
        client_name = "MCP Testing Framework"
        grant_types = ["authorization_code", "refresh_token"]
        response_types = ["code"]

        # Auto-discover scope or use default
        if oauth_metadata:
            scopes_supported = oauth_metadata.get("scopes_supported", [])
            scope = " ".join(scopes_supported) if scopes_supported else "user"
        else:
            scope = "user"

        return OAuthClientMetadata(
            client_name=client_name,
            redirect_uris=[AnyUrl(redirect_uri)],
            grant_types=grant_types,
            response_types=response_types,
            scope=scope,
        )

    @asynccontextmanager
    async def _get_stdio_connection_context(
        self, server_config: dict[str, Any]
    ) -> AsyncGenerator[ClientSession, None]:
        """
        Create async context manager for stdio MCP connections.
        Spawns a subprocess and communicates via stdin/stdout.
        Ensures proper process cleanup including child processes.

        Note: For best results with npm-based servers, consider using the node
        command directly instead of 'npm run start'. This avoids issues with
        child process cleanup when npm spawns node as a subprocess.
        Example: "node dist/index.js" instead of "npm run start"
        """
        command_str = server_config.get("command")
        if not command_str:
            raise ValueError("command is required for stdio transport")

        # Parse command string
        command, args = self._parse_command(command_str)

        # Get optional env and cwd from config
        env = server_config.get("env")
        cwd = server_config.get("cwd")

        # Create stdio server parameters with process group for proper cleanup
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env,
            cwd=cwd,
        )

        stdio_context = None
        process_handle = None

        try:
            # Connect via stdio
            stdio_context = stdio_client(server_params)
            read_stream, write_stream = await stdio_context.__aenter__()

            # Try to access the subprocess for cleanup (if available)
            # The stdio_client from MCP SDK should have a process attribute
            if hasattr(stdio_context, "_process"):
                process_handle = stdio_context._process

            client_info = Implementation(name="mcp-testing-framework", version="1.0.0")
            async with ClientSession(
                read_stream, write_stream, client_info=client_info
            ) as session:
                await asyncio.wait_for(session.initialize(), timeout=30.0)
                yield session

        except Exception as e:
            raise RuntimeError(
                f"Failed to connect via stdio with command '{command_str}': {e}"
            ) from e
        finally:
            # Ensure subprocess cleanup
            if stdio_context:
                try:
                    await stdio_context.__aexit__(None, None, None)
                except Exception:
                    pass

            # Additional cleanup: terminate any lingering processes
            # This helps with npm/node scenarios where child processes may persist
            if process_handle and hasattr(process_handle, "pid"):
                try:
                    # Try to terminate the process group (helps with npm -> node)
                    try:
                        os.killpg(os.getpgid(process_handle.pid), signal.SIGTERM)
                        # Give process a moment to terminate gracefully
                        await asyncio.sleep(0.1)
                        # Force kill if still running
                        try:
                            os.killpg(os.getpgid(process_handle.pid), signal.SIGKILL)
                        except (ProcessLookupError, PermissionError):
                            # Process already terminated, which is what we want
                            pass
                    except (ProcessLookupError, PermissionError, AttributeError):
                        # Process already terminated or no permission
                        pass
                except Exception:
                    # Ignore cleanup errors
                    pass

    @asynccontextmanager
    async def _get_connection_context(
        self, server_config: dict[str, Any]
    ) -> AsyncGenerator[ClientSession, None]:
        """
        Create a proper async context manager for MCP connections following the example pattern.
        This ensures transport and session contexts are properly nested.
        Supports both HTTP and stdio transports.
        """
        # Determine transport type
        transport = server_config.get("transport", "http")

        # Route to appropriate transport
        if transport == "stdio":
            async with self._get_stdio_connection_context(server_config) as session:
                yield session
            return

        # HTTP transport (existing code)
        url = server_config.get("url")
        if not url:
            raise ValueError("URL required for HTTP server")

        # Check for OAuth authentication
        use_oauth = server_config.get("oauth", False)

        if use_oauth:
            # Discover OAuth metadata from server
            try:
                oauth_metadata = await self._discover_oauth_metadata(url)
            except Exception:
                oauth_metadata = None

            # Create client metadata using hardcoded parameters
            client_metadata = self._build_client_metadata(oauth_metadata)

            # Create shared token storage and OAuth provider
            token_storage = SharedTokenStorage.get_instance(url)

            try:
                oauth_auth = OAuthClientProvider(
                    server_url=url,
                    client_metadata=client_metadata,
                    storage=token_storage,
                    redirect_handler=self._handle_oauth_redirect,
                    callback_handler=self._handle_oauth_callback,
                )

                # Use OAuth authentication
                async with streamablehttp_client(url, auth=oauth_auth) as (
                    read_stream,
                    write_stream,
                    _,
                ):
                    client_info = Implementation(
                        name="mcp-testing-framework", version="1.0.0"
                    )
                    async with ClientSession(
                        read_stream, write_stream, client_info=client_info
                    ) as session:
                        await asyncio.wait_for(session.initialize(), timeout=30.0)
                        yield session
                return
            except Exception as e:
                import traceback

                from rich.console import Console
                from rich.panel import Panel

                console = Console()

                # Get detailed error information for debugging
                error_details = str(e)
                exception_type = type(e).__name__

                # Handle TaskGroup exceptions specially
                if hasattr(e, "__notes__") and e.__notes__:
                    error_details += f"\nAdditional details: {'; '.join(e.__notes__)}"

                # Check for nested exceptions in TaskGroup/ExceptionGroup
                nested_errors = []
                if hasattr(e, "exceptions"):
                    for nested_e in e.exceptions:
                        nested_errors.append(f"{type(nested_e).__name__}: {nested_e!s}")

                if nested_errors:
                    error_details += f"\nNested exceptions: {'; '.join(nested_errors)}"

                # Provide specific error guidance based on exception type
                if "TaskGroup" in error_details or "ExceptionGroup" in exception_type:
                    error_panel = Panel(
                        f"""[red]❌ OAuth Token Exchange Failed[/red]

The OAuth authorization code was received but token exchange failed due to concurrent operation errors.

[yellow]Debug information:[/yellow]
• Exception type: {exception_type}
• Error details: {error_details}

[yellow]Possible solutions:[/yellow]
• Check server OAuth token endpoint is working correctly
• Verify client credentials and OAuth configuration
• Check server logs for token validation errors
• Try using token-based authentication instead

[dim]This typically indicates issues with the OAuth server's token endpoint or token validation.[/dim]""",
                        title="🔧 Token Exchange Error",
                        border_style="red",
                    )
                elif "metadata" in str(e).lower():
                    error_panel = Panel(
                        f"""[red]❌ OAuth Metadata Discovery Failed[/red]

The server might not support OAuth or the endpoints are not accessible.

[yellow]Possible solutions:[/yellow]
• Verify the server URL is correct
• Check if the server supports OAuth 2.0
• Ensure `.well-known/oauth-authorization-server` endpoint is available
• Try using token-based authentication instead

[dim]Original error:[/dim] {e!s}""",
                        title="🔧 Configuration Issue",
                        border_style="red",
                    )
                elif "callback" in str(e).lower():
                    error_panel = Panel(
                        f"""[red]❌ OAuth Callback Failed[/red]

There was an issue processing the OAuth authorization callback.

[yellow]Possible solutions:[/yellow]
• Ensure you copied the complete callback URL
• Check that the callback URL contains the authorization code
• Verify the OAuth flow completed successfully in your browser

[dim]Original error:[/dim] {e!s}""",
                        title="🔧 Callback Issue",
                        border_style="red",
                    )
                else:
                    error_panel = Panel(
                        f"""[red]❌ OAuth Setup Failed[/red]

{error_details}

[yellow]Exception type:[/yellow] {exception_type}

[yellow]Try using token-based authentication instead:[/yellow]
• Remove `oauth_config` from server configuration
• Add `authorization_token` with a Bearer token""",
                        title="🔧 Authentication Error",
                        border_style="red",
                    )

                console.print()
                console.print(error_panel)
                console.print()

                # Log full traceback for debugging (only in verbose mode if available)
                traceback.print_exc()

                raise RuntimeError(f"OAuth authentication failed: {e!s}") from e

        # Prepare headers with authentication for basic HTTP
        headers = {}
        if auth_token := server_config.get("authorization_token"):
            if not auth_token.startswith("Bearer "):
                auth_token = f"Bearer {auth_token}"
            headers["Authorization"] = auth_token

        # Follow the example pattern: nested async context managers
        try:
            async with streamablehttp_client(url, headers=headers) as (
                read_stream,
                write_stream,
                _,
            ):
                client_info = Implementation(
                    name="mcp-testing-framework", version="1.0.0"
                )
                async with ClientSession(
                    read_stream, write_stream, client_info=client_info
                ) as session:
                    await asyncio.wait_for(session.initialize(), timeout=30.0)
                    yield session
        except Exception as e:
            # Convert connection errors to more user-friendly messages
            if "SSL" in str(e) or "certificate" in str(e).lower():
                raise RuntimeError(
                    f"SSL/Certificate error connecting to '{url}': {e}"
                ) from e
            elif "Connection refused" in str(e) or "ConnectError" in str(e):
                raise RuntimeError(
                    f"Cannot connect to server '{url}': Connection refused. Please verify the server is running."
                ) from e
            else:
                raise RuntimeError(
                    f"Failed to connect to MCP server '{url}': {e}"
                ) from e

    async def _recover_connection(self, server_id: str) -> None:
        """
        Recover a failed connection by recreating the session context.

        Args:
            server_id: ID of the connection to recover
        """
        connection = self.connections.get(server_id)
        if not connection:
            raise RuntimeError(f"No connection found for server {server_id}")

        # Clean up old context if it exists
        if server_id in self._active_contexts:
            try:
                await self._active_contexts[server_id].__aexit__(None, None, None)
            except Exception:
                pass  # Ignore errors during cleanup

        # Create new connection context
        try:
            context_manager = self._get_connection_context(connection.server_config)
            session = await context_manager.__aenter__()

            # Update connection with new session and context
            connection.session = session
            connection._context_stack = context_manager
            connection._is_healthy = True
            self._active_contexts[server_id] = context_manager

        except Exception as e:
            # If recovery fails, mark as unhealthy
            connection._is_healthy = False
            raise RuntimeError(
                f"Connection recovery failed for server {server_id}: {e}"
            ) from e

    async def connect_server(self, server_config: dict[str, Any]) -> str:
        """
        Connect to an MCP server and maintain persistent connection.

        Args:
            server_config: Server configuration dict with type, url, auth, etc.

        Returns:
            server_id: Unique identifier for this server connection
        """
        server_id = str(uuid.uuid4())
        self._connection_locks[server_id] = asyncio.Lock()

        try:
            # Create persistent connection context
            context_manager = self._get_connection_context(server_config)
            session = await context_manager.__aenter__()

            # Store the context for cleanup
            self._active_contexts[server_id] = context_manager

            # Discover capabilities during the initial connection
            tools = await self._discover_tools(session)
            resources = await self._discover_resources(session)
            prompts = await self._discover_prompts(session)

            # Store connection info with persistent session
            self.connections[server_id] = MCPServerConnection(
                server_id=server_id,
                session=session,  # Store persistent session
                tools=tools,
                resources=resources,
                prompts=prompts,
                server_config=server_config,
                _context_stack=context_manager,
                _is_healthy=True,
            )

            return server_id

        except Exception as e:
            # Cleanup on failure
            if server_id in self._connection_locks:
                del self._connection_locks[server_id]
            if server_id in self._active_contexts:
                try:
                    await self._active_contexts[server_id].__aexit__(None, None, None)
                except Exception:
                    pass
                del self._active_contexts[server_id]
            raise e

    async def _discover_tools(self, session: ClientSession) -> list[dict[str, Any]]:
        """Discover available tools from MCP server"""
        try:
            response = await session.list_tools()
            return (
                [tool.model_dump() for tool in response.tools]
                if hasattr(response, "tools")
                else []
            )
        except Exception:
            return []

    async def _discover_resources(self, session: ClientSession) -> list[dict[str, Any]]:
        """Discover available resources from MCP server"""
        try:
            response = await session.list_resources()
            return (
                [resource.model_dump() for resource in response.resources]
                if hasattr(response, "resources")
                else []
            )
        except Exception:
            return []

    async def _discover_prompts(self, session: ClientSession) -> list[dict[str, Any]]:
        """Discover available prompts from MCP server"""
        try:
            response = await session.list_prompts()
            return (
                [prompt.model_dump() for prompt in response.prompts]
                if hasattr(response, "prompts")
                else []
            )
        except Exception:
            return []

    async def execute_tool(
        self, server_id: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute a tool on an MCP server using persistent session.

        Args:
            server_id: ID of the server connection
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        connection = self.connections.get(server_id)
        if not connection:
            return {
                "success": False,
                "error": f"No connection found for server {server_id}",
            }

        # Use connection lock to prevent race conditions
        async with self._connection_locks[server_id]:
            # Check if connection needs recovery
            if not connection._is_healthy or not connection.session:
                try:
                    await self._recover_connection(server_id)
                    connection = self.connections[server_id]  # Get updated connection
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Connection recovery failed: {e!s}",
                    }

            try:
                # Use persistent session
                result = await connection.session.call_tool(tool_name, arguments)

                # Parse result content
                if hasattr(result, "content"):
                    content = []
                    for item in result.content:
                        if hasattr(item, "text"):
                            content.append({"type": "text", "text": item.text})
                        elif hasattr(item, "resource"):
                            content.append({"type": "resource", "data": item.resource})
                        elif hasattr(item, "image"):
                            content.append({"type": "image", "data": item.image})

                    return {"success": True, "content": content}
                else:
                    return {
                        "success": True,
                        "content": [{"type": "text", "text": str(result)}],
                    }

            except Exception as e:
                # Mark connection as unhealthy for potential recovery
                connection._is_healthy = False
                return {"success": False, "error": str(e)}

    async def read_resource(self, server_id: str, resource_uri: str) -> dict[str, Any]:
        """
        Read a resource from an MCP server using persistent session.

        Args:
            server_id: ID of the server connection
            resource_uri: URI of the resource to read

        Returns:
            Resource content
        """
        connection = self.connections.get(server_id)
        if not connection:
            return {
                "success": False,
                "uri": resource_uri,
                "error": f"No connection found for server {server_id}",
            }

        # Use connection lock to prevent race conditions
        async with self._connection_locks[server_id]:
            # Check if connection needs recovery
            if not connection._is_healthy or not connection.session:
                try:
                    await self._recover_connection(server_id)
                    connection = self.connections[server_id]  # Get updated connection
                except Exception as e:
                    return {
                        "success": False,
                        "uri": resource_uri,
                        "error": f"Connection recovery failed: {e!s}",
                    }

            try:
                # Use persistent session
                result = await connection.session.read_resource(resource_uri)

                # Parse result content
                if hasattr(result, "contents"):
                    contents = []
                    for item in result.contents:
                        if hasattr(item, "text"):
                            contents.append({"type": "text", "text": item.text})
                        elif hasattr(item, "blob"):
                            contents.append({"type": "blob", "data": item.blob})

                    return {"success": True, "uri": resource_uri, "contents": contents}
                else:
                    return {
                        "success": True,
                        "uri": resource_uri,
                        "contents": [{"type": "text", "text": str(result)}],
                    }

            except Exception as e:
                # Mark connection as unhealthy for potential recovery
                connection._is_healthy = False
                return {"success": False, "uri": resource_uri, "error": str(e)}

    async def get_prompt(
        self,
        server_id: str,
        prompt_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Get a prompt from an MCP server using persistent session.

        Args:
            server_id: ID of the server connection
            prompt_name: Name of the prompt
            arguments: Optional arguments for the prompt

        Returns:
            Prompt content
        """
        connection = self.connections.get(server_id)
        if not connection:
            return {
                "success": False,
                "prompt_name": prompt_name,
                "error": f"No connection found for server {server_id}",
            }

        # Use connection lock to prevent race conditions
        async with self._connection_locks[server_id]:
            # Check if connection needs recovery
            if not connection._is_healthy or not connection.session:
                try:
                    await self._recover_connection(server_id)
                    connection = self.connections[server_id]  # Get updated connection
                except Exception as e:
                    return {
                        "success": False,
                        "prompt_name": prompt_name,
                        "error": f"Connection recovery failed: {e!s}",
                    }

            try:
                # Use persistent session
                result = await connection.session.get_prompt(
                    prompt_name, arguments or {}
                )

                # Parse result messages
                if hasattr(result, "messages"):
                    messages = []
                    for msg in result.messages:
                        message = {"role": msg.role}
                        if hasattr(msg, "content"):
                            if isinstance(msg.content, str):
                                message["content"] = msg.content
                            else:
                                # Handle structured content
                                message["content"] = str(msg.content)
                        messages.append(message)

                    return {
                        "success": True,
                        "prompt_name": prompt_name,
                        "messages": messages,
                    }
                else:
                    return {
                        "success": True,
                        "prompt_name": prompt_name,
                        "messages": [{"role": "user", "content": str(result)}],
                    }

            except Exception as e:
                # Mark connection as unhealthy for potential recovery
                connection._is_healthy = False
                return {"success": False, "prompt_name": prompt_name, "error": str(e)}

    async def get_tools_for_llm(self, server_ids: list[str]) -> list[dict[str, Any]]:
        """
        Get tool definitions formatted for LLM providers.

        Args:
            server_ids: List of server IDs to get tools from

        Returns:
            Combined list of tool definitions for LLM
        """
        tools = []
        for server_id in server_ids:
            connection = self.connections.get(server_id)
            if connection:
                # Add server_id to each tool for routing
                for tool in connection.tools:
                    tool_with_server = tool.copy()
                    tool_with_server["_mcp_server_id"] = server_id
                    tools.append(tool_with_server)
        return tools

    async def get_resources_for_llm(
        self, server_ids: list[str]
    ) -> list[dict[str, Any]]:
        """
        Get resource definitions formatted for LLM providers.

        Args:
            server_ids: List of server IDs to get resources from

        Returns:
            Combined list of resource definitions for LLM
        """
        resources = []
        for server_id in server_ids:
            connection = self.connections.get(server_id)
            if connection:
                # Add server_id to each resource for routing
                for resource in connection.resources:
                    resource_with_server = resource.copy()
                    resource_with_server["_mcp_server_id"] = server_id
                    resources.append(resource_with_server)
        return resources

    async def get_prompts_for_llm(self, server_ids: list[str]) -> list[dict[str, Any]]:
        """
        Get prompt definitions formatted for LLM providers.

        Args:
            server_ids: List of server IDs to get prompts from

        Returns:
            Combined list of prompt definitions for LLM
        """
        prompts = []
        for server_id in server_ids:
            connection = self.connections.get(server_id)
            if connection:
                # Add server_id to each prompt for routing
                for prompt in connection.prompts:
                    prompt_with_server = prompt.copy()
                    prompt_with_server["_mcp_server_id"] = server_id
                    prompts.append(prompt_with_server)
        return prompts

    async def disconnect_server(self, server_id: str):
        """
        Disconnect from an MCP server and clean up persistent connection.
        """
        if server_id in self.connections:
            # Clean up active context if it exists
            if server_id in self._active_contexts:
                try:
                    await self._active_contexts[server_id].__aexit__(None, None, None)
                except Exception as e:
                    print(
                        f"Warning: Error closing connection context for {server_id}: {e}"
                    )
                del self._active_contexts[server_id]

            # Clean up connection lock
            if server_id in self._connection_locks:
                del self._connection_locks[server_id]

            del self.connections[server_id]

    async def disconnect_all(self):
        """Disconnect from all MCP servers and clean up persistent connections"""
        # Clean up all active contexts
        for server_id, context_manager in list(self._active_contexts.items()):
            try:
                await context_manager.__aexit__(None, None, None)
            except Exception as e:
                print(f"Warning: Error closing connection context for {server_id}: {e}")

        # Clear all registries
        self._active_contexts.clear()
        self._connection_locks.clear()
        self.connections.clear()

    def force_disconnect_all(self):
        """Force disconnect from all MCP servers without awaiting cleanup"""
        # Clear all registries immediately without awaiting context cleanup
        # This is used when async cleanup isn't possible (e.g., in sync cleanup methods)
        self._active_contexts.clear()
        self._connection_locks.clear()
        self.connections.clear()
