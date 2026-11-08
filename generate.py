#!/usr/bin/env python3
"""
Раздел новостей derm-atlas.ru: генератор статичного сайта.

Читает карточки из cards/*.json и собирает в dist/:
  index.html            лента карточек с поиском и фильтром по тегам
  <slug>/index.html     страница карточки
  feed.xml              лента RSS
  cards.json            все опубликованные карточки одним файлом
  sitemap.xml, robots.txt, CNAME

Запуск:
  python3 generate.py                   публикуемые карточки (status = published)
  python3 generate.py --include-drafts  предпросмотр вместе с черновиками

Только стандартная библиотека Python 3.9+.
"""
import argparse
import datetime
import html
import json
import pathlib
import re
import shutil
import sys
from email.utils import format_datetime

ROOT = pathlib.Path(__file__).parent
CARDS_DIR = ROOT / "cards"
DIST = ROOT / "dist"
TILDA_OUT = ROOT / "tilda_out"

MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля",
          "августа", "сентября", "октября", "ноября", "декабря"]

REQUIRED = ["slug", "title", "date", "journal", "doc_type", "url", "method",
            "results", "authors_conclusion", "our_analysis", "evidence_level"]

DISCLAIMER = ("Материал для врачей. Разбор не заменяет полный текст публикации "
              "и клинические рекомендации.")


def esc(value):
    return html.escape(str(value), quote=True)


def ru_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def walk_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from walk_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk_strings(v)


ANTITHESIS = [
    re.compile(r"(?i)\bне\s[^.!?\n]{1,80}?,\s*а\s"),
    re.compile(r"(?i)\bэто\s[^.!?\n]{1,60}?,\s*не\s"),
]


def check_card(card, path):
    """Возвращает (ошибки, предупреждения). Ошибка блокирует публикацию карточки."""
    errors, warnings = [], []
    for key in REQUIRED:
        if key not in card or card[key] in ("", [], {}, None):
            errors.append(f"нет поля {key}")
    if errors:
        return errors, warnings

    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", card["slug"]):
        errors.append("slug должен состоять из латиницы, цифр и дефисов")
    try:
        datetime.date.fromisoformat(card["date"])
    except ValueError:
        errors.append("date должна быть в формате ГГГГ-ММ-ДД")
    if not str(card["url"]).startswith("https://"):
        errors.append("url должен начинаться с https://")
    tilda_url = card.get("tilda_url")
    if tilda_url and not re.match(r"https?://derm-atlas\.ru/", str(tilda_url)):
        errors.append("tilda_url должен начинаться с https://derm-atlas.ru/")
    for key in ("design", "population", "endpoint"):
        if not card["method"].get(key):
            errors.append(f"в method нет поля {key}")
    for key in ("strengths", "limitations", "applicability_ru"):
        if not card["our_analysis"].get(key):
            errors.append(f"в our_analysis нет поля {key}")

    for text in walk_strings({k: v for k, v in card.items() if k not in ("url",)}):
        if "\u2014" in text or "\u2013" in text or "--" in text:
            errors.append("в тексте есть тире или двойной дефис, нужен одинарный дефис")
            break
    for text in walk_strings(card):
        for rx in ANTITHESIS:
            if rx.search(text):
                warnings.append("возможная антитеза: " + text[:80])
                break
        if re.search(r"(?i)патч[- ]?тест|patch test", text):
            warnings.append("упоминание патч-тестов")
    return errors, warnings


def load_cards(include_drafts):
    cards = []
    for path in sorted(CARDS_DIR.glob("*.json")):
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"[пропуск] {path.name}: некорректный JSON ({exc})")
            continue
        errors, warnings = check_card(card, path)
        for w in warnings:
            print(f"[предупреждение] {path.name}: {w}")
        if errors:
            print(f"[пропуск] {path.name}: " + "; ".join(errors))
            continue
        status = card.get("status", "published")
        if status != "published" and not include_drafts:
            continue
        cards.append(card)
    cards.sort(key=lambda c: (c["date"], c["slug"]), reverse=True)
    return cards


CSS = """
:root{--bg:#fbfaf8;--fg:#1d2326;--muted:#5d696e;--accent:#0f6b6b;--accent-soft:#e3f0ef;
--line:#e2e0da;--card:#ffffff;--warn:#8a5a00;--warn-bg:#fff4dc}
@media (prefers-color-scheme:dark){:root{--bg:#14191b;--fg:#e8ecec;--muted:#9aa7ab;
--accent:#5cc2bd;--accent-soft:#1d2f30;--line:#2a3336;--card:#1a2022;--warn:#f0c46a;--warn-bg:#2d2512}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:17px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent)}
.wrap{max-width:860px;margin:0 auto;padding:0 16px}
header.site{border-bottom:1px solid var(--line);background:var(--card)}
header.site .wrap{display:flex;align-items:center;gap:24px;flex-wrap:wrap;padding-top:14px;padding-bottom:14px}
header.site .brand{font-weight:700;font-size:20px;color:var(--fg);text-decoration:none}
header.site nav a{margin-right:18px;text-decoration:none;color:var(--muted)}
header.site nav a.on{color:var(--accent);font-weight:600}
h1{font-size:30px;line-height:1.25;margin:8px 0 12px}
h2{font-size:21px;margin:30px 0 10px}
.lead{color:var(--muted);margin:0 0 20px}
.search{width:100%;padding:11px 14px;font-size:16px;border:1px solid var(--line);
border-radius:10px;background:var(--card);color:var(--fg)}
.tags{margin:14px 0 22px;display:flex;flex-wrap:wrap;gap:8px}
.tag{border:1px solid var(--line);background:var(--card);color:var(--fg);padding:5px 12px;
border-radius:999px;font-size:14px;cursor:pointer}
.tag.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.card{display:block;background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:18px 20px;margin:0 0 14px;text-decoration:none;color:var(--fg)}
.card:hover{border-color:var(--accent)}
.card h3{margin:4px 0 8px;font-size:19px;line-height:1.35}
.meta{font-size:14px;color:var(--muted);margin:0}
.badge{display:inline-block;background:var(--accent-soft);color:var(--accent);
font-size:13px;padding:2px 10px;border-radius:999px;margin-right:6px}
.btn{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;
padding:9px 18px;border-radius:10px;font-weight:600}
dl.method{display:grid;grid-template-columns:170px 1fr;gap:8px 16px;margin:0}
dl.method dt{color:var(--muted)}
dl.method dd{margin:0}
.box{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:6px 20px 14px}
.warn{background:var(--warn-bg);color:var(--warn);border-radius:10px;padding:10px 14px;font-size:15px}
.disclaimer{margin:36px 0 0;padding-top:14px;border-top:1px solid var(--line);
color:var(--muted);font-size:14px}
footer{margin:40px 0 30px;color:var(--muted);font-size:14px}
.hidden{display:none}
@media(max-width:600px){dl.method{grid-template-columns:1fr}dl.method dt{margin-top:6px}h1{font-size:25px}}
"""

INDEX_JS = """
(function(){
var q=document.getElementById('q'),cards=[].slice.call(document.querySelectorAll('.card')),
tags=[].slice.call(document.querySelectorAll('.tag')),active='',empty=document.getElementById('empty');
function apply(){var s=(q.value||'').toLowerCase(),n=0;
cards.forEach(function(c){var ok=(!s||c.dataset.text.indexOf(s)>-1)&&(!active||c.dataset.tags.indexOf('|'+active+'|')>-1);
c.classList.toggle('hidden',!ok);if(ok)n++;});empty.classList.toggle('hidden',n>0);}
q.addEventListener('input',apply);
tags.forEach(function(t){t.addEventListener('click',function(){
active=(active===t.dataset.tag)?'':t.dataset.tag;
tags.forEach(function(x){x.classList.toggle('on',x.dataset.tag===active)});apply();});});
})();
"""


def shell(config, title, description, canonical, body, active_news=True, extra_head="", script=""):
    site = config["site_url"].rstrip("/")
    main = config["main_site_url"].rstrip("/")
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<link rel="alternate" type="application/rss+xml" title="Кожный атлас - новости" href="{esc(site)}/feed.xml">
<meta property="og:type" content="article">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
{extra_head}
<style>{CSS}</style>
</head>
<body>
<header class="site"><div class="wrap">
<a class="brand" href="{esc(main)}/">Кожный атлас</a>
<nav>
<a href="{esc(main)}/">Все болезни</a>
<a class="{'on' if active_news else ''}" href="{esc(site)}/">Новости</a>
<a href="{esc(main)}/#about">О проекте</a>
</nav></div></header>
<main class="wrap">
{body}
</main>
<footer class="wrap">Кожный атлас - некоммерческий образовательный проект для врачей.</footer>
{('<script>' + script + '</script>') if script else ''}
</body>
</html>
"""


def render_index(config, cards):
    all_tags = sorted({t for c in cards for t in c.get("tags", [])})
    tag_buttons = "".join(
        f'<button class="tag" type="button" data-tag="{esc(t)}">{esc(t)}</button>' for t in all_tags
    )
    items = []
    for c in cards:
        text = " ".join([c["title"], c["journal"], c["doc_type"], " ".join(c.get("tags", []))]).lower()
        tags_attr = "|" + "|".join(c.get("tags", [])) + "|"
        draft = '<span class="badge">Черновик</span>' if c.get("status", "published") != "published" else ""
        items.append(
            f'<a class="card" href="{esc(c["slug"])}/" data-text="{esc(text)}" data-tags="{esc(tags_attr)}">'
            f'<p class="meta">{draft}<span class="badge">{esc(c["doc_type"])}</span>'
            f'{esc(ru_date(c["date"]))} - {esc(c["journal"])}</p>'
            f'<h3>{esc(c["title"])}</h3>'
            f'<p class="meta">Уровень доказательности: {esc(c["evidence_level"])}</p></a>'
        )
    body = (
        "<h1>Новости дерматологии</h1>"
        '<p class="lead">Свежие публикации и руководства с разбором метода и вывода. '
        "Тезисы здесь, полный текст по ссылке на оригинал.</p>"
        '<input id="q" class="search" type="search" placeholder="Поиск по названию, журналу, тегу">'
        f'<div class="tags">{tag_buttons}</div>'
        + ("\n".join(items) if items else '<p class="lead">Карточек пока нет.</p>')
        + '<p id="empty" class="lead hidden">Ничего не найдено.</p>'
    )
    return shell(
        config,
        "Новости дерматологии - Кожный атлас",
        "Свежие публикации и руководства по дерматологии с разбором метода и вывода.",
        config["site_url"].rstrip("/") + "/",
        body,
        script=INDEX_JS,
    )


def ul(items):
    return "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"


def card_inner(c, back_url):
    m = c["method"]
    a = c["our_analysis"]
    labels = [
        ("design", "Дизайн"), ("population", "Популяция"), ("sample", "Выборка"),
        ("comparison", "Сравнение"), ("endpoint", "Основная конечная точка"),
        ("followup", "Срок наблюдения"),
    ]
    method_rows = "".join(
        f"<dt>{label}</dt><dd>{esc(m[key])}</dd>" for key, label in labels if m.get(key)
    )
    doi = (f' DOI: <a href="https://doi.org/{esc(c["doi"])}">{esc(c["doi"])}</a>' if c.get("doi") else "")
    related = ""
    if c.get("related"):
        related = "<h2>Связанные разделы атласа</h2><ul>" + "".join(
            f'<li><a href="{esc(r["url"])}">{esc(r["title"])}</a></li>' for r in c["related"]
        ) + "</ul>"
    extrapolation = (
        f'<p class="warn">Экстраполяция и мнение экспертов: {esc(c["extrapolation_note"])}</p>'
        if c.get("extrapolation_note") else ""
    )
    funding = (f"<h3>Финансирование и конфликт интересов</h3><p>{esc(a['funding'])}</p>"
               if a.get("funding") else "")
    tags = " ".join(f'<span class="badge">{esc(t)}</span>' for t in c.get("tags", []))
    draft = ('<p class="warn">Черновик. Карточка не опубликована.</p>'
             if c.get("status", "published") != "published" else "")
    return f"""{draft}
<p class="meta"><span class="badge">{esc(c['doc_type'])}</span>{esc(ru_date(c['date']))} - {esc(c['journal'])}</p>
<h1>{esc(c['title'])}</h1>
<p><a class="btn" href="{esc(c['url'])}" rel="noopener">Читать оригинал</a>{doi}</p>
<h2>Метод</h2>
<div class="box"><dl class="method">{method_rows}</dl></div>
<h2>Результат</h2>
{ul(c['results'])}
<h2>Вывод авторов</h2>
<p>{esc(c['authors_conclusion'])}</p>
<h2>Наш разбор</h2>
<div class="box">
<h3>Сильные стороны</h3>{ul(a['strengths'])}
<h3>Ограничения</h3>{ul(a['limitations'])}
{funding}
<h3>Применимость в России</h3><p>{esc(a['applicability_ru'])}</p>
</div>
<h2>Уровень доказательности</h2>
<p>{esc(c['evidence_level'])}</p>
{extrapolation}
{related}
<p style="margin-top:24px">{tags}</p>
<p class="disclaimer">{esc(DISCLAIMER)}</p>
<p><a href="{esc(back_url)}">Все новости</a></p>"""


def render_card(config, c):
    body = card_inner(c, "../")
    description = c["authors_conclusion"][:180]
    own = config["site_url"].rstrip("/") + "/" + c["slug"] + "/"
    # если есть страница на derm-atlas.ru, она основная для поисковиков
    canonical = c.get("tilda_url") or own
    return shell(config, c["title"] + " - Кожный атлас", description, canonical, body)


NW_CSS = """
.nw{max-width:860px;margin:0 auto;padding:24px 16px;color:#1d2326;font:17px/1.6 inherit}
.nw h1{font-size:30px;line-height:1.25;margin:8px 0 12px}
.nw h2{font-size:21px;margin:30px 0 10px}
.nw h3{font-size:17px;margin:16px 0 6px}
.nw a{color:#0f6b6b}
.nw .meta{font-size:14px;color:#5d696e;margin:0}
.nw .badge{display:inline-block;background:#e3f0ef;color:#0f6b6b;font-size:13px;padding:2px 10px;border-radius:999px;margin-right:6px}
.nw .btn{display:inline-block;background:#0f6b6b;color:#fff;text-decoration:none;padding:9px 18px;border-radius:10px;font-weight:600}
.nw dl.method{display:grid;grid-template-columns:170px 1fr;gap:8px 16px;margin:0}
.nw dl.method dt{color:#5d696e}
.nw dl.method dd{margin:0}
.nw .box{background:#fff;border:1px solid #e2e0da;border-radius:12px;padding:6px 20px 14px}
.nw .warn{background:#fff4dc;color:#8a5a00;border-radius:10px;padding:10px 14px;font-size:15px}
.nw .disclaimer{margin:36px 0 0;padding-top:14px;border-top:1px solid #e2e0da;color:#5d696e;font-size:14px}
.nw .item{display:block;background:#fff;border:1px solid #e2e0da;border-radius:14px;padding:18px 20px;margin:0 0 14px;text-decoration:none;color:#1d2326}
.nw .item h3{margin:4px 0 8px;font-size:19px;line-height:1.35}
@media(max-width:600px){.nw dl.method{grid-template-columns:1fr}.nw h1{font-size:25px}}
"""


def render_tilda_card(config, c):
    """Фрагмент для блока HTML (T123) на странице Tilda."""
    back = config.get("tilda_news_url", config["site_url"].rstrip("/") + "/")
    return f'<style>{NW_CSS}</style>\n<div class="nw">\n{card_inner(c, back)}\n</div>\n'


def render_tilda_list(config, cards):
    items = []
    for c in cards:
        url = c.get("tilda_url") or (config["site_url"].rstrip("/") + "/" + c["slug"] + "/")
        items.append(
            f'<a class="item" href="{esc(url)}">'
            f'<p class="meta"><span class="badge">{esc(c["doc_type"])}</span>'
            f'{esc(ru_date(c["date"]))} - {esc(c["journal"])}</p>'
            f'<h3>{esc(c["title"])}</h3>'
            f'<p class="meta">Уровень доказательности: {esc(c["evidence_level"])}</p></a>'
        )
    return (f'<style>{NW_CSS}</style>\n<div class="nw">\n<h1>Новости дерматологии</h1>\n'
            + ("\n".join(items) if items else "<p>Карточек пока нет.</p>") + "\n</div>\n")


def render_feed(config, cards):
    site = config["site_url"].rstrip("/")
    items = []
    for c in cards[:30]:
        dt = datetime.datetime.combine(datetime.date.fromisoformat(c["date"]),
                                       datetime.time(6, 0), tzinfo=datetime.timezone.utc)
        link = f"{site}/{c['slug']}/"
        items.append(
            "<item>"
            f"<title>{esc(c['title'])}</title><link>{esc(link)}</link><guid>{esc(link)}</guid>"
            f"<pubDate>{format_datetime(dt)}</pubDate>"
            f"<description>{esc(c['authors_conclusion'])}</description></item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
        "<title>Кожный атлас - новости дерматологии</title>"
        f"<link>{esc(site)}/</link>"
        "<description>Разбор свежих публикаций и руководств по дерматологии</description>"
        "<language>ru</language>" + "".join(items) + "</channel></rss>"
    )


def render_sitemap(config, cards):
    site = config["site_url"].rstrip("/")
    urls = [f"<url><loc>{esc(site)}/</loc></url>"] + [
        f"<url><loc>{esc(site)}/{esc(c['slug'])}/</loc><lastmod>{esc(c['date'])}</lastmod></url>"
        for c in cards
    ]
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(urls) + "</urlset>")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-drafts", action="store_true")
    args = parser.parse_args()

    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    cards = load_cards(args.include_drafts)

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    (DIST / "index.html").write_text(render_index(config, cards), encoding="utf-8")
    for c in cards:
        out = DIST / c["slug"]
        out.mkdir()
        (out / "index.html").write_text(render_card(config, c), encoding="utf-8")
    (DIST / "feed.xml").write_text(render_feed(config, cards), encoding="utf-8")
    (DIST / "sitemap.xml").write_text(render_sitemap(config, cards), encoding="utf-8")
    (DIST / "cards.json").write_text(json.dumps(cards, ensure_ascii=False, indent=2), encoding="utf-8")
    if TILDA_OUT.exists():
        shutil.rmtree(TILDA_OUT)
    TILDA_OUT.mkdir(parents=True)
    for c in cards:
        (TILDA_OUT / f"{c['slug']}.html").write_text(render_tilda_card(config, c), encoding="utf-8")
        seo = {
            "page_address": "/news-" + c["slug"],
            "seo_title": c["title"] + " - Кожный атлас",
            "seo_description": c["authors_conclusion"][:160],
        }
        (TILDA_OUT / f"{c['slug']}.seo.json").write_text(
            json.dumps(seo, ensure_ascii=False, indent=2), encoding="utf-8")
    (TILDA_OUT / "news-list.html").write_text(render_tilda_list(config, cards), encoding="utf-8")
    site = config["site_url"].rstrip("/")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {site}/sitemap.xml\n", encoding="utf-8")
    if config.get("cname"):
        (DIST / "CNAME").write_text(config["cname"] + "\n", encoding="utf-8")

    print(f"Собрано карточек: {len(cards)}. Результат в {DIST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
