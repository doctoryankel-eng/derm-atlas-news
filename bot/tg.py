"""Минимальный клиент Telegram Bot API (только стандартная библиотека).

Токен берется из переменной окружения TELEGRAM_BOT_TOKEN и нигде не выводится.
"""
import json
import os
import urllib.error
import urllib.request


class TgError(Exception):
    pass


def call(method, **params):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise TgError("не задана переменная TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(params).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            body = {"ok": False, "description": f"HTTP {exc.code}"}
    except Exception as exc:
        # текст исключения может содержать адрес с токеном, поэтому выводим только тип
        raise TgError(f"{method}: {type(exc).__name__}")
    if not body.get("ok"):
        raise TgError(f"{method}: {body.get('description')}")
    return body["result"]
