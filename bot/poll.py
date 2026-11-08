#!/usr/bin/env python3
"""Обрабатывает нажатия кнопок согласования. Запускается по расписанию в GitHub Actions.

Кнопки принимаются только от владельца канала. Каждое нажатие обрабатывается не более одного
раза: обновления подтверждаются в Telegram до обработки. Если публикация не удалась,
владелец получает сообщение об ошибке и может нажать кнопку еще раз на новом черновике.
"""
import html
import json
import shutil
import sys
import time

import common
import tg


def pending():
    if not common.DRAFTS.exists():
        return []
    return [d for d in sorted(common.DRAFTS.iterdir())
            if d.is_dir() and common.FOLDER_RE.match(d.name) and (d / ".sent").exists()]


def say(owner, text):
    tg.call("sendMessage", chat_id=owner, text=text, parse_mode="HTML", disable_web_page_preview=True)


def strip_buttons(owner, message):
    try:
        tg.call("editMessageReplyMarkup", chat_id=owner, message_id=message["message_id"],
                reply_markup={"inline_keyboard": []})
    except tg.TgError:
        pass


def answer(query_id, text):
    try:
        tg.call("answerCallbackQuery", callback_query_id=query_id, text=text)
    except tg.TgError:
        pass


def publish(folder, owner):
    errors, _warnings, cards = common.lint_draft(folder)
    if errors:
        say(owner, "Публикация остановлена, в черновике найдены ошибки:\n"
            + "\n".join("- " + html.escape(e) for e in errors))
        return
    test = (folder / "TEST").exists()
    target = owner if test else common.CHANNEL
    prefix = "[ТЕСТ] " if test else ""
    for part in common.read_parts(folder):
        tg.call("sendMessage", chat_id=target, text=prefix + part, parse_mode="HTML",
                disable_web_page_preview=True)
    if test:
        shutil.rmtree(folder)
        common.commit_and_push(f"Тестовый черновик {folder.name} обработан")
        say(owner, "Тест пройден: выпуск пришел сюда, канал не затронут. Черновик удален.")
        return
    common.CARDS.mkdir(exist_ok=True)
    for card in cards:
        card["status"] = "published"
        (common.CARDS / f"{card['slug']}.json").write_text(
            json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    common.ARCHIVE.mkdir(exist_ok=True)
    shutil.copy(folder / "digest.html", common.ARCHIVE / f"{folder.name}.html")
    shutil.rmtree(folder)
    common.commit_and_push(f"Выпуск {folder.name} опубликован, карточки добавлены на сайт")
    common.dispatch_deploy()
    say(owner, f"Выпуск {html.escape(folder.name)} опубликован в канале. Карточки ({len(cards)}) появятся на сайте "
        "через несколько минут. Чтобы создать страницы на derm-atlas.ru, напишите Claude: "
        "«сделай страницы в Tilda».")


def reject(folder, owner):
    shutil.rmtree(folder)
    common.commit_and_push(f"Черновик {folder.name} отклонен")
    say(owner, f"Черновик {html.escape(folder.name)} отклонен и удален.")


def edit(folder, owner):
    (folder / ".sent").unlink(missing_ok=True)
    common.commit_and_push(f"Черновик {folder.name} возвращен на правки")
    say(owner, f"Черновик {html.escape(folder.name)} возвращен на правки. Напишите Claude, что исправить: "
        "новая версия придет сюда с теми же кнопками.")


def handle(query, owner):
    qid = query["id"]
    if query.get("from", {}).get("id") != owner:
        answer(qid, "Нет доступа")
        return
    message = query.get("message") or {}
    if message.get("chat", {}).get("id") != owner:
        answer(qid, "Нет доступа")
        return
    action, _, name = (query.get("data") or "").partition(":")
    folder = common.DRAFTS / name
    if action not in ("pub", "edit", "rej") or not common.FOLDER_RE.match(name):
        answer(qid, "Неизвестная команда")
        return
    if not folder.is_dir() or not (folder / ".sent").exists():
        answer(qid, "Черновик уже обработан или удален")
        strip_buttons(owner, message)
        return
    answer(qid, "Принято, обрабатываю")
    strip_buttons(owner, message)
    try:
        {"pub": publish, "edit": edit, "rej": reject}[action](folder, owner)
    except Exception as exc:  # сообщаем владельцу, детали в журнале без токена
        print(f"[ошибка] {action} {name}: {type(exc).__name__}")
        say(owner, f"Не удалось выполнить действие «{action}» для {html.escape(name)}: "
            f"{html.escape(type(exc).__name__)}. Проверьте журнал запуска в GitHub Actions.")


def process(owner, updates):
    for update in updates:
        if "callback_query" in update:
            handle(update["callback_query"], owner)


def main():
    """Без аргументов: одна проверка. С параметром --wait N: ждет нажатий до N секунд,
    пока на согласовании есть черновики (долгий опрос Telegram)."""
    wait = 0
    if "--wait" in sys.argv:
        wait = int(sys.argv[sys.argv.index("--wait") + 1])
    if not pending():
        print("Черновиков на согласовании нет")
        return 0
    owner = common.owner_id()
    try:
        info = tg.call("getWebhookInfo")
        print("webhook:", "задан" if info.get("url") else "нет", "| ожидающих обновлений:", info.get("pending_update_count"))
    except tg.TgError as exc:
        print("getWebhookInfo:", exc)
    deadline = time.time() + wait
    offset = None
    while True:
        params = {"timeout": 25 if wait else 0, "allowed_updates": ["callback_query"]}
        if offset is not None:
            params["offset"] = offset
        try:
            updates = tg.call("getUpdates", **params)
        except tg.TgError as exc:
            print("getUpdates:", exc)
            updates = []
            time.sleep(5)
        if updates:
            offset = max(u["update_id"] for u in updates) + 1
            tg.call("getUpdates", offset=offset, timeout=0, allowed_updates=["callback_query"])
            print(f"получено обновлений: {len(updates)}")
            process(owner, updates)
        elif not wait:
            print("Новых нажатий нет")
        if not wait or time.time() >= deadline or not pending():
            return 0


if __name__ == "__main__":
    sys.exit(main())
