from mcp.server.mcpserver import MCPServer

server = MCPServer(name="graph-stats")


def _build_clusters(tasks: list[dict]) -> list[set[int]]:
    # union-find по общим тегам
    parent = {t["id"]: t["id"] for t in tasks}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i, a in enumerate(tasks):
        for b in tasks[i + 1:]:
            if set(a["tags"]) & set(b["tags"]):
                union(a["id"], b["id"])

    groups: dict[int, set[int]] = {}
    for t in tasks:
        root = find(t["id"])
        groups.setdefault(root, set()).add(t["id"])
    return list(groups.values())


@server.tool()
def graph_stats(tasks: list[dict]) -> dict:
    """Статистика графа задач по тегам: число узлов/рёбер/кластеров, самый частый тег, изолированные задачи.

    tasks: список объектов {"id": int, "title": str, "tags": [str, ...]}.
    """
    try:
        if not tasks:
            raise ValueError("empty tasks list, nothing to analyze")

        for t in tasks:
            if not isinstance(t.get("title"), str):
                raise ValueError(f"task {t.get('id')!r}: title must be a string")
            tags = t.get("tags")
            if not isinstance(tags, list) or len(tags) == 0:
                raise ValueError(f"task {t.get('id')!r}: tags must be a non-empty list")

        nodes = len(tasks)

        edges = 0
        for i, a in enumerate(tasks):
            for b in tasks[i + 1:]:
                if set(a["tags"]) & set(b["tags"]):
                    edges += 1

        clusters = _build_clusters(tasks)

        tag_counts: dict[str, int] = {}
        for t in tasks:
            for tag in t["tags"]:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        most_common_tag = None
        if tag_counts:
            max_count = max(tag_counts.values())
            candidates = sorted(tag for tag, c in tag_counts.items() if c == max_count)
            most_common_tag = candidates[0]

        isolated_tasks = [list(c)[0] for c in clusters if len(c) == 1]

        return {
            "nodes": nodes,
            "edges": edges,
            "clusters": len(clusters),
            "largest_cluster_size": max((len(c) for c in clusters), default=0),
            "most_common_tag": most_common_tag,
            "isolated_tasks": isolated_tasks,
        }
    except Exception as exc:
        return {"error": str(exc)}


if __name__ == "__main__":
    server.run()  # transport по умолчанию "stdio"
