"""
Dynamic ARI client that generates methods from Swagger/OpenAPI specification.
Pure asyncio implementation without anyio dependencies.
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
from urllib.parse import urljoin

import aiohttp
from loguru import logger


class SwaggerMethod:
    """Represents a Swagger API method."""

    def __init__(
        self, client: "AsyncARIClient", path: str, method: str, operation: dict
    ):
        self.client = client
        self.path = path
        self.http_method = method.upper()
        self.operation = operation
        self.operation_id = operation.get("operationId", "")
        self.parameters = operation.get("parameters", [])
        self.description = operation.get("description", "")

    def _build_path(self, **kwargs) -> str:
        """Build the actual path by substituting path parameters."""
        path = self.path

        # Replace path parameters like {channelId} with actual values
        for param in self.parameters:
            # Swagger spec uses 'paramType' not 'in'
            if param.get("paramType", param.get("in")) == "path":
                param_name = param["name"]
                if param_name in kwargs:
                    path = path.replace(f"{{{param_name}}}", str(kwargs[param_name]))

        return path

    def _build_params(self, **kwargs) -> dict:
        """Extract query parameters from kwargs."""
        params = {}

        for param in self.parameters:
            # Swagger spec uses 'paramType' not 'in'
            if param.get("paramType", param.get("in")) == "query":
                param_name = param["name"]
                if param_name in kwargs:
                    params[param_name] = kwargs[param_name]

        return params

    def _build_body(self, **kwargs) -> dict:
        """Extract body parameters from kwargs."""
        body = {}

        for param in self.parameters:
            # Swagger 1.2 uses 'paramType' = 'body' for body parameters
            if param.get("paramType", param.get("in")) == "body":
                param_name = param["name"]
                if param_name in kwargs:
                    # In Swagger 1.2, body param is usually the whole body
                    return (
                        kwargs[param_name]
                        if isinstance(kwargs[param_name], dict)
                        else {param_name: kwargs[param_name]}
                    )

        return body

    async def __call__(self, **kwargs):
        """Execute the API method."""
        path = self._build_path(**kwargs)
        params = self._build_params(**kwargs)

        # Check if there's a body parameter defined in the spec
        body_data = self._build_body(**kwargs)

        # If no body param in spec, use remaining kwargs for body (backward compat)
        if not body_data:
            # Remove path and query parameters from kwargs (leaving body params)
            # Swagger spec uses 'paramType' not 'in'
            path_param_names = {
                p["name"]
                for p in self.parameters
                if p.get("paramType", p.get("in")) == "path"
            }
            query_param_names = {
                p["name"]
                for p in self.parameters
                if p.get("paramType", p.get("in")) == "query"
            }
            body_param_names = {
                p["name"]
                for p in self.parameters
                if p.get("paramType", p.get("in")) == "body"
            }
            body_data = {
                k: v
                for k, v in kwargs.items()
                if k not in path_param_names
                and k not in query_param_names
                and k not in body_param_names
            }

        # Debug logging for externalMedia
        if "externalMedia" in path:
            logger.debug(
                f"externalMedia call - method: {self.http_method}, path: {path}, params: {params}"
            )

        if self.http_method == "GET":
            return await self.client.api_get(path, **params)
        elif self.http_method == "POST":
            return await self.client.api_post(
                path, json_data=body_data if body_data else None, **params
            )
        elif self.http_method == "PUT":
            return await self.client.api_put(
                path, json_data=body_data if body_data else None, **params
            )
        elif self.http_method == "DELETE":
            return await self.client.api_delete(path, **params)
        else:
            raise ValueError(f"Unsupported HTTP method: {self.http_method}")


class ResourceAPI:
    """Represents a resource API (like channels, bridges, etc.)."""

    def __init__(self, client: "AsyncARIClient", resource_name: str):
        self.client = client
        self.resource_name = resource_name
        self._methods = {}

    def add_method(self, method_name: str, swagger_method: SwaggerMethod):
        """Add a method to this resource."""
        self._methods[method_name] = swagger_method

    def __getattr__(self, name):
        """Dynamically return methods."""
        if name in self._methods:
            return self._methods[name]
        raise AttributeError(f"'{self.resource_name}' has no method '{name}'")


@dataclass
class Channel:
    """Channel model with dynamic method support."""

    id: str
    name: str = ""
    state: str = ""
    caller: Dict[str, str] = field(default_factory=dict)
    connected: Dict[str, str] = field(default_factory=dict)
    accountcode: str = ""
    dialplan: Dict[str, str] = field(default_factory=dict)
    creationtime: str = ""
    language: str = "en"

    # Store reference to client for method calls
    _client: Optional["AsyncARIClient"] = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, data: dict, client=None) -> "Channel":
        """Create Channel from API response."""
        channel = cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            state=data.get("state", ""),
            caller=data.get("caller", {}),
            connected=data.get("connected", {}),
            accountcode=data.get("accountcode", ""),
            dialplan=data.get("dialplan", {}),
            creationtime=data.get("creationtime", ""),
            language=data.get("language", "en"),
            _client=client,
        )
        return channel

    async def continueInDialplan(
        self,
        context: str = None,
        extension: str = None,
        priority: int = None,
        label: str = None,
    ):
        """Continue channel in dialplan."""
        if not self._client:
            raise RuntimeError("Channel not associated with a client")

        params = {"channelId": self.id}
        if context:
            params["context"] = context
        if extension:
            params["extension"] = extension
        if priority is not None:
            params["priority"] = priority
        if label:
            params["label"] = label

        # The ARI API method is named 'continueInDialplan'
        channels_api = self._client.channels
        if hasattr(channels_api, "continueInDialplan"):
            await channels_api.continueInDialplan(**params)
        else:
            # Fallback to direct API call
            await self._client.api_post(f"/channels/{self.id}/continue", **params)

    async def hangup(self, reason: str = "normal"):
        """Hangup the channel."""
        if not self._client:
            raise RuntimeError("Channel not associated with a client")
        await self._client.channels.hangup(channelId=self.id, reason=reason)

    async def answer(self):
        """Answer the channel."""
        if not self._client:
            raise RuntimeError("Channel not associated with a client")
        await self._client.channels.answer(channelId=self.id)

    async def getChannelVar(self, variable: str):
        """Get a channel variable."""
        if not self._client:
            raise RuntimeError("Channel not associated with a client")
        return await self._client.channels.getChannelVar(
            channelId=self.id, variable=variable
        )


@dataclass
class Bridge:
    """Bridge model with dynamic method support."""

    id: str
    technology: str = ""
    bridge_type: str = ""
    bridge_class: str = ""
    creator: str = ""
    name: str = ""
    channels: List[str] = field(default_factory=list)

    _client: Optional["AsyncARIClient"] = field(default=None, repr=False)

    @classmethod
    def from_dict(cls, data: dict, client=None) -> "Bridge":
        """Create Bridge from API response."""
        return cls(
            id=data.get("id", ""),
            technology=data.get("technology", ""),
            bridge_type=data.get("bridge_type", ""),
            bridge_class=data.get("bridge_class", ""),
            creator=data.get("creator", ""),
            name=data.get("name", ""),
            channels=data.get("channels", []),
            _client=client,
        )

    async def addChannel(self, channel: str):
        """Add channel to bridge."""
        if not self._client:
            raise RuntimeError("Bridge not associated with a client")
        await self._client.bridges.addChannel(bridgeId=self.id, channel=channel)

    async def removeChannel(self, channel: str):
        """Remove channel from bridge."""
        if not self._client:
            raise RuntimeError("Bridge not associated with a client")
        await self._client.bridges.removeChannel(bridgeId=self.id, channel=channel)

    async def destroy(self):
        """Destroy the bridge."""
        if not self._client:
            raise RuntimeError("Bridge not associated with a client")
        await self._client.bridges.destroy(bridgeId=self.id)


class AsyncARIClient:
    """ARI client that dynamically generates methods from Swagger spec."""

    def __init__(self, base_url: str, username: str, password: str, app: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.app = app

        # REST API URL
        self.api_url = self.base_url.replace("ws://", "http://").replace(
            "wss://", "https://"
        )

        # WebSocket URL
        self.ws_url = (
            f"{self.base_url}/ari/events?app={app}&api_key={username}:{password}"
        )

        # Session and WebSocket
        self._session: Optional[aiohttp.ClientSession] = None
        self._websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self._running = False

        # Event handling
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

        # Resource APIs (will be populated from Swagger)
        self.channels: Optional[ResourceAPI] = None
        self.bridges: Optional[ResourceAPI] = None
        self.endpoints: Optional[ResourceAPI] = None
        self.recordings: Optional[ResourceAPI] = None
        self.sounds: Optional[ResourceAPI] = None
        self.playbacks: Optional[ResourceAPI] = None
        self.asterisk: Optional[ResourceAPI] = None
        self.applications: Optional[ResourceAPI] = None
        self.deviceStates: Optional[ResourceAPI] = None
        self.mailboxes: Optional[ResourceAPI] = None

        # Swagger spec cache
        self._swagger_spec: Optional[dict] = None

    async def connect(self):
        """Connect to ARI and load Swagger spec."""
        # Create HTTP session
        auth = aiohttp.BasicAuth(self.username, self.password)
        self._session = aiohttp.ClientSession(auth=auth)

        try:
            # Load Swagger spec and generate methods
            await self._load_swagger_spec()

            # Connect WebSocket
            self._websocket = await self._session.ws_connect(
                self.ws_url, heartbeat=30, autoping=True
            )
            self._running = True
            logger.info(f"Connected to ARI at {self.ws_url}")

        except Exception as e:
            await self._session.close()
            raise Exception(f"Failed to connect to ARI: {e}")

    async def _load_swagger_spec(self):
        """Load Swagger spec and generate dynamic methods."""
        spec_loaded = False
        try:
            # Get Swagger spec from ARI
            url = f"{self.api_url}/ari/api-docs/resources.json"
            async with self._session.get(url) as resp:
                resp.raise_for_status()
                resources = await resp.json()

            # Store the spec
            self._swagger_spec = resources

            # Create resource APIs
            for api_info in resources.get("apis", []):
                resource_path = api_info["path"]

                # Fix the path - remove .{format} and add proper prefix
                resource_path = resource_path.replace(".{format}", ".json")

                # Load detailed spec for this resource
                # The resource_path already contains /api-docs/, so we just need the base URL
                url = f"{self.api_url}/ari{resource_path}"
                try:
                    async with self._session.get(url) as resp:
                        resp.raise_for_status()
                        spec = await resp.json()

                    self._process_swagger_spec(spec)
                    spec_loaded = True
                except Exception as e:
                    logger.warning(f"Failed to load spec for {resource_path}: {e}")

            if spec_loaded:
                logger.info("Loaded Swagger spec and generated dynamic methods")
            else:
                raise Exception("No individual specs could be loaded")

        except Exception as e:
            logger.warning(f"Failed to load Swagger spec, using fallback methods: {e}")
            self._create_fallback_methods()

    def _process_swagger_spec(self, spec: dict):
        """Process a Swagger spec and create dynamic methods."""
        # basePath is available in spec but not currently used

        for api in spec.get("apis", []):
            path = api["path"]

            for operation in api.get("operations", []):
                self._create_method_from_operation(path, operation)

    def _create_method_from_operation(self, path: str, operation: dict):
        """Create a method from a Swagger operation."""
        # Swagger spec uses 'httpMethod' not 'method'
        method = operation.get("httpMethod", operation.get("method", "GET"))
        operation_id = operation.get("nickname", "")

        if not operation_id:
            return

        # Determine resource from path (e.g., /channels/{channelId} -> channels)
        path_parts = path.strip("/").split("/")
        if path_parts:
            resource_name = path_parts[0]

            # Create resource API if it doesn't exist
            if not hasattr(self, resource_name) or getattr(self, resource_name) is None:
                setattr(self, resource_name, ResourceAPI(self, resource_name))

            resource_api = getattr(self, resource_name)

            # Extract method name from operation ID
            # e.g., "channels_continue" -> "continue_"
            # or "channels_get" -> "get"
            method_name = operation_id
            if method_name.startswith(resource_name + "_"):
                method_name = method_name[len(resource_name) + 1 :]

            # Handle special cases
            if method_name == "continue":
                method_name = "continue_"  # Avoid Python keyword

            # Create and add the method
            swagger_method = SwaggerMethod(self, path, method, operation)
            resource_api.add_method(method_name, swagger_method)

    def _create_fallback_methods(self):
        """Create fallback methods if Swagger spec is not available."""
        # Create basic resource APIs
        self.channels = ResourceAPI(self, "channels")
        self.bridges = ResourceAPI(self, "bridges")

        # Add essential channel methods
        self.channels.add_method(
            "get",
            SwaggerMethod(
                self,
                "/channels/{channelId}",
                "GET",
                {
                    "operationId": "get",
                    "parameters": [{"name": "channelId", "in": "path"}],
                },
            ),
        )
        self.channels.add_method(
            "hangup",
            SwaggerMethod(
                self,
                "/channels/{channelId}",
                "DELETE",
                {
                    "operationId": "hangup",
                    "parameters": [
                        {"name": "channelId", "in": "path"},
                        {"name": "reason", "in": "query"},
                    ],
                },
            ),
        )
        self.channels.add_method(
            "answer",
            SwaggerMethod(
                self,
                "/channels/{channelId}/answer",
                "POST",
                {
                    "operationId": "answer",
                    "parameters": [{"name": "channelId", "in": "path"}],
                },
            ),
        )
        self.channels.add_method(
            "continueInDialplan",
            SwaggerMethod(
                self,
                "/channels/{channelId}/continue",
                "POST",
                {
                    "operationId": "continueInDialplan",
                    "parameters": [
                        {"name": "channelId", "in": "path"},
                        {"name": "context", "in": "query"},
                        {"name": "extension", "in": "query"},
                        {"name": "priority", "in": "query"},
                        {"name": "label", "in": "query"},
                    ],
                },
            ),
        )
        self.channels.add_method(
            "externalMedia",
            SwaggerMethod(
                self,
                "/channels/externalMedia",
                "POST",
                {
                    "operationId": "externalMedia",
                    "parameters": [
                        {"name": "channelId", "in": "query"},  # Add channelId parameter
                        {"name": "app", "in": "query"},
                        {"name": "external_host", "in": "query"},
                        {"name": "format", "in": "query"},
                        {"name": "encapsulation", "in": "query"},
                        {"name": "transport", "in": "query"},
                        {"name": "connection_type", "in": "query"},
                        {"name": "direction", "in": "query"},
                    ],
                },
            ),
        )
        self.channels.add_method(
            "getChannelVar",
            SwaggerMethod(
                self,
                "/channels/{channelId}/variable",
                "GET",
                {
                    "operationId": "getChannelVar",
                    "parameters": [
                        {"name": "channelId", "in": "path"},
                        {"name": "variable", "in": "query"},
                    ],
                },
            ),
        )

        # Add essential bridge methods
        self.bridges.add_method(
            "get",
            SwaggerMethod(
                self,
                "/bridges/{bridgeId}",
                "GET",
                {
                    "operationId": "get",
                    "parameters": [{"name": "bridgeId", "in": "path"}],
                },
            ),
        )
        self.bridges.add_method(
            "create",
            SwaggerMethod(
                self,
                "/bridges",
                "POST",
                {
                    "operationId": "create",
                    "parameters": [
                        {"name": "type", "in": "query"},
                        {"name": "name", "in": "query"},
                    ],
                },
            ),
        )
        self.bridges.add_method(
            "addChannel",
            SwaggerMethod(
                self,
                "/bridges/{bridgeId}/addChannel",
                "POST",
                {
                    "operationId": "addChannel",
                    "parameters": [
                        {"name": "bridgeId", "in": "path"},
                        {"name": "channel", "in": "query"},
                    ],
                },
            ),
        )
        self.bridges.add_method(
            "removeChannel",
            SwaggerMethod(
                self,
                "/bridges/{bridgeId}/removeChannel",
                "POST",
                {
                    "operationId": "removeChannel",
                    "parameters": [
                        {"name": "bridgeId", "in": "path"},
                        {"name": "channel", "in": "query"},
                    ],
                },
            ),
        )
        self.bridges.add_method(
            "destroy",
            SwaggerMethod(
                self,
                "/bridges/{bridgeId}",
                "DELETE",
                {
                    "operationId": "destroy",
                    "parameters": [{"name": "bridgeId", "in": "path"}],
                },
            ),
        )

    async def disconnect(self):
        """Disconnect from ARI."""
        self._running = False

        if self._websocket:
            await self._websocket.close()

        if self._session:
            await self._session.close()

    async def run(self):
        """Main event loop."""
        if not self._websocket:
            raise RuntimeError("Not connected")

        processor_task = asyncio.create_task(self._process_events())

        try:
            async for msg in self._websocket:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        event = json.loads(msg.data)
                        # Wrap channel/bridge objects
                        if "channel" in event and isinstance(event["channel"], dict):
                            event["channel"] = Channel.from_dict(event["channel"], self)
                        if "bridge" in event and isinstance(event["bridge"], dict):
                            event["bridge"] = Bridge.from_dict(event["bridge"], self)
                        await self._event_queue.put(event)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON: {msg.data}")

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {self._websocket.exception()}")
                    break

                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.info("WebSocket closed")
                    break

        finally:
            self._running = False
            processor_task.cancel()
            await asyncio.gather(processor_task, return_exceptions=True)

    async def _process_events(self):
        """Process events from queue."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                event_type = event.get("type")
                if event_type:
                    await self._dispatch_event(event_type, event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing event: {e}")

    async def _dispatch_event(self, event_type: str, event: dict):
        """Dispatch event to handlers."""
        handlers = self._event_handlers.get(event_type, [])
        if handlers:
            logger.debug(
                f"AsyncARIClient: Dispatching {event_type} to {len(handlers)} handlers"
            )
        for i, handler in enumerate(handlers):
            try:
                logger.debug(
                    f"  AsyncARIClient: Calling {event_type} handler {i + 1}/{len(handlers)}"
                )
                await handler(event)
            except Exception as e:
                logger.error(f"Handler {i + 1} error for {event_type}: {e}")

    def on_event(self, event_type: str, handler: Callable):
        """Register event handler."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        logger.debug(
            f"AsyncARIClient: Registering handler for {event_type}. Current count: {len(self._event_handlers.get(event_type, []))}"
        )
        self._event_handlers[event_type].append(handler)
        logger.debug(
            f"AsyncARIClient: After registration, {event_type} handler count: {len(self._event_handlers[event_type])}"
        )

    # REST API methods
    async def api_get(self, path: str, **params) -> dict:
        """GET request."""
        # Ensure path starts with /ari if not already
        if not path.startswith("/ari"):
            path = f"/ari{path}" if path.startswith("/") else f"/ari/{path}"
        url = urljoin(self.api_url, path.lstrip("/"))
        async with self._session.get(url, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()
            # Wrap known objects
            if isinstance(data, list):
                # Handle lists of channels/bridges
                if "/channels" in path:
                    return [
                        Channel.from_dict(item, self)
                        if isinstance(item, dict)
                        else item
                        for item in data
                    ]
                elif "/bridges" in path:
                    return [
                        Bridge.from_dict(item, self) if isinstance(item, dict) else item
                        for item in data
                    ]
                return data
            elif isinstance(data, dict):
                if "/channels/" in path and "id" in data:
                    return Channel.from_dict(data, self)
                elif "/bridges/" in path and "id" in data:
                    return Bridge.from_dict(data, self)
            return data

    async def api_post(self, path: str, json_data: dict = None, **params) -> dict:
        """POST request."""
        # Ensure path starts with /ari if not already
        if not path.startswith("/ari"):
            path = f"/ari{path}" if path.startswith("/") else f"/ari/{path}"
        url = urljoin(self.api_url, path.lstrip("/"))
        async with self._session.post(url, json=json_data, params=params) as resp:
            resp.raise_for_status()
            if resp.content_length and resp.content_length > 0:
                data = await resp.json()
                # Wrap known objects
                if "id" in data and "state" in data:
                    return Channel.from_dict(data, self)
                elif "id" in data and "bridge_type" in data:
                    return Bridge.from_dict(data, self)
                return data
            return {}

    async def api_put(self, path: str, json_data: dict = None, **params) -> dict:
        """PUT request."""
        # Ensure path starts with /ari if not already
        if not path.startswith("/ari"):
            path = f"/ari{path}" if path.startswith("/") else f"/ari/{path}"
        url = urljoin(self.api_url, path.lstrip("/"))
        async with self._session.put(url, json=json_data, params=params) as resp:
            resp.raise_for_status()
            if resp.content_length and resp.content_length > 0:
                return await resp.json()
            return {}

    async def api_delete(self, path: str, **params) -> dict:
        """DELETE request."""
        # Ensure path starts with /ari if not already
        if not path.startswith("/ari"):
            path = f"/ari{path}" if path.startswith("/") else f"/ari/{path}"
        url = urljoin(self.api_url, path.lstrip("/"))
        async with self._session.delete(url, params=params) as resp:
            resp.raise_for_status()
            if resp.content_length and resp.content_length > 0:
                return await resp.json()
            return {}
