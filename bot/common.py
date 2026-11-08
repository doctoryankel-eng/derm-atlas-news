"""Общие функции для отправки черновиков и обработки кнопок."""
import html
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(os.environ.get("BOT_ROOT") or pathlib.Path(__file__).resolve().parent.parent)
DRAFTS = ROOT / "drafts"
CARDS = ROOT / "cards"
ARCHIVE = ROOT / "archive"
CHANNEL = os.environ.get("TG_CHANNEL", "@doctoryankelevich")
FOLDER_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(-[a-z0-9]+)?$")
SPLIT = "<!--split-->"
MAX_VISIBLE = 3900
ALLOWED_TAGS = {"b", "i", "u", "s", "a", "code", "pre", "blockquote", "tg-spoiler"}

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import generate  # noqa: E402  (проверки карточек из генератора сайта)

import tg  # noqa: E402


def owner_id():
    """Владелец канала. Только он может нажимать кнопки и получает черновики."""
    for admin in tg.call("getChatAdministrators", chat_id=CHANNEL):
        if admin.get("status") == "creator":
            return admin["user"]["id"]
    raise tg.TgError("в канале не найден владелец")


def read_parts(folder):
    text = (folder / "digest.html").read_text(encoding="utf-8")
    return [p.strip() for p in text.split(SPLIT) if p.strip()]


def lint_part(part):
    """Возвращает (ошибки, предупреждения) для одного сообщения Telegram HTML."""
    errors, warnings = [], []
    stack = []
    for m in re.finditer(r"<(/?)([a-zA-Z][a-zA-Z-]*)([^>]*)>", part):
        closing, name = m.group(1), m.group(2).lower()
        if name not in ALLOWED_TAGS:
            errors.append(f"тег <{name}> не поддерживается Telegram")
            continue
        if closing:
            if not stack or stack[-1] != name:
                errors.append(f"лишний или неверно вложенный тег </{name}>")
            else:
                stack.pop()
        else:
            stack.append(name)
    if stack:
        errors.append("не закрыт тег <" + stack[-1] + ">")
    no_tags = re.sub(r"<(/?)([a-zA-Z][a-zA-Z-]*)([^>]*)>", "", part)
    if "<" in no_tags or ">" in no_tags:
        errors.append("символы < и > в тексте нужно писать как &lt; и &gt;")
    if re.search(r"&(?!(amp|lt|gt|quot|#\d+);)", no_tags):
        errors.append("символ & в тексте нужно писать как &amp;")
    visible = html.unescape(no_tags)
    if len(visible) > MAX_VISIBLE:
        errors.append(f"сообщение длиннее {MAX_VISIBLE} знаков ({len(visible)})")
    if "—" in visible or "–" in visible or "--" in visible:
        errors.append("в тексте есть тире или двойной дефис, нужен одинарный дефис")
    for rx in generate.ANTITHESIS:
        if rx.search(visible):
            warnings.append("возможная антитеза в тексте выпуска")
            break
    if re.search(r"(?i)патч[- ]?тест|patch test", visible):
        warnings.append("в тексте упоминаются патч-тесты")
    return errors, warnings


def lint_draft(folder):
    """Проверяет выпуск и карточки. Возвращает (ошибки, предупреждения, карточки)."""
    errors, warnings, cards = [], [], []
    if not (folder / "digest.html").exists():
        return ["нет файла digest.html"], [], []
    parts = read_parts(folder)
    if not parts:
        errors.append("выпуск пустой")
    for i, part in enumerate(parts, 1):
        e, w = lint_part(part)
        errors += [f"сообщение {i}: {x}" for x in e]
        warnings += [f"сообщение {i}: {x}" for x in w]
    for path in sorted((folder / "cards").glob("*.json")) if (folder / "cards").exists() else []:
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            errors.append(f"{path.name}: некорректный JSON")
            continue
        e, w = generate.check_card(card, path)
        errors += [f"{path.name}: {x}" for x in e]
        warnings += [f"{path.name}: {x}" for x in w]
        cards.append(card)
    return errors, warnings, cards


def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=ROOT, check=check, capture_output=True, text=True)


def commit_and_push(message):
    """Фиксирует изменения и отправляет их в main. В тестах отключается BOT_NO_GIT=1."""
    if os.environ.get("BOT_NO_GIT") == "1":
        return
    git("config", "user.name", "derm-atlas-bot")
    git("config", "user.email", "bot@users.noreply.github.com")
    git("add", "-A")
    if not git("status", "--porcelain").stdout.strip():
        return
    git("commit", "-m", message)
    for attempt in range(2):
        git("pull", "--rebase", "origin", "main", check=False)
        res = git("push", "origin", "HEAD:main", check=False)
        if res.returncode == 0:
            return
    raise RuntimeError("не удалось отправить изменения в репозиторий")


def dispatch_deploy():
    if os.environ.get("BOT_NO_GIT") == "1":
        return
    subprocess.run(["gh", "workflow", "run", "deploy.yml", "--ref", "main"], cwd=ROOT, check=False)
