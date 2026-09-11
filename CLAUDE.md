# CLAUDE.md

Читай `AGENTS.md`: там команды, нормативные документы, жёсткие правила и роли агентов.
Этот файл только дополняет его.

- Общение с пользователем: русский. Код, коммиты, документация репозитория: английский.
- Пунктуация в тексте для людей: дефис вместо тире, прямые кавычки.
- Субагенты: `.claude/agents/{verifier,implementer,reviewer,critic}.md`. Порядок и правила в
  `AGENTS.md`, раздел Roles. Reviewer и critic получают только issue, spec, diff, тесты и вывод
  CI. Никогда не передавай им рассуждения implementer.
- Перед новым detector: запись в `specs/invariants.md` с Non-claim conditions, потом oracle,
  потом код. Не наоборот.
- Команды префиксовать `rtk` (`rtk uv run pytest`), см. глобальный CLAUDE.md.
