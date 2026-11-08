# Раздел новостей derm-atlas.ru

Статичный раздел на поддомене news.derm-atlas.ru. Карточки лежат в cards/*.json, генератор строит из них страницы, ленту RSS и карту сайта. Сайт на Tilda остается как есть, в его меню добавляется ссылка "Новости".

## Как это работает

1. Еженедельная задача (см. WEEKLY_PROMPT.md) готовит карточки как JSON-файлы.
2. Карточка со status "published" попадает на сайт, со status "draft" остается черновиком.
3. После записи карточки в репозиторий GitHub Actions запускает generate.py и публикует результат на GitHub Pages.

## Проверки при сборке

- Обязательные поля: slug, title, date, journal, doc_type, url, method, results, authors_conclusion, our_analysis, evidence_level.
- Тире и двойной дефис в тексте блокируют публикацию карточки.
- Возможные антитезы и упоминания патч-тестов дают предупреждение.

## Схема карточки

Пример лежит в cards/_example-layout.json. Поля method: design, population, endpoint обязательны, sample, comparison, followup по желанию. Поля our_analysis: strengths, limitations, applicability_ru обязательны, funding по желанию.

## Запуск локально

    python3 generate.py --include-drafts
    # открыть dist/index.html в браузере

## Публикация и адрес

1. Репозиторий на GitHub, в настройках Pages источник GitHub Actions. Каждое изменение в main публикуется автоматически.
2. Раздел доступен по адресу https://doctoryankel-eng.github.io/derm-atlas-news/ (он задан в config.json как site_url).
3. В меню Tilda пункт "Новости" ведет на этот адрес.
4. Свой поддомен вида news.derm-atlas.ru потребует DNS, где можно добавить запись CNAME. В панели DNS Tilda есть только записи TXT и MX, поэтому для поддомена домен нужно переносить на другой DNS-сервис.
