import asyncio
import sys
from omnixon import Client
from omnixon.exceptions import NotFound
from config import BASE_URL, TOKEN


async def run_smoke_test():
    client = Client(TOKEN, BASE_URL)
    test_user_id = "smoke_test_user_777"

    print("Starting omnixon library test")

    try:
        print("[ ] Creating user...")
        user = await client.create_user(test_user_id)
        print(f"[+] Success. Internal ID: {user.id}")

        print("[ ] Sending message...")
        msg = await client.send_message(test_user_id, "Test hello!")
        print(f"[+] Success. Server response: {msg.response}")

        print("[ ] Getting history...")
        history = await client.get_history(test_user_id)
        assert len(history) > 0
        print(f"[+] Success. Messages found: {len(history)}")

        print("[ ] Sending without user_id (service creates a user)...")
        created = await client.send_message(None, "Say pong.", use_memo=False)
        assert created.user.external_id and created.response.strip()
        await client.delete_user(created.user.external_id)
        print(f"[+] Success. New user: {created.user.external_id}")

        print("[ ] Sending with save_message=False...")
        before = len(await client.get_history(test_user_id))
        await client.send_message(test_user_id, "Say pong.", save_message=False)
        assert len(await client.get_history(test_user_id)) == before
        print("[+] Success. History unchanged.")

        print("[ ] Streaming a message...")
        chunks = [c async for c in client.send_message_stream(test_user_id, "Say pong.")]
        assert chunks and "".join(chunks).strip()
        print(f"[+] Success. Streamed {len(chunks)} chunks: {''.join(chunks)!r}")

        print("[ ] Renaming user (external_id)...")
        updated = await client.update_user(test_user_id, "ext_ref_1")
        assert updated.external_id == "ext_ref_1"

        test_user_id = updated.external_id
        print(f"[+] Success. New external_id: {updated.external_id}")

        print("[ ] Memory (admin)...")
        memory = await client.create_memory(test_user_id, "Likes smoke tests.")
        assert memory.content in [m.content for m in await client.get_memories(test_user_id)]
        await client.update_memory(memory.id, "Likes unit tests.")
        await client.delete_memory(memory.id)
        print("[+] Success. Memory created, updated and deleted.")

        print("[ ] Creating an MCP server and attaching it to the agent...")
        agent = await client.get_self_agent()
        mcp_server = await client.create_mcp_server({"url": "http://mcp-calculator:9100/mcp"})
        attached = await client.add_agent_mcp_server(agent.id, mcp_server.id)
        assert mcp_server.id in [m.id for m in attached]
        detached = await client.remove_agent_mcp_server(agent.id, mcp_server.id)
        assert mcp_server.id not in [m.id for m in detached]
        await client.delete_mcp_server(mcp_server.id)
        print("[+] Success. MCP server attached, detached and deleted.")

        print("[ ] Clearing message history...")
        await client.clear_history(test_user_id)
        empty_history = await client.get_history(test_user_id)
        assert len(empty_history) == 0
        print("[+] Success. History is empty.")

        print("[ ] Deleting user...")
        deleted = await client.delete_user(test_user_id)
        assert deleted.id == user.id
        assert deleted.external_id == updated.external_id
        print(f"[+] Success. User {deleted.id} deleted.")

        print("[ ] Checking user existence...")
        try:
            user = await client.get_user(test_user_id)
        except NotFound:
            print("[+] Success. User not found as expected.")
            print("\n[!] All tests passed successfully.")
            sys.exit(0)
        sys.exit(1)

    except Exception as e:
        print(f"\n[!] Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
