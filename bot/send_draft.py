#!/usr/bin/env python3
"""Отправляет владельцу канала черновики из drafts/<папка>/ с кнопками согласования.

Папка черновика:
  digest.html     текст выпуска в Telegram HTML, сообщения разделены строкой <!--split-->
  cards/*.json    карточки для сайта (status draft)
  TEST            необязательный файл: тестовый черновик, публикация уйдет только владельцу
Отправленные черновики помечаются файлом .sent.
"""
import html
import sys

import common
import tg


def notify(owner, text):
    tg.call("sendMessage", chat_id=owner, text=text, parse_mode="HTML", disable_web_page_preview=True)


def send_one(folder, owner):
    name = folder.name
    errors, warnings, cards = common.lint_draft(folder)
    if errors:
        notify(owner, f"Черновик {html.escape(name)} не отправлен на согласование.\n"
               + "\n".join("- " + html.escape(e) for e in errors))
        print(f"[ошибки] {name}: {len(errors)}")
        return False
    test = (folder / "TEST").exists()
    parts = common.read_parts(folder)
    prefix = "[ТЕСТ] " if test else ""
    for part in parts:
        tg.call("sendMessage", chat_id=owner, text=prefix + part, parse_mode="HTML",
                disable_web_page_preview=True)
    lines = [f"{prefix}<b>Выпуск {html.escape(name)}</b>: сообщений {len(parts)}, карточек для сайта {len(cards)}."]
    for card in cards:
        lines.append("- " + html.escape(card["title"]))
    if warnings:
        lines.append("\nПредупреждения:")
        lines += ["- " + html.escape(w) for w in warnings]
    if test:
        lines.append("\nТестовый режим: после нажатия «Опубликовать» выпуск придет сюда же, канал не затрагивается.")
    else:
        lines.append(f"\nОпубликовать выпуск в канале «Записки Дерматолога»?")
    keyboard = {"inline_keyboard": [[
        {"text": "Опубликовать", "callback_data": f"pub:{name}"},
        {"text": "Правки", "callback_data": f"edit:{name}"},
        {"text": "Отклонить", "callback_data": f"rej:{name}"},
    ]]}
    tg.call("sendMessage", chat_id=owner, text="\n".join(lines), parse_mode="HTML",
            disable_web_page_preview=True, reply_markup=keyboard)
    (folder / ".sent").write_text("sent\n", encoding="utf-8")
    print(f"[отправлено] {name}")
    return True


def main():
    owner = common.owner_id()
    sent = False
    if not common.DRAFTS.exists():
        print("Папки drafts нет")
        return 0
    for folder in sorted(common.DRAFTS.iterdir()):
        if folder.is_dir() and common.FOLDER_RE.match(folder.name) and not (folder / ".sent").exists():
            sent = send_one(folder, owner) or sent
    if sent:
        common.commit_and_push("Черновики отправлены на согласование")
    return 0


if __name__ == "__main__":
    sys.exit(main())
