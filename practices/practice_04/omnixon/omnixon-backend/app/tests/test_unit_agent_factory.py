"""unit agent factory tests: which capabilities an agent has, what it is told, what the provider is asked"""

import pytest
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel

from ai.deps import RunDeps
from ai.factory import AgentFactory
from ai.capabilities.parallel import PARALLEL_INSTRUCTIONS
from repositories.connections import ConnectionRepository
from repositories.models import McpServerRepository, ModelRepository
from services.knowledge import KnowledgeService
from services.memories import MEMORY_INSTRUCTIONS, MemoryService
from world import world


def names(capabilities):
    return [type(c).__name__ for c in capabilities]


async def tools_of(w, conversation, model):
    """The tool names the model was offered when the agent ran."""
    factory = w.get(AgentFactory)
    agent = await factory.build(conversation, await w.get(ModelRepository).get(0))
    await agent.run("hi", deps=RunDeps(conversation, w.get(MemoryService), w.get(KnowledgeService)))
    return {tool.name for tool in model.last_model_request_parameters.function_tools}


@pytest.mark.asyncio
async def test_an_agent_has_only_the_tools_its_config_names():
    model = TestModel(call_tools=[])
    async with world(model=model) as w:
        for tools, expected in (
            (["rag"], {"retrieve"}),
            (["memory"], {"remember", "recall", "forget"}),
            ([], set()),
            (["rag", "memory"], {"retrieve", "remember", "recall", "forget"}),
        ):
            agent = await w.agent("a", tools=tools)
            assert await tools_of(w, await w.conversation(agent=agent), model) == expected


@pytest.mark.asyncio
async def test_capabilities_come_in_a_fixed_order_with_the_failure_guard_first_and_parallel_last():
    async with world(model=TestModel()) as w:
        factory = w.get(AgentFactory)
        everything = await w.agent("a", tools=["rag", "memory"])
        other = await w.agent("b")
        await w.get(ConnectionRepository).insert(everything.id, other.id, "d")
        server = await w.get(McpServerRepository).insert({"url": "http://m/mcp"}, "s")
        await w.get(McpServerRepository).attach(everything.id, server.id)
        assert names(await factory.capabilities(await w.conversation(agent=everything))) == [
            "ToolFailures", "KnowledgeBase", "Memory", "AgentCalls", "McpServers", "ParallelCalls",
        ]
        nothing = await w.agent("c", tools=[])
        assert names(await factory.capabilities(await w.conversation(agent=nothing))) == ["ToolFailures"]  # no tools: nothing to call together


@pytest.mark.asyncio
async def test_parallel_off_means_no_instruction_and_the_provider_is_told_so():
    seen = []

    def respond(messages, info):
        seen.append(info)
        return ModelResponse(parts=[TextPart("ok")])

    async with world(model=FunctionModel(respond)) as w:
        factory, models = w.get(AgentFactory), w.get(ModelRepository)
        for parallel in (True, False):
            conversation = await w.conversation(agent=await w.agent(f"p{parallel}", parallel_tool_calls=parallel))
            agent = await factory.build(conversation, await models.get(0))
            await agent.run("hi", deps=RunDeps(conversation, w.get(MemoryService), w.get(KnowledgeService)))
        on, off = seen
        assert PARALLEL_INSTRUCTIONS in on.instructions and "parallel_tool_calls" not in (on.model_settings or {})
        assert PARALLEL_INSTRUCTIONS not in (off.instructions or "") and off.model_settings["parallel_tool_calls"] is False


@pytest.mark.asyncio
async def test_the_prompt_is_the_instructions_and_an_empty_prompt_leaves_only_what_the_capabilities_say():
    seen = []

    def respond(messages, info):
        seen.append(info.instructions or "")
        return ModelResponse(parts=[TextPart("ok")])

    async with world(model=FunctionModel(respond)) as w:
        factory, models = w.get(AgentFactory), w.get(ModelRepository)
        deps = lambda c: RunDeps(c, w.get(MemoryService), w.get(KnowledgeService))  # noqa: E731
        for prompt, tools in (("Be helpful.", ["memory"]), ("", ["memory"]), ("", ["rag"]), ("", [])):
            conversation = await w.conversation(agent=await w.agent("x", prompt=prompt, tools=tools))
            await (await factory.build(conversation, await models.get(0))).run("hi", deps=deps(conversation))
        assert seen[0] == f"Be helpful.\n\n{MEMORY_INSTRUCTIONS}\n\n{PARALLEL_INSTRUCTIONS}"
        assert seen[1] == f"{MEMORY_INSTRUCTIONS}\n\n{PARALLEL_INSTRUCTIONS}"
        assert seen[2] == PARALLEL_INSTRUCTIONS and seen[3] == ""  # nothing to say: no system message (an empty one is refused by some providers)


@pytest.mark.asyncio
async def test_the_model_of_the_agent_is_made_from_its_record_and_connection():
    async with world(model=TestModel()) as w:
        models = w.get(ModelRepository)
        record = await models.insert({"model": "a/b", "temperature": 0}, base_url="http://llm/v1", use_proxy=False, api_token="own-key")
        agent = await w.agent("a")
        conversation = await w.conversation(agent=agent)
        await w.get(AgentFactory).build(conversation, record)
        request_json, connection = w.gateway.models_asked[-1]
        assert request_json == {"model": "a/b", "temperature": 0}
        assert connection == {"base_url": "http://llm/v1", "use_proxy": False, "api_token": "own-key"}
