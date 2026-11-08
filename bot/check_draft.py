#!/usr/bin/env python3
"""Локальная проверка черновика: python3 bot/check_draft.py drafts/2026-11-15

Токен не нужен. Код возврата 1, если есть ошибки."""
import pathlib
import sys

import common

folder = pathlib.Path(sys.argv[1])
errors, warnings, cards = common.lint_draft(folder)
parts = common.read_parts(folder) if (folder / "digest.html").exists() else []
print(f"сообщений: {len(parts)}, карточек: {len(cards)}")
for e in errors:
    print("ОШИБКА:", e)
for w in warnings:
    print("предупреждение:", w)
sys.exit(1 if errors else 0)
