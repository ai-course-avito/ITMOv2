#!/usr/bin/env python3
"""Разовое получение access token у TickTick (OAuth 2.0, authorization code).

Запуск:  python3 get_token.py

Перед запуском заполни в .env значения TICKTICK_CLIENT_ID и TICKTICK_CLIENT_SECRET.
Скрипт напечатает ссылку, ты подтвердишь доступ в браузере и вставишь обратно адрес,
на который тебя перекинуло. Токен будет дописан в .env. На экран он не выводится.
"""

import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENV_PATH = Path(__file__).with_name(".env")
AUTHORIZE_URL = "https://ticktick.com/oauth/authorize"
TOKEN_URL = "https://ticktick.com/oauth/token"
SCOPE = "tasks:read tasks:write"


def read_env(path):
    values = {}
    if not path.exists():
        sys.exit(f"Нет файла {path}. Скопируй .env.example в .env и заполни его.")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def write_token(path, token):
    lines = path.read_text(encoding="utf-8").splitlines()
    out, replaced = [], False
    for line in lines:
        if line.strip().startswith("TICKTICK_ACCESS_TOKEN="):
            out.append(f"TICKTICK_ACCESS_TOKEN={token}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"TICKTICK_ACCESS_TOKEN={token}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def post_token(params, client_id, client_secret, use_basic_auth):
    data = dict(params)
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if use_basic_auth:
        pair = f"{client_id}:{client_secret}".encode()
        headers["Authorization"] = "Basic " + base64.b64encode(pair).decode()
    else:
        data["client_id"] = client_id
        data["client_secret"] = client_secret
    request = urllib.request.Request(
        TOKEN_URL, data=urllib.parse.urlencode(data).encode(), headers=headers
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode())


def main():
    env = read_env(ENV_PATH)
    client_id = env.get("TICKTICK_CLIENT_ID", "")
    client_secret = env.get("TICKTICK_CLIENT_SECRET", "")
    redirect_uri = env.get("TICKTICK_REDIRECT_URI", "")

    missing = [
        name
        for name, value in (
            ("TICKTICK_CLIENT_ID", client_id),
            ("TICKTICK_CLIENT_SECRET", client_secret),
            ("TICKTICK_REDIRECT_URI", redirect_uri),
        )
        if not value
    ]
    if missing:
        sys.exit("В .env не заполнено: " + ", ".join(missing))

    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "scope": SCOPE,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": "subtracker-hw4",
        }
    )
    print("\n1. Открой эту ссылку в браузере и подтверди доступ:\n")
    print(f"   {AUTHORIZE_URL}?{query}\n")
    print("2. Браузер перекинет на localhost и покажет ошибку — это нормально.")
    print("   Скопируй из адресной строки ВЕСЬ адрес целиком.\n")

    redirected = input("3. Вставь адрес сюда и нажми Enter:\n> ").strip()
    if not redirected:
        sys.exit("Адрес пустой, отмена.")

    parsed = urllib.parse.urlparse(redirected)
    params = urllib.parse.parse_qs(parsed.query)
    if "error" in params:
        sys.exit(f"TickTick вернул ошибку: {params['error'][0]}")
    code = params.get("code", [""])[0]
    if not code:
        sys.exit("В адресе нет параметра code. Скопируй адрес целиком, вместе с '?code=...'.")

    payload = {
        "code": code,
        "grant_type": "authorization_code",
        "scope": SCOPE,
        "redirect_uri": redirect_uri,
    }

    last_error = None
    for use_basic_auth in (False, True):
        try:
            result = post_token(payload, client_id, client_secret, use_basic_auth)
            break
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:300]}"
        except urllib.error.URLError as exc:
            sys.exit(f"Сеть недоступна: {exc.reason}")
    else:
        sys.exit(f"Не удалось обменять код на токен. {last_error}")

    token = result.get("access_token")
    if not token:
        sys.exit(f"В ответе нет access_token. Ответ: {json.dumps(result)[:300]}")

    write_token(ENV_PATH, token)
    print(f"\nГотово. Токен сохранён в {ENV_PATH.name} (длина {len(token)} символов).")
    print("На экран он не выводится. Никому его не показывай и не коммить.")
    if "expires_in" in result:
        print(f"Срок действия по данным TickTick: {result['expires_in']} секунд.")


if __name__ == "__main__":
    main()
