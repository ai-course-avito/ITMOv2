"""Воспроизведение угроз T01-T16 по HTTP против своего локального стенда (127.0.0.1).

Печатает по одной строке на угрозу: подтвердилась ли проблема. Данные синтетические.
Запуск: python3 repro.py [порт]   (по умолчанию 8066)
"""

import json
import sys
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8066
BASE = f"http://127.0.0.1:{PORT}"
SECRET = "TEST_ONLY_OPERATOR_SECRET"


def call(method, path, body=None, headers=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    request = Request(BASE + path, data=data, method=method,
                      headers={"Content-Type": "application/json", **(headers or {})})
    try:
        response = urlopen(request, timeout=5)
    except HTTPError as exc:
        response = exc
    with response:
        return response.status, response.read().decode()


def login(user):
    return {"X-Token": json.loads(call("POST", "/login", {"username": user, "password": f"learn-{user}"})[1])["token"]}


def execute(auth, tool, **arguments):
    return call("POST", "/assistant/execute", {"decision": {"tool": tool, "arguments": arguments}}, auth)


alice = login("alice")
results = []


def check(threat, title, confirmed, evidence):
    results.append((threat, confirmed))
    print(f"{threat} {'ПОДТВЕРЖДЕНО' if confirmed else 'не воспроизводится'}: {title} — {evidence}")


s, b = call("GET", "/admin/export", headers={"X-Role": "staff"})
check("T01", "роль из заголовка X-Role без входа", s == 200 and "TEST_BOB" in b, f"HTTP {s}")

s, b = call("GET", "/profile?id=2", headers=alice)
check("T02", "alice читает профиль bob", s == 200 and "TEST_BOB" in b, f"HTTP {s}")

s, b = call("GET", "/profile?id=" + quote("1 OR 1=1"), headers=alice)
check("T03a", "SQL через id профиля", s == 200 and b.count("TEST_") >= 2, f"HTTP {s}, строк профилей: {b.count('TEST_')}")

s, b = call("GET", "/search?q=" + quote("x' OR 1=1 --"), headers=alice)
check("T03b", "SQL через поиск", s == 200 and b.count("TEST_") >= 2, f"HTTP {s}, строк профилей: {b.count('TEST_')}")

s, b = call("GET", "/assistant/context?order_id=2", headers=alice)
check("T03c", "alice получает контекст чужого заказа", s == 200 and "lamp" in b, f"HTTP {s}")

s, b = call("GET", "/orders")
check("T04", "список всех заказов без входа", s == 200 and "lamp" in b and "chair" in b, f"HTTP {s}")

s, b = call("POST", "/orders", {"product": "chair", "price": 1}, alice)
check("T05", "цена заказа от клиента", s == 201 and json.loads(b)["price"] == 1, f"HTTP {s}, цена в заказе: {json.loads(b).get('price')}")

s, b = call("GET", "/files?user=bob&path=receipt.txt", headers=alice)
check("T06a", "alice читает чек bob", s == 200 and "TEST_BOB" in b, f"HTTP {s}")
s, b = call("GET", "/files?user=alice&path=" + quote("../../private/operator-note.txt"))
check("T06b", "служебная заметка без входа", s == 200 and SECRET in b, f"HTTP {s}")

s, b = call("GET", "/debug/logs")
check("T07", "журнал запросов с токенами без входа", s == 200 and alice["X-Token"] in b, f"HTTP {s}, токен alice в журнале: {alice['X-Token'] in b}")

s, _ = call("POST", "/reviews", {"product": "chair", "text": "<b id=probe>x</b>"})
s2, b2 = call("GET", "/reviews/view")
check("T08", "отзыв без входа, HTML без экранирования", s == 201 and "<b id=probe>" in b2, f"POST {s}, в странице тег как есть: {'<b id=probe>' in b2}")

s, b = call("GET", "/assistant/context?order_id=1", headers=alice)
check("T09", "отзыв попадает в prompt без пометки недоверенных данных", s == 200 and "<b id=probe>" in b and "недоверенн" not in b, f"HTTP {s}")

s, b = execute(alice, "read_file", path="private/operator-note.txt")
check("T10", "инструмент read_file читает служебную заметку", s == 200 and SECRET in b, f"HTTP {s}")

s, b = execute(alice, "export_profiles")
check("T11", "клиент вызывает export_profiles", s == 200 and "TEST_BOB" in b, f"HTTP {s}")

s, b = execute(alice, "delete_tree", path="files/bob")
s2, b2 = call("GET", "/files?user=bob&path=receipt.txt", headers=alice)
check("T12", "клиент удаляет чеки bob через delete_tree", s == 200 and s2 != 200, f"удаление HTTP {s}, чек bob после: HTTP {s2}")

codes = [call("POST", "/login", {"username": "alice", "password": "wrong"})[0] for _ in range(8)]
s, _ = call("POST", "/login", {"username": "alice", "password": "learn-alice"})
check("T13", "нет ограничения числа попыток входа", all(c == 401 for c in codes) and s == 200, f"8 неудач подряд: {set(codes)}, затем верный пароль: HTTP {s}")

s, b = call("POST", "/login", raw=b"{not json")
check("T14", "в ошибке видны внутренности", s == 500 and "JSONDecodeError" in b, f"HTTP {s}, тело: {b[:60]}")

s, b = call("POST", "/orders", {}, alice)
check("T15", "пустое тело → необработанная ошибка (500)", s == 500, f"HTTP {s}, тело: {b[:60]}")

call("POST", "/login", {"username": "alice", "password": "wrong-password-probe"})
s, b = call("GET", "/debug/logs")
check("T07b", "пароль из тела /login виден в журнале", s == 200 and "wrong-password-probe" in b, f"HTTP {s}, пароль в журнале: {'wrong-password-probe' in b}")

s, b = call("GET", "/search?q=TEST")
check("T17a", "поиск профилей без входа", s == 200 and "TEST_" in b, f"HTTP {s}")
s, b = call("GET", "/assistant/context?order_id=2")
check("T17b", "контекст помощника без входа", s == 200 and "lamp" in b, f"HTTP {s}")

s, b = call("POST", "/assistant/execute", {"decision": {"tool": "read_file", "arguments": {"path": "private/operator-note.txt"}}})
check("T18", "инструменты помощника без входа", s == 200 and SECRET in b, f"HTTP {s}")

s, b = execute(alice, "delete_tree", path=".")
s2, _ = call("GET", "/files?user=alice&path=receipt.txt", headers=alice)
check("T19", "delete_tree удаляет корень песочницы", s == 200 and s2 != 200, f"удаление HTTP {s}, свой чек после: HTTP {s2}")

s, _ = call("GET", "/health", headers={"Host": "evil.example"})
check("T22a", "чужой заголовок Host принимается (DNS rebinding)", s == 200, f"HTTP {s}")
s, _ = call("POST", "/login", raw=json.dumps({"username": "bob", "password": "learn-bob"}).encode(), headers={"Content-Type": "text/plain"})
check("T22b", "простой кросс-сайтовый POST (text/plain) принимается", s == 200, f"HTTP {s}")

print(f"\nПодтверждено: {sum(c for _, c in results)} из {len(results)} проверок (T16 журнал действий и T20 пределы памяти — только тестами)")
