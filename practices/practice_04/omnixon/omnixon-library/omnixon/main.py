import asyncio
import contextlib
import json
import httpx
from urllib.parse import quote
from typing import AsyncIterator, List, Optional, Sequence, Union

from .schemes import (
    MessageResponse,
    TraceStep,
    MessageRequest,
    User,
    UserCreate,
    UserUpdate,
    Message,
    Agent,
    AgentConfigInput,
    AgentCreate,
    AgentConnection,
    AgentConnectionCreate,
    AgentConnectionUpdate,
    AgentVersion,
    Attachment,
    AgentUpdate,
    DailyUsage,
    MonthlyUsage,
    NewToken,
    Role,
    Token,
    TokenCreate,
    TokenUpdate,
    RAG,
    RAGCreate,
    RAGUpdate,
    Memory,
    MemoryCreate,
    MemoryUpdate,
    Model,
    Interrupted,
    Chat,
    ChatCreate,
    ChatUpdate,
    RecentUser,
    ModelCreate,
    ModelUpdate,
    MCPServer,
    MCPServerCreate,
    MCPServerUpdate,
    RollbackRequest,
    VersionDiff,
)
from .exceptions import (
    NotFound,
    NoAccess,
    Conflict,
    InvalidRequest,
    UpstreamError,
    ConnectionError as UnlinkConnectionError,
    StreamError,
)


DEFAULT_TIMEOUT = 5.0  # seconds; httpx's own default
LONG_TIMEOUT = 120.0  # for what waits for a model


class _Session:
    """An httpx client whose requests wait `timeout` seconds unless told otherwise."""

    def __init__(self, client: httpx.AsyncClient, timeout: float) -> None:
        self._client = client
        self._timeout = timeout

    async def get(self, *args, **kwargs) -> httpx.Response:
        kwargs.setdefault("timeout", self._timeout)
        return await self._client.get(*args, **kwargs)

    async def post(self, *args, **kwargs) -> httpx.Response:
        kwargs.setdefault("timeout", self._timeout)
        return await self._client.post(*args, **kwargs)

    async def patch(self, *args, **kwargs) -> httpx.Response:
        kwargs.setdefault("timeout", self._timeout)
        return await self._client.patch(*args, **kwargs)

    async def delete(self, *args, **kwargs) -> httpx.Response:
        kwargs.setdefault("timeout", self._timeout)
        return await self._client.delete(*args, **kwargs)

    def stream(self, *args, **kwargs):
        kwargs.setdefault("timeout", self._timeout)
        return self._client.stream(*args, **kwargs)


def _q(user_id) -> str:
    """An external id as a part of a path: any character is allowed in one, `/` and `?` included."""
    return quote(str(user_id), safe="")


def _given(**values):
    """Only the values that were given, so that the models know what was set."""
    return {key: value for key, value in values.items() if value is not None}


def _detail(r: httpx.Response) -> Optional[str]:
    """The service's explanation of an error, if it gave one."""
    try:
        detail = r.json().get("detail")
    except Exception:
        return r.text[:200] or None

    if isinstance(detail, list):  # validation errors
        return "; ".join(str(item.get("msg", item)) for item in detail)
    return detail if isinstance(detail, str) else None


def _raise_for_status(r: httpx.Response) -> None:
    detail = _detail(r) if r.status_code >= 400 else None
    if r.status_code == 401 or r.status_code == 403:
        raise NoAccess(*([detail] if detail else []))
    if r.status_code == 404:
        raise NotFound(*([detail] if detail else []))
    if r.status_code == 409:
        raise Conflict(*([detail] if detail else []))
    if r.status_code == 422:
        raise InvalidRequest(*([detail] if detail else []))
    if r.status_code in (502, 504):
        raise UpstreamError(*([detail] if detail else []), status_code=r.status_code)
    r.raise_for_status()


class MessageStream:
    """An answer being generated. Iterate it to get the text chunks:

        stream = client.stream_message(None, "Hello")
        async for chunk in stream:
            print(chunk, end="")
        print(stream.user.external_id)

    `user` is set as soon as the service sends it (before the first chunk), so it is
    available even when no user_id was given and the service created a new user.
    A stream can be iterated once. Raises StreamError if the service fails midway.
    If the answer is cut off (`Client.interrupt`, or a newer request of the same user), the
    iteration just ends and `.interrupted` is True.
    """

    def __init__(self, client: "Client", data: MessageRequest) -> None:
        self._client = client
        self._data = data
        self.user: Optional[User] = None
        # True when the answer was cut off (interrupt(), or a new request of the same user): the text so far is in the history
        self.interrupted = False
        # steps of the chain of calls, as they arrive (only with trace=True)
        self.trace: List[TraceStep] = []

    def __aiter__(self) -> AsyncIterator[str]:
        return self._chunks()

    async def _chunks(self) -> AsyncIterator[str]:
        client = self._client
        async with client._session(timeout=LONG_TIMEOUT) as http:
            async with http.stream(
                "POST",
                f"{client.base_url}request-stream",
                json=self._data.model_dump(),
            ) as r:
                if r.status_code >= 400:
                    await r.aread()
                _raise_for_status(r)

                event = "message"
                async for line in r.aiter_lines():
                    if line.startswith("event:"):
                        event = line[len("event:") :].strip()
                    elif line.startswith("data:"):
                        payload = json.loads(line[len("data:") :].strip())
                        if event == "error":
                            raise StreamError(payload.get("detail", "Streaming failed"))
                        elif event in ("user", "done", "interrupted"):
                            self.user = User(**payload)
                            self.interrupted = event == "interrupted"
                        elif event == "trace":
                            self.trace.append(TraceStep(**payload))
                        elif event == "message":
                            yield payload
                    elif line == "":
                        event = "message"


class Client:
    token: str
    base_url: str
    headers: dict

    def __init__(
        self, token: str, base_url: str, act_as_agent: Optional[int] = None
    ) -> None:
        """`act_as_agent`: an admin or owner token may work as another agent (its users, its
        knowledge, its answers). What is spent is still written on your own token."""
        self.token = token
        self.act_as_agent = act_as_agent
        _base = base_url.rstrip("/")
        self.base_url = f"{_base}/api/v1/"
        self.admin_url = f"{_base}/api/v1/admin/"

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        if act_as_agent is not None:
            self.headers["X-Act-As-Agent"] = str(act_as_agent)

        self._http: Optional[httpx.AsyncClient] = None
        self.check_connection()

    async def __aenter__(self) -> "Client":
        """`async with Client(...) as client:` keeps one connection pool for all calls
        (faster for many calls); without it every call opens its own connection."""
        if self._http is None:
            self._http = httpx.AsyncClient(headers=self.headers)
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the shared connection pool, if there is one (calls still work, each on
        a connection of its own)."""
        http, self._http = self._http, None
        if http is not None:
            await http.aclose()

    @contextlib.asynccontextmanager
    async def _session(self, timeout: float = DEFAULT_TIMEOUT):
        if self._http is not None:
            yield _Session(self._http, timeout)
            return
        async with httpx.AsyncClient(headers=self.headers) as http:
            yield _Session(http, timeout)

    def check_connection(self) -> None:
        with httpx.Client(headers=self.headers) as client:
            try:
                r = client.get(self.base_url)
                if r.status_code == 401 or r.status_code == 403:
                    raise NoAccess()
                r.raise_for_status()
            except httpx.HTTPError as e:
                raise UnlinkConnectionError(
                    f"Connection error, check your base url: {e}"
                )

    async def ready(self) -> bool:
        """Does the service answer and is its database ready? (GET /readyz, no token)"""
        root = self.base_url[: -len("api/v1/")]
        try:
            async with httpx.AsyncClient() as http:
                r = await http.get(f"{root}readyz", timeout=DEFAULT_TIMEOUT)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def send_message(
        self,
        user_id: Optional[str],
        message: str,
        retries: int = 3,
        save_message: bool = True,
        use_memo: bool = True,
        attachments: Optional[Sequence[Union[Attachment, dict]]] = None,
        trace: bool = False,
        chat_id: Optional[int] = None,
    ) -> MessageResponse:
        """Send a message and get the answer.

        user_id: the user's external id; None or "" makes the service create a new
            user, which is returned as `response.user`.
        save_message: store this exchange in the user's history.
        use_memo: give the model the user's previous messages.
        attachments: files for the model (images, PDFs, audio, ...), see Attachment.
            The model must be able to handle them.
        trace: also get the chain of calls behind the answer in `response.trace`
            (each call to the model and each tool it called).
        chat_id: write in this chat of the user (`create_chat`; `NotFound` when it is not
            the user's). None: the user's default chat, which is where clients that know
            nothing about chats always are. `response.chat_id` says where it was written.
        """
        data = self._message_request(
            user_id, message, save_message, use_memo, attachments, trace, chat_id
        )
        for attempt in range(retries):
            try:
                async with self._session(timeout=LONG_TIMEOUT) as client:
                    r = await client.post(
                        f"{self.base_url}request",
                        json=data.model_dump(),
                    )
                    _raise_for_status(r)
                    return MessageResponse(**r.json())
            except httpx.ReadError:
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(1)

    def stream_message(
        self,
        user_id: Optional[str],
        message: str,
        save_message: bool = True,
        use_memo: bool = True,
        attachments: Optional[Sequence[Union[Attachment, dict]]] = None,
        trace: bool = False,
        chat_id: Optional[int] = None,
    ) -> MessageStream:
        """Like send_message, but the answer arrives in chunks while it is generated.

        Returns a MessageStream: iterate it for the chunks, then read `.user`. With
        `trace=True` the steps of the chain of calls collect in `.trace` while it runs.
        Not retried, since a retry would restart a partially delivered answer.
        """
        return MessageStream(
            self,
            self._message_request(
                user_id, message, save_message, use_memo, attachments, trace, chat_id
            ),
        )

    async def send_message_stream(
        self,
        user_id: Optional[str],
        message: str,
        save_message: bool = True,
        use_memo: bool = True,
        attachments: Optional[Sequence[Union[Attachment, dict]]] = None,
        trace: bool = False,
        chat_id: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Yield the answer's text chunks (see stream_message for the user object)."""
        async for chunk in self.stream_message(
            user_id, message, save_message, use_memo, attachments, trace, chat_id
        ):
            yield chunk

    @staticmethod
    def _message_request(
        user_id: Optional[str],
        message: str,
        save_message: bool,
        use_memo: bool,
        attachments: Optional[Sequence[Union[Attachment, dict]]] = None,
        trace: bool = False,
        chat_id: Optional[int] = None,
    ) -> MessageRequest:
        return MessageRequest(
            user_id=None if user_id is None else str(user_id),
            request=message,
            chat_id=chat_id,
            save_message=save_message,
            use_memo=use_memo,
            attachments=list(attachments or []),
            trace=trace,
        )

    # Users

    async def create_user(self, external_id: str) -> User:
        data = UserCreate(external_id=str(external_id))
        async with self._session() as client:
            r = await client.post(
                f"{self.base_url}users",
                json=data.model_dump(),
            )
            _raise_for_status(r)
            return User(**r.json())

    async def get_user(self, user_id: str) -> User:
        async with self._session() as client:
            r = await client.get(f"{self.base_url}users/{_q(user_id)}")
            _raise_for_status(r)
            return User(**r.json())

    async def search_users(self, query: str, limit: int = 10) -> List[User]:
        """The users of your agent whose external id starts with `query` (at least 3
        characters, `InvalidRequest` otherwise: the service has no list of all users),
        sorted by id, at most `limit` (1-50). For suggestions while someone types."""
        async with self._session() as client:
            r = await client.get(
                f"{self.base_url}users", params={"query": query, "limit": limit}
            )
            _raise_for_status(r)
            return [User(**u) for u in r.json()]

    async def get_recent_users(self, limit: int = 20) -> List[RecentUser]:
        """The users of your agent that wrote lately, latest first (1-100): those with messages that
        are still kept (the service forgets messages after `MESSAGE_TTL_DAYS`, 7 by default). Not a list of
        all users; use `search_users` for the others."""
        async with self._session() as client:
            r = await client.get(f"{self.base_url}users/recent", params={"limit": limit})
            _raise_for_status(r)
            return [RecentUser(**u) for u in r.json()]

    async def update_user(
        self,
        user_id: str,
        external_id: Optional[str] = None,
    ) -> User:
        data = UserUpdate(external_id=external_id)
        async with self._session() as client:
            r = await client.patch(
                f"{self.base_url}users/{_q(user_id)}",
                json=data.model_dump(),
            )
            _raise_for_status(r)
            return User(**r.json())

    async def delete_user(self, user_id: str) -> User:
        async with self._session() as client:
            r = await client.delete(f"{self.base_url}users/{_q(user_id)}")
            _raise_for_status(r)
            return User(**r.json())

    async def interrupt(self, user_id: str) -> Interrupted:
        """Stop the answer that is being streamed to this user (with the agent of the token).

        The stream ends (`MessageStream.interrupted` is True), what was said so far goes to the
        history marked `interrupted` and to the memory; the returned `text` is that part. Without
        a running stream `interrupted` is False and nothing is written. A new request of the same
        user cuts a running stream by itself. Only streams of the process that gets the call can be reached.
        """
        async with self._session() as client:
            r = await client.post(f"{self.base_url}users/{_q(user_id)}/interrupt")
            _raise_for_status(r)
            return Interrupted(**r.json())

    # History

    async def get_history(self, user_id: str) -> List[Message]:
        """The messages of the user's default chat (see `get_chat_history` for the others)."""
        async with self._session() as client:
            r = await client.get(f"{self.base_url}users/{_q(user_id)}/history")
            _raise_for_status(r)
            return [Message(**m) for m in r.json()]

    async def clear_history(self, user_id: str) -> None:
        async with self._session() as client:
            r = await client.delete(f"{self.base_url}users/{_q(user_id)}/history")
            _raise_for_status(r)

    # Chats: the conversations of a user, each its own thread of messages

    async def get_chats(self, user_id: str) -> List[Chat]:
        """The user's chats, the latest first. A user who has not written has none."""
        async with self._session() as client:
            r = await client.get(f"{self.base_url}users/{_q(user_id)}/chats")
            _raise_for_status(r)
            return [Chat(**c) for c in r.json()]

    async def create_chat(self, user_id: str, title: Optional[str] = None) -> Chat:
        """Start a chat. Without a title it is named after the first message written in it."""
        data = ChatCreate(title=title)
        async with self._session() as client:
            r = await client.post(
                f"{self.base_url}users/{_q(user_id)}/chats", json=data.model_dump()
            )
            _raise_for_status(r)
            return Chat(**r.json())

    async def get_chat(self, user_id: str, chat_id: int) -> Chat:
        async with self._session() as client:
            r = await client.get(f"{self.base_url}users/{_q(user_id)}/chats/{chat_id}")
            _raise_for_status(r)
            return Chat(**r.json())

    async def rename_chat(self, user_id: str, chat_id: int, title: str) -> Chat:
        data = ChatUpdate(title=title)
        async with self._session() as client:
            r = await client.patch(
                f"{self.base_url}users/{_q(user_id)}/chats/{chat_id}", json=data.model_dump()
            )
            _raise_for_status(r)
            return Chat(**r.json())

    async def delete_chat(self, user_id: str, chat_id: int) -> Chat:
        """The chat and its messages. The default chat can go too: it is made again when a
        request without `chat_id` needs it."""
        async with self._session() as client:
            r = await client.delete(f"{self.base_url}users/{_q(user_id)}/chats/{chat_id}")
            _raise_for_status(r)
            return Chat(**r.json())

    async def get_chat_history(self, user_id: str, chat_id: int) -> List[Message]:
        async with self._session() as client:
            r = await client.get(f"{self.base_url}users/{_q(user_id)}/chats/{chat_id}/history")
            _raise_for_status(r)
            return [Message(**m) for m in r.json()]

    async def clear_chat_history(self, user_id: str, chat_id: int) -> None:
        """Empty the chat; it stays."""
        async with self._session() as client:
            r = await client.delete(f"{self.base_url}users/{_q(user_id)}/chats/{chat_id}/history")
            _raise_for_status(r)

    # Admin API
    # Agents

    async def get_agents(self) -> List[Agent]:
        async with self._session() as client:
            r = await client.get(f"{self.admin_url}agents")
            _raise_for_status(r)
            return [Agent(**a) for a in r.json()]

    async def create_agent(
        self,
        name: str,
        prompt: str,
        model_id: int,
        config: Optional[Union[dict, AgentConfigInput]] = None,
        comment: Optional[str] = None,
    ) -> Agent:
        """name: required, shown everywhere instead of the id.
        config: {"tools": [...], "message_limit": int, "memo_limit": int, "rag_limit": int,
        "auto_memory": bool}, every key optional. tools are any of "rag" and "memory"
        (default: both). comment: shown in the history of the agent."""
        data = AgentCreate(
            **_given(
                name=name,
                prompt=prompt,
                model_id=model_id,
                config=config,
                comment=comment,
            )
        )
        async with self._session() as client:
            r = await client.post(
                f"{self.admin_url}agents",
                json=data.model_dump(exclude_unset=True),
            )
            _raise_for_status(r)
            return Agent(**r.json())

    async def get_self_agent(self) -> Agent:
        """The agent of the token (or the one acted as). Works with any role."""
        async with self._session() as client:
            r = await client.get(f"{self.base_url}agents/self")
            _raise_for_status(r)
            return Agent(**r.json())

    async def get_agent(self, agent_id: int) -> Agent:
        async with self._session() as client:
            r = await client.get(f"{self.admin_url}agents/{agent_id}")
            _raise_for_status(r)
            return Agent(**r.json())

    async def update_agent(
        self,
        agent_id: int,
        prompt: Optional[str] = None,
        model_id: Optional[int] = None,
        config: Optional[Union[dict, AgentConfigInput]] = None,
        comment: Optional[str] = None,
        expected_version: Optional[int] = None,
        name: Optional[str] = None,
    ) -> Agent:
        """Only what is given changes. Of `config` only the given keys change, and a key
        set to None goes back to its default: update_agent(1, config={"memo_limit": None}).

        comment: shown in the history of the agent. expected_version: the number of
        the version this change is based on; if the agent has moved on, nothing
        changes and Conflict is raised."""
        data = AgentUpdate(
            **_given(
                name=name,
                prompt=prompt,
                model_id=model_id,
                config=config,
                comment=comment,
                expected_version=expected_version,
            )
        )
        async with self._session() as client:
            r = await client.patch(
                f"{self.admin_url}agents/{agent_id}",
                json=data.model_dump(exclude_unset=True),
            )
            _raise_for_status(r)
            return Agent(**r.json())

    # Agent versions

    async def get_agent_versions(self, agent_id: int) -> List[AgentVersion]:
        """The history of an agent, newest first."""
        async with self._session() as client:
            r = await client.get(f"{self.admin_url}agents/{agent_id}/versions")
            _raise_for_status(r)
            return [AgentVersion(**v) for v in r.json()]

    async def get_agent_version(self, agent_id: int, number: int) -> AgentVersion:
        async with self._session() as client:
            r = await client.get(f"{self.admin_url}agents/{agent_id}/versions/{number}")
            _raise_for_status(r)
            return AgentVersion(**r.json())

    async def diff_agent_versions(
        self, agent_id: int, number: int, to: Optional[int] = None
    ) -> VersionDiff:
        """What changed between version `number` and version `to` (default: the latest)."""
        params = {} if to is None else {"to": to}
        async with self._session() as client:
            r = await client.get(
                f"{self.admin_url}agents/{agent_id}/versions/{number}/diff",
                params=params,
            )
            _raise_for_status(r)
            return VersionDiff(**r.json())

    async def rollback_agent(
        self, agent_id: int, to: int, comment: Optional[str] = None
    ) -> AgentVersion:
        """Make the agent what version `to` was. This is recorded as a new version
        (the history is kept); the result is the agent's latest version."""
        data = RollbackRequest(**_given(to=to, comment=comment))
        async with self._session() as client:
            r = await client.post(
                f"{self.admin_url}agents/{agent_id}/rollback",
                json=data.model_dump(exclude_unset=True),
            )
            _raise_for_status(r)
            return AgentVersion(**r.json())

    async def delete_agent(self, agent_id: int) -> Agent:
        async with self._session() as client:
            r = await client.delete(f"{self.admin_url}agents/{agent_id}")
            _raise_for_status(r)
            return Agent(**r.json())

    # Models

    async def get_models(self) -> List[Model]:
        async with self._session() as client:
            r = await client.get(f"{self.admin_url}models")
            _raise_for_status(r)
            return [Model(**m) for m in r.json()]

    async def create_model(
        self,
        name: str,
        request_json: dict,
        base_url: Optional[str] = None,
        use_proxy: bool = True,
        api_token: Optional[str] = None,
    ) -> Model:
        """`base_url`: another OpenAI-compatible server (default OpenRouter); `use_proxy=False`: call it
        without the proxy of the service; `api_token`: its key (default the key of the service; never returned)."""
        data = ModelCreate(
            name=name, request_json=request_json, base_url=base_url, use_proxy=use_proxy, api_token=api_token
        )
        async with self._session() as client:
            r = await client.post(
                f"{self.admin_url}models",
                json=data.model_dump(exclude_none=True),
            )
            _raise_for_status(r)
            return Model(**r.json())

    async def get_model(self, model_id: int) -> Model:
        async with self._session() as client:
            r = await client.get(f"{self.admin_url}models/{model_id}")
            _raise_for_status(r)
            return Model(**r.json())

    async def update_model(
        self,
        model_id: int,
        request_json: Optional[dict] = None,
        name: Optional[str] = None,
        base_url: Optional[str] = None,
        use_proxy: Optional[bool] = None,
        api_token: Optional[str] = None,
    ) -> Model:
        """Only what is given changes. `base_url=""` goes back to OpenRouter, `api_token=""` to the key of the service."""
        data = ModelUpdate(
            **_given(name=name, request_json=request_json, base_url=base_url, use_proxy=use_proxy, api_token=api_token)
        )
        async with self._session() as client:
            r = await client.patch(
                f"{self.admin_url}models/{model_id}",
                json=data.model_dump(),
            )
            _raise_for_status(r)
            return Model(**r.json())

    async def delete_model(self, model_id: int) -> Model:
        async with self._session() as client:
            r = await client.delete(f"{self.admin_url}models/{model_id}")
            _raise_for_status(r)
            return Model(**r.json())

    # Connections between agents: agent1 may call agent2 (admin and owner only)

    async def get_agent_connections(self, agent_id: Optional[int] = None) -> List[AgentConnection]:
        """All connections, or with `agent_id` the ones going out of that agent."""
        params = {} if agent_id is None else {"agent_id": agent_id}
        async with self._session() as client:
            r = await client.get(f"{self.admin_url}agent-connections", params=params)
            _raise_for_status(r)
            return [AgentConnection(**c) for c in r.json()]

    async def create_agent_connection(self, agent1_id: int, agent2_id: int, description: str) -> AgentConnection:
        """Let agent1 call agent2; the description tells agent1 what agent2 is for. Conflict: the pair is there
        already, or both are one agent; NotFound: an agent is not there."""
        data = AgentConnectionCreate(agent1_id=agent1_id, agent2_id=agent2_id, description=description)
        async with self._session() as client:
            r = await client.post(f"{self.admin_url}agent-connections", json=data.model_dump())
            _raise_for_status(r)
            return AgentConnection(**r.json())

    async def get_agent_connection(self, connection_id: int) -> AgentConnection:
        async with self._session() as client:
            r = await client.get(f"{self.admin_url}agent-connections/{connection_id}")
            _raise_for_status(r)
            return AgentConnection(**r.json())

    async def update_agent_connection(self, connection_id: int, description: str) -> AgentConnection:
        data = AgentConnectionUpdate(description=description)
        async with self._session() as client:
            r = await client.patch(f"{self.admin_url}agent-connections/{connection_id}", json=data.model_dump())
            _raise_for_status(r)
            return AgentConnection(**r.json())

    async def delete_agent_connection(self, connection_id: int) -> AgentConnection:
        async with self._session() as client:
            r = await client.delete(f"{self.admin_url}agent-connections/{connection_id}")
            _raise_for_status(r)
            return AgentConnection(**r.json())

    # MCP servers

    async def get_mcp_servers(self) -> List[MCPServer]:
        async with self._session() as client:
            r = await client.get(f"{self.admin_url}mcp-servers")
            _raise_for_status(r)
            return [MCPServer(**m) for m in r.json()]

    async def create_mcp_server(
        self, name: str, config: dict, agent_id: Optional[int] = None
    ) -> MCPServer:
        """A user token's server is attached to its own agent at once. An admin may give an
        `agent_id` to attach it, or leave it out to make a server of nobody's."""
        data = MCPServerCreate(name=name, config=config, agent_id=agent_id)
        async with self._session() as client:
            r = await client.post(
                f"{self.admin_url}mcp-servers",
                json=data.model_dump(exclude_none=True),
            )
            _raise_for_status(r)
            return MCPServer(**r.json())

    async def get_mcp_server(self, mcp_server_id: int) -> MCPServer:
        async with self._session() as client:
            r = await client.get(f"{self.admin_url}mcp-servers/{mcp_server_id}")
            _raise_for_status(r)
            return MCPServer(**r.json())

    async def update_mcp_server(
        self,
        mcp_server_id: int,
        config: Optional[dict] = None,
        name: Optional[str] = None,
    ) -> MCPServer:
        data = MCPServerUpdate(**_given(name=name, config=config))
        async with self._session() as client:
            r = await client.patch(
                f"{self.admin_url}mcp-servers/{mcp_server_id}",
                json=data.model_dump(),
            )
            _raise_for_status(r)
            return MCPServer(**r.json())

    async def delete_mcp_server(self, mcp_server_id: int) -> MCPServer:
        async with self._session() as client:
            r = await client.delete(f"{self.admin_url}mcp-servers/{mcp_server_id}")
            _raise_for_status(r)
            return MCPServer(**r.json())

    async def get_agent_mcp_servers(self, agent_id: int) -> List[MCPServer]:
        async with self._session() as client:
            r = await client.get(f"{self.admin_url}agents/{agent_id}/mcp-servers")
            _raise_for_status(r)
            return [MCPServer(**m) for m in r.json()]

    async def add_agent_mcp_server(
        self, agent_id: int, mcp_server_id: int
    ) -> List[MCPServer]:
        async with self._session() as client:
            r = await client.post(
                f"{self.admin_url}agents/{agent_id}/mcp-servers/{mcp_server_id}"
            )
            _raise_for_status(r)
            return [MCPServer(**m) for m in r.json()]

    async def remove_agent_mcp_server(
        self, agent_id: int, mcp_server_id: int
    ) -> List[MCPServer]:
        async with self._session() as client:
            r = await client.delete(
                f"{self.admin_url}agents/{agent_id}/mcp-servers/{mcp_server_id}"
            )
            _raise_for_status(r)
            return [MCPServer(**m) for m in r.json()]

    # Memory (what an agent remembers about a user)

    async def get_memories(
        self,
        user_id: str,
        agent_id: Optional[int] = None,
        limit: int = 100,
        query: Optional[str] = None,
    ) -> List[Memory]:
        """Newest first, or, with `query`, what is remembered about it: found by meaning
        ("my pet" finds "the dog is called Rex"), the closest first.
        agent_id defaults to the agent of this client's token."""
        params = {"user_id": str(user_id), "limit": limit}
        if agent_id is not None:
            params["agent_id"] = agent_id
        if query:
            params["query"] = query
        async with self._session() as client:
            r = await client.get(f"{self.admin_url}memories", params=params)
            _raise_for_status(r)
            return [Memory(**m) for m in r.json()]

    async def create_memory(
        self, user_id: str, content: str, agent_id: Optional[int] = None
    ) -> Memory:
        data = MemoryCreate(user_id=str(user_id), content=content, agent_id=agent_id)
        async with self._session() as client:
            r = await client.post(
                f"{self.admin_url}memories",
                json=data.model_dump(),
            )
            _raise_for_status(r)
            return Memory(**r.json())

    async def get_memory(self, memory_id: int) -> Memory:
        async with self._session() as client:
            r = await client.get(f"{self.admin_url}memories/{memory_id}")
            _raise_for_status(r)
            return Memory(**r.json())

    async def update_memory(self, memory_id: int, content: str) -> Memory:
        data = MemoryUpdate(content=content)
        async with self._session() as client:
            r = await client.patch(
                f"{self.admin_url}memories/{memory_id}",
                json=data.model_dump(),
            )
            _raise_for_status(r)
            return Memory(**r.json())

    async def delete_memory(self, memory_id: int) -> Memory:
        async with self._session() as client:
            r = await client.delete(f"{self.admin_url}memories/{memory_id}")
            _raise_for_status(r)
            return Memory(**r.json())

    # Tokens

    async def get_self_token(self) -> Token:
        """The token this client signs in with: its role and its agent. Works with any role."""
        async with self._session() as client:
            r = await client.get(f"{self.base_url}tokens/self")
            _raise_for_status(r)
            return Token(**r.json())

    async def get_tokens(self, agent_id: Optional[int] = None) -> List[Token]:
        """The tokens of an agent. Without `agent_id`: those of your own agent, or of every
        agent for an admin or an owner."""
        params = {} if agent_id is None else {"agent_id": agent_id}
        async with self._session() as client:
            r = await client.get(f"{self.admin_url}tokens", params=params)
            _raise_for_status(r)
            return [Token(**t) for t in r.json()]

    async def create_token(
        self, name: str, role: Role, agent_id: Optional[int] = None
    ) -> NewToken:
        """Make a token of `role` for an agent (default: your own). The answer holds the secret
        in `.token`, and it is not shown again. An owner may hand out any role, an admin
        `regular` and `user`, a user the same but only for its own agent (`NoAccess` otherwise)."""
        data = TokenCreate(name=name, role=role, agent_id=agent_id)
        async with self._session() as client:
            r = await client.post(
                f"{self.admin_url}tokens", json=data.model_dump(exclude_none=True)
            )
            _raise_for_status(r)
            return NewToken(**r.json())

    async def update_token(
        self, token_id: int, name: Optional[str] = None, role: Optional[Role] = None
    ) -> Token:
        """Rename a token and/or change its role (what is not given stays). The role can be set up to
        what the caller may hand out (`NoAccess` above that); a token cannot change its own role and
        the initial token stays an owner (`Conflict`)."""
        data = TokenUpdate(**_given(name=name, role=role))
        async with self._session() as client:
            r = await client.patch(
                f"{self.admin_url}tokens/{token_id}", json=data.model_dump(exclude_none=True)
            )
            _raise_for_status(r)
            return Token(**r.json())

    async def rename_token(self, token_id: int, name: str) -> Token:
        return await self.update_token(token_id, name=name)

    async def delete_token(self, token_id: int) -> Token:
        """The token stops working at once. The token in use and the initial token cannot be
        deleted (`Conflict`)."""
        async with self._session() as client:
            r = await client.delete(f"{self.admin_url}tokens/{token_id}")
            _raise_for_status(r)
            return Token(**r.json())

    # Usage of the models (no texts are kept)

    async def get_usage(
        self,
        days: int = 30,
        token_id: Optional[int] = None,
        agent_id: Optional[int] = None,
    ) -> List[DailyUsage]:
        """Recent usage by day, token and model."""
        params = {"days": days}
        if token_id is not None:
            params["token_id"] = token_id
        if agent_id is not None:
            params["agent_id"] = agent_id
        async with self._session() as client:
            r = await client.get(f"{self.admin_url}usage", params=params)
            _raise_for_status(r)
            return [DailyUsage(**row) for row in r.json()]

    async def get_usage_monthly(
        self, token_id: Optional[int] = None, agent_id: Optional[int] = None
    ) -> List[MonthlyUsage]:
        """Older usage, folded into one row per token, month and model."""
        params = {}
        if token_id is not None:
            params["token_id"] = token_id
        if agent_id is not None:
            params["agent_id"] = agent_id
        async with self._session() as client:
            r = await client.get(f"{self.admin_url}usage/monthly", params=params)
            _raise_for_status(r)
            return [MonthlyUsage(**row) for row in r.json()]

    # RAG

    async def list_rag(
        self,
        limit: int = 1000,
        offset: int = 0,
        agent_id: Optional[int] = None,
    ) -> List[RAG]:
        """The entries of the agent in the order they were made, `limit` (<= 1000) at a time:
        page with `offset`."""
        params = {"limit": limit, "offset": offset}
        if agent_id is not None:
            params["agent_id"] = agent_id
        async with self._session() as client:
            r = await client.get(f"{self.admin_url}rag", params=params)
            _raise_for_status(r)
            return [RAG(**item) for item in r.json()]

    async def search_rag(
        self,
        query: str,
        limit: int = 10,
        include_embedding: bool = False,
        agent_id: Optional[int] = None,
    ) -> List[RAG]:
        params = {
            "query": query,
            "limit": limit,
            "include_embedding": include_embedding,
        }
        if agent_id is not None:
            params["agent_id"] = agent_id
        async with self._session() as client:
            r = await client.get(
                f"{self.admin_url}rag",
                params=params,
            )
            _raise_for_status(r)
            return [RAG(**item) for item in r.json()]

    async def create_rag(
        self,
        content: str,
        embedding_content: Optional[str] = None,
        metadata: Optional[dict] = None,
        agent_id: Optional[int] = None,
        retries: int = 3,
    ) -> RAG:
        data = RAGCreate(
            content=content, embedding_content=embedding_content, metadata=metadata
        )

        params = {}
        if agent_id is not None:
            params["agent_id"] = agent_id
        for attempt in range(retries):
            try:
                async with self._session(timeout=LONG_TIMEOUT) as client:
                    r = await client.post(
                        f"{self.admin_url}rag",
                        params=params,
                        json=data.model_dump(),
                    )
                    _raise_for_status(r)
                    return RAG(**r.json())
            except httpx.ReadError:
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(1)

    async def get_rag(
        self,
        rag_id: int,
        include_embedding: bool = False,
        agent_id: Optional[int] = None,
    ) -> RAG:
        params = {"include_embedding": include_embedding}
        if agent_id is not None:
            params["agent_id"] = agent_id
        async with self._session() as client:
            r = await client.get(
                f"{self.admin_url}rag/{rag_id}",
                params=params,
            )
            _raise_for_status(r)
            return RAG(**r.json())

    async def update_rag(
        self,
        rag_id: int,
        content: str,
        embedding_content: Optional[str] = None,
        metadata: Optional[dict] = None,
        agent_id: Optional[int] = None,
        retries: int = 3,
    ) -> RAG:
        data = RAGUpdate(
            content=content, embedding_content=embedding_content, metadata=metadata
        )
        params = {}
        if agent_id is not None:
            params["agent_id"] = agent_id
        for attempt in range(retries):
            try:
                async with self._session(timeout=LONG_TIMEOUT) as client:
                    r = await client.patch(
                        f"{self.admin_url}rag/{rag_id}",
                        params=params,
                        json=data.model_dump(),
                    )
                    _raise_for_status(r)
                    return RAG(**r.json())
            except httpx.ReadError:
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(1)

    async def delete_rag(self, rag_id: int) -> RAG:
        async with self._session() as client:
            r = await client.delete(f"{self.admin_url}rag/{rag_id}")
            _raise_for_status(r)
            return RAG(**r.json())
