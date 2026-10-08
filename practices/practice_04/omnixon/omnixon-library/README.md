# Omnixon Python Client

## Overview

This document provides instructions for the Python client used to connect to the Omnixon web service. The Omnixon service receives text requests, processes them through artificial intelligence programs, and returns text responses.

## Connection and Setup

To use the client, you must provide an access token and the base web address. Every request requires this access token, which is placed in the request headers automatically by the client.

The client verifies the connection upon creation. It returns a 403 error if the token is incorrect. It returns a connection error if the web address is incorrect.

## Client Functions

The client provides the following functions to interact with the service:

* `send_message(user_id, message, save_message=True, use_memo=True, attachments=None)`: Sends a user text request to the service and returns a generated answer. This function has a 120-second timeout.
  * `user_id` may be `None` or an empty string. The service then creates a new user for your agent and returns it as `response.user`; keep `response.user.external_id` to continue the conversation.
  * `save_message=False` does not store this exchange in the user's history.
  * `attachments` is a list of files for the model: images, PDFs, text, audio, video. Build them with `Attachment.from_file(path)`, `Attachment.from_bytes(data, "image/png")` or `Attachment.from_url(url)`. The model must be able to handle them (for images it must see); a model that cannot gives `UpstreamError`. The history keeps only a note that a file was there, never the file.
  * `use_memo=False` does not give the model the user's previous messages. The agent's memory (see below) is not affected: it is controlled by the agent's `config`.
* `send_message_stream(user_id, message, save_message=True, use_memo=True, attachments=None)`: Like `send_message`, but an asynchronous generator that yields the answer in text chunks while it is being generated (`async for chunk in client.send_message_stream(...)`). It raises `StreamError` if the service fails midway, and is not retried automatically.
* `stream_message(user_id, message, save_message=True, use_memo=True, attachments=None)`: The same stream as an object. Iterate it for the chunks; its `user` attribute holds the user (also a newly created one) as soon as the service sends it, before the first chunk.
* `get_history(user_id)`: Returns a list of saved text records for a specific user.
* `clear_history(user_id)`: Deletes all saved text records for a specific user.
* `get_user(user_id)`: Retrieves stored information for a specific user. It returns nothing if the user is not found.
* `create_user(user_id)`: Adds a new user to the database.
* `update_user(user_id, new_user_id)`: Modifies existing information for a user, such as their identification number.
* `delete_user(user_id)`: Removes a user from the database.

Administrative functions (admin token required):

* Chats: a user has several conversations, each its own thread of messages (what the agent remembers about the user is shared). `get_chats(user_id)` (the latest first), `create_chat(user_id, title=None)` (no title: named after the first message), `get_chat`, `rename_chat(user_id, chat_id, title)`, `delete_chat` (with its messages), `get_chat_history(user_id, chat_id)`, `clear_chat_history`. `send_message`, `stream_message` and `send_message_stream` take `chat_id=`; `MessageResponse.chat_id` says where it was written. Without `chat_id` a message goes to the user's default chat, so code that knows nothing about chats works as before; `get_history` / `clear_history` are that chat's.
* Interrupting: `interrupt(user_id)` stops the answer that is being streamed to that user and returns `Interrupted(interrupted, text)`. The stream ends cleanly (`MessageStream.interrupted` is `True`), what had been said goes to the history (marked `interrupted`) and the memory. A new request of the same user does the same by itself. Streams can only be reached in the service process that runs them.
* Agents: `get_agents()`, `create_agent(name, prompt, model_id, config=None, comment=None)`, `get_self_agent()`, `get_agent(agent_id)`, `update_agent(agent_id, prompt, model_id, config, comment, expected_version, name=None)`, `delete_agent(agent_id)`.
* Models: `get_models()`, `create_model(name, request_json, base_url=None, use_proxy=True, api_token=None)`, `get_model(model_id)`, `update_model(model_id, request_json=None, name=None, base_url=None, use_proxy=None, api_token=None)`, `delete_model(model_id)`. `base_url` points a model at another OpenAI-compatible server (default: OpenRouter), `use_proxy=False` calls it without the service's proxy, `api_token` is the key for that server (default: the key of the service; it is never returned, `Model.has_api_token` says whether there is one; `""` in `update_model` clears `base_url` / `api_token`). A model is an OpenRouter request body that must contain a `"model"` name, for example `{"model": "openai/gpt-4o-mini", "provider": {"order": ["openai"]}}`.
* MCP servers: `get_mcp_servers()`, `create_mcp_server(name, config, agent_id=None)`, `get_mcp_server(id)`, `update_mcp_server(id, config=None, name=None)`, `delete_mcp_server(id)`. The config needs a `"url"` and an optional `"transport"` (`"streamable_http"` by default, or `"sse"`).
* Agent config: an agent has a `config` dictionary with its settings, all keys optional: `tools` (built-in tools, any of `"rag"` for knowledge base search and `"memory"` so the model can remember facts about a user; the default is `["rag", "memory"]`, an empty list gives no built-in tools), `message_limit` (how many of the latest messages the model gets) and `memo_limit` (how many memories it sees at once), `rag_limit` (how many knowledge base entries one search returns, 1 to 100, default 8) and `auto_memory` (on unless set to `False`: after every saved exchange the model is asked, in the background, what is worth remembering about the user). A limit that is not set uses the service default. `update_agent` changes only the given keys; a key set to `None` goes back to its default, for example `update_agent(1, config={"memo_limit": None})`. Unknown keys, unknown tools and bad limits raise `InvalidRequest`.
* Agent versions: every change of an agent (prompt, model, config, MCP servers, even an edit of the model or MCP server record it uses) is a numbered version. `get_agent_versions(agent_id)` (newest first), `get_agent_version(agent_id, number)`, `diff_agent_versions(agent_id, number, to=None)` (what changed, `to` defaults to the latest) and `rollback_agent(agent_id, to, comment=None)` (the agent becomes what that version was; recorded as a new version, nothing is lost). `update_agent(..., expected_version=n)` refuses with `Conflict` if the agent has moved on since version `n`, so two people do not overwrite each other. A message knows the version that produced it (`Message.agent_version`).
* Memory: `get_memories(user_id, agent_id=None, limit=100, query=None)` (newest first; with `query` the memories about it, found by meaning, closest first), `create_memory(user_id, content, agent_id=None)`, `get_memory(memory_id)`, `update_memory(memory_id, content)`, `delete_memory(memory_id)`. Memories belong to a user and an agent (by default the agent of your unit). The model sees the newest ones in every request, the service limits how many, and can search the older ones itself.
* Connections between agents (admin and owner): `get_agent_connections(agent_id=None)` (all, or those going out of one agent), `create_agent_connection(agent1_id, agent2_id, description)`, `get_agent_connection(id)`, `update_agent_connection(id, description)`, `delete_agent_connection(id)`. A connection lets agent1 call agent2: agent1 gets the built-in tools `list_agents` (the agents it may call, with the description) and `ask_agent(agent_id, request)` (their answer as text). Each change is a version of agent1.
* MCP tools of an agent: `get_agent_mcp_servers(agent_id)`, `add_agent_mcp_server(agent_id, mcp_server_id)`, `remove_agent_mcp_server(agent_id, mcp_server_id)` give an agent access to the tools of an MCP server.
* The chain of calls: `send_message(..., trace=True)` puts the steps in `response.trace`; `stream_message(..., trace=True)` collects them in `stream.trace` while the answer arrives. A `TraceStep` is a call to the model (`kind="model"`, with `text`, tokens, `duration_ms`) or a tool the model called (`kind="tool"`, with `args`, `result` or `error`).
* Finding users: `get_recent_users(limit=20)` (who wrote lately: latest first, with `last_active` and `messages`; the window is the service's message TTL), `search_users(query, limit=10)` returns the users of your agent whose external id starts with `query` (at least 3 characters, else `InvalidRequest`; the service has no list of all users), sorted, for suggestions while someone types.
* Tokens: `get_self_token()`, `get_tokens(agent_id=None)`, `create_token(name, role, agent_id=None)` (the answer's `.token` is the secret, shown once), `update_token(id, name=None, role=None)` (rename and/or change the role), `rename_token(id, name)`, `delete_token(id)`. Roles, least to most: `regular`, `user`, `admin`, `owner`; an owner hands out any, an admin and a user `regular` and `user` (a user only for its own agent). A token is bound to an **agent**; there are no units any more.
* Usage of the models (no texts): `get_usage(days=30, token_id=None, agent_id=None)` by day, token and model; `get_usage_monthly(...)` for what is older (folded by month).
* Knowledge base: `search_rag()`, `list_rag()`, `create_rag()`, `get_rag()`, `update_rag()`, `delete_rag()`.

## Data Structures

The client receives data organized into the following structures:

* **Names**: agents, models, MCP servers and tokens have a required `name` on create (a breaking change of 4.0.0) and an optional one on update. Every object read back has a non-empty `name`; old entities without one get a fallback from the service (model -> its model name, agent -> the start of its prompt or `Agent <id>`, `MCP <id>`, `Unit <id>`). `get_self_unit()` and `get_self_agent()` use the main API, so they work without admin rights.
* **Token**: `role` (`regular|user|admin|owner`), `agent_id`, `is_initial` (the token of the service's `INITIAL_API_KEY`: an owner that cannot be deleted). What each role may do is decided by the service (`NoAccess` when a call is refused). An admin or owner may work as another agent: `Client(token, url, act_as_agent=7)` sends `X-Act-As-Agent` on every call (what is spent is still written on your own token).
* **User**: the system identification number, the agent's id, the external identification string and a timestamp.
* **Agent**: Contains the prompt, the `model_id` of its model, and its `config` (`tools`, `message_limit`, `memo_limit`, `rag_limit`, `auto_memory`).
* **AgentVersion**: Contains the agent, its number, a `snapshot` (prompt, model, config, MCP servers as they were), the comment, who made it and a timestamp.
* **Attachment**: A file for the model: `url` or base64 `data`, with `media_type` and an optional `name`.
* **Memory**: Contains the identification number, the user and agent it belongs to, the remembered text and a timestamp.
* **Model**: Contains the identification number and the `request_json` sent to the model provider.
* **MCPServer**: Contains the identification number and the connection `config`.
* **MessageResponse**: Contains the text response from the artificial intelligence and the user information.
* **Message**: Contains the message identification number, user identification number, the text content, and a timestamp. The content is automatically converted from text format into a dictionary.

## Connections

By default every call opens its own connection. For many calls use the client as an async context manager, which keeps one connection pool:

```python
async with Client(token, base_url) as client:
    for text in texts:
        await client.send_message(user_id, text)
```

`await client.aclose()` closes the pool by hand. `await client.ready()` asks the service whether it is up and its database is ready (no token needed).

## Errors

All errors derive from `UnlinkError` and carry the explanation given by the service: `NoAccess` (401/403), `NotFound` (404), `Conflict` (409, for example deleting a model that an agent uses), `InvalidRequest` (422, rejected data), `StreamError` (a streamed answer failed midway) and `UpstreamError` (HTTP 502 or 504: the model provider or an MCP server failed or timed out; a retry may help) and `ConnectionError` (the service cannot be reached).

## Development

```bash
uv sync                # create .venv (with the dev group: pytest)
uv run pytest            # unit tests and the contract test
uv build                 # build the wheel and sdist into dist/
```

`tests/test_server_contract.py` compares the models of this library with `tests/server_openapi.json`, a snapshot of the service's OpenAPI schema. After a model changes in the service, regenerate the snapshot there (`uv run python scripts/dump_openapi.py <path to this file>`) and adapt the library until the tests pass.

