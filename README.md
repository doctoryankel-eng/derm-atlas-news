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

## Подключение домена

1. Создать репозиторий на GitHub, загрузить эти файлы, в настройках включить Pages с источником GitHub Actions.
2. В DNS домена derm-atlas.ru добавить запись CNAME: news указывает на <логин GitHub>.github.io.
3. В меню Tilda добавить пункт "Новости" со ссылкой https://news.derm-atlas.ru.
