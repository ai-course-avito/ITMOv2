"""The models of this library must match the ones of the service.

tests/server_openapi.json is a snapshot of the service's OpenAPI schema, made with
`uv run python scripts/dump_openapi.py <path>` in the omnixon repository. After a
model changes there, regenerate it, and these tests show what to change here.
"""

import json
from pathlib import Path

import pytest

import omnixon.schemes as lib

SPEC = json.loads((Path(__file__).parent / "server_openapi.json").read_text())
SCHEMAS = SPEC["components"]["schemas"]

# model name in the service (OpenAPI) -> class of this library
MODELS = [
    "Agent",
    "AgentConfig",
    "AgentVersion",
    "VersionDiff",
    "RollbackRequest",
    "Attachment",
    "Token",
    "NewToken",
    "DailyUsage",
    "MonthlyUsage",
    "User",
    "RecentUser",
    "Message",
    "Model",
    "Interrupted",
    "Chat",
    "ChatCreate",
    "ChatUpdate",
    "MCPServer",
    "Memory",
    "RAG",
    "MessageRequest",
    "MessageResponse",
    "TraceStep",
    "UserCreate",
    "UserUpdate",
    "TokenCreate",
    "TokenUpdate",
    "AgentCreate",
    "AgentUpdate",
    "ModelCreate",
    "ModelUpdate",
    "MCPServerCreate",
    "AgentConnection",
    "AgentConnectionCreate",
    "AgentConnectionUpdate",
    "MCPServerUpdate",
    "MemoryCreate",
    "MemoryUpdate",
    "RAGCreate",
    "RAGUpdate",
]

# Where the library is deliberately more precise than the OpenAPI schema
KNOWN_DIFFERENCES = {
    # the service serializes the config with a custom serializer, so OpenAPI only
    # says "object"; the library parses it into AgentConfig, which has the same keys
    ("Agent", "config"),
    # the service takes the config of a request as AgentConfigInput
    ("AgentCreate", "config"),
    ("AgentUpdate", "config"),
    # the service always sends it; the library defaults it so an older service still parses
    ("Token", "is_initial"),
    ("NewToken", "is_initial"),
    ("Model", "has_api_token"),
}


def kind(prop: dict) -> str:
    if "$ref" in prop:
        name = prop["$ref"].split("/")[-1]
        return "ref:" + name.replace("-Input", "").replace("-Output", "")
    if "anyOf" in prop:
        parts = sorted(kind(p) for p in prop["anyOf"] if p.get("type") != "null")
        nullable = any(p.get("type") == "null" for p in prop["anyOf"])
        return "|".join(parts) + ("?" if nullable else "")
    if prop.get("type") == "array":
        return "array[" + kind(prop.get("items", {})) + "]"
    return prop.get("type", "any")


def fields(schema: dict) -> dict:
    required = set(schema.get("required", []))
    return {
        name: (kind(prop), name in required)
        for name, prop in schema.get("properties", {}).items()
    }


def service_schema(name: str) -> dict:
    for candidate in (name, f"{name}-Output", f"{name}-Input"):
        if candidate in SCHEMAS:
            return SCHEMAS[candidate]
    raise KeyError(name)


@pytest.mark.parametrize("name", MODELS)
def test_model_has_the_fields_of_the_service(name):
    service = fields(service_schema(name))
    library = fields(getattr(lib, name).model_json_schema())

    assert set(library) == set(service), (
        f"{name}: only in the service {sorted(set(service) - set(library))}, "
        f"only in the library {sorted(set(library) - set(service))}"
    )
    for field in service:
        if (name, field) in KNOWN_DIFFERENCES:
            continue
        assert library[field] == service[field], (
            f"{name}.{field}: service {service[field]}, library {library[field]}"
        )


def test_every_service_model_is_covered_or_ignored():
    # models the library does not need: errors, input-only helpers, internals
    ignored = {"HTTPValidationError", "ValidationError", "AgentConfigInput"}
    covered = set(MODELS) | ignored
    uncovered = {
        name.replace("-Input", "").replace("-Output", "") for name in SCHEMAS
    } - covered
    assert not uncovered, f"new models in the service, add them to MODELS: {sorted(uncovered)}"


def test_agent_config_input_matches_the_service():
    service = fields(SCHEMAS["AgentConfigInput"])
    library = fields(lib.AgentConfigInput.model_json_schema())
    assert library == service
