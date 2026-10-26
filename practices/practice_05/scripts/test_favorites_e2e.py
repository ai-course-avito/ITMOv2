#!/usr/bin/env python3
"""
Сквозной E2E-тест HTTP API подсистемы Избранного (Favorites & Wishlist).
Запускает локальный тестовый HTTP-сервер на свободном порту и проверяет
все 5 эндпоинтов, коды статусов, идемпотентность и структуры данных.
"""

import threading
import json
import urllib.request
import urllib.error
from http.server import HTTPServer
import sys
from pathlib import Path

# Добавляем корень practice_05 в sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.server import VkusMartHTTPHandler
from app.services import favorites_service

def run_test():
    server_address = ("127.0.0.1", 8899)
    httpd = HTTPServer(server_address, VkusMartHTTPHandler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    print("✓ Тестовый HTTP-сервер запущен на http://127.0.0.1:8899")

    base_url = "http://127.0.0.1:8899"
    favorites_service.clear()

    try:
        # 1. GET /api/favorites - пустой список
        req = urllib.request.Request(f"{base_url}/api/favorites")
        with urllib.request.urlopen(req) as resp:
            self_res = json.loads(resp.read().decode("utf-8"))
            assert resp.status == 200
            assert self_res["total_count"] == 0
            assert self_res["items"] == []
            print("✓ [GET /api/favorites]: пустой список корректен")

        # 2. POST /api/favorites - добавление prod-1
        data = json.dumps({"product_id": "prod-1"}).encode("utf-8")
        req = urllib.request.Request(f"{base_url}/api/favorites", data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            self_res = json.loads(resp.read().decode("utf-8"))
            assert resp.status == 200
            assert self_res["status"] == "added"
            assert self_res["already_exists"] is False
            assert self_res["total_count"] == 1
            print("✓ [POST /api/favorites]: товар prod-1 успешно добавлен")

        # 3. POST /api/favorites - повторное добавление prod-1 (Идемпотентность)
        req = urllib.request.Request(f"{base_url}/api/favorites", data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            self_res = json.loads(resp.read().decode("utf-8"))
            assert resp.status == 200
            assert self_res["status"] == "exists"
            assert self_res["already_exists"] is True
            assert self_res["total_count"] == 1
            print("✓ [POST /api/favorites]: идемпотентность подтверждена (200 OK, already_exists=True)")

        # 4. POST /api/favorites - добавление prod-3
        data3 = json.dumps({"product_id": "prod-3"}).encode("utf-8")
        req = urllib.request.Request(f"{base_url}/api/favorites", data=data3, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            self_res = json.loads(resp.read().decode("utf-8"))
            assert self_res["total_count"] == 2
            print("✓ [POST /api/favorites]: товар prod-3 успешно добавлен, всего 2 товара")

        # 5. GET /api/favorites - обогащенный список
        req = urllib.request.Request(f"{base_url}/api/favorites")
        with urllib.request.urlopen(req) as resp:
            self_res = json.loads(resp.read().decode("utf-8"))
            assert resp.status == 200
            assert self_res["total_count"] == 2
            assert self_res["total_price"] == 530.0  # 320 + 210
            assert self_res["total_calories"] == 280 # 120 + 160
            assert len(self_res["items"]) == 2
            assert self_res["items"][0]["name"] == "Филе грудки индейки су-вид"
            print("✓ [GET /api/favorites]: обогащенный DTO (цена 530.0 ₽, калории 280) подтвержден")

        # 6. DELETE /api/favorites - удаление prod-1
        data_del = json.dumps({"product_id": "prod-1"}).encode("utf-8")
        req = urllib.request.Request(f"{base_url}/api/favorites", data=data_del, headers={"Content-Type": "application/json"}, method="DELETE")
        with urllib.request.urlopen(req) as resp:
            self_res = json.loads(resp.read().decode("utf-8"))
            assert resp.status == 200
            assert self_res["status"] == "removed"
            assert self_res["total_count"] == 1
            print("✓ [DELETE /api/favorites]: товар prod-1 удален")

        # 7. POST /api/favorites/move-to-cart - перенос в корзину
        data_move = json.dumps({"clear_favorites": True}).encode("utf-8")
        req = urllib.request.Request(f"{base_url}/api/favorites/move-to-cart", data=data_move, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            self_res = json.loads(resp.read().decode("utf-8"))
            assert resp.status == 200
            assert self_res["status"] == "moved_to_cart"
            assert self_res["moved_items_count"] == 1
            assert self_res["favorites_count"] == 0
            assert "cart" in self_res
            print("✓ [POST /api/favorites/move-to-cart]: атомарный перенос в корзину успешен")

        # 8. Ошибочный сценарий: несуществующий товар (404)
        data_err = json.dumps({"product_id": "prod-unknown-999"}).encode("utf-8")
        req = urllib.request.Request(f"{base_url}/api/favorites", data=data_err, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as resp:
                assert False, "Запрос должен был завершиться ошибкой 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404
            err_body = json.loads(e.read().decode("utf-8"))
            assert err_body["error"] == "product_not_found"
            print("✓ [Error 404]: корректный ответ product_not_found при несуществующем ID")

        # 9. Ошибочный сценарий: пустой запрос (400)
        data_bad = json.dumps({}).encode("utf-8")
        req = urllib.request.Request(f"{base_url}/api/favorites", data=data_bad, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as resp:
                assert False, "Запрос должен был завершиться ошибкой 400"
        except urllib.error.HTTPError as e:
            assert e.code == 400
            err_body = json.loads(e.read().decode("utf-8"))
            assert err_body["error"] == "missing_product_id"
            print("✓ [Error 400]: корректный ответ missing_product_id при пустом payload")

        print("\n🎉 ВСЕ СЦЕНАРИИ СКВОЗНОГО ТЕСТИРОВАНИЯ УСПЕШНО ПРОЙДЕНЫ!")

    finally:
        httpd.shutdown()
        httpd.server_close()

if __name__ == "__main__":
    run_test()
