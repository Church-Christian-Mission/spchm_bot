from typing import Any

from app.config import DEFAULT_CHURCH_NAME

FORM_FILTER_ORDER = ["completed", "incomplete", "joined", "default_church", "other_church"]
FORM_FILTERS: dict[str, dict[str, Any]] = {
    "completed": {
        "label": "✅ Заполнены",
        "where": "questionnaire_completed = 1",
        "params": [],
    },
    "incomplete": {
        "label": "⏳ Не заполнены",
        "where": "accepted_rules = 1 AND questionnaire_completed = 0",
        "params": [],
    },
    "joined": {
        "label": "👥 В чате",
        "where": "questionnaire_completed = 1 AND joined = 1",
        "params": [],
    },
    "default_church": {
        "label": "⛪ ХМ",
        "where": "questionnaire_completed = 1 AND church_name = ?",
        "params": [DEFAULT_CHURCH_NAME],
    },
    "other_church": {
        "label": "⛪ Другие",
        "where": (
            "questionnaire_completed = 1 AND church_name IS NOT NULL "
            "AND church_name != ?"
        ),
        "params": [DEFAULT_CHURCH_NAME],
    },
}

STAGE_ORDER = ["all", "start", "rules", "form", "pd", "joined"]
STAGE_LABELS = {
    "all": "👥 Все пользователи",
    "start": "🆕 Без правил",
    "rules": "📜 Правила ✓, анкета нет",
    "form": "📝 Анкета ✓, согласие нет",
    "pd": "🔐 Согласие ✓, не в чате",
    "joined": "✅ Вступили в чат",
}

STAGES: dict[str, dict[str, str]] = {
    "all": {"title": "Все пользователи", "where": "1=1"},
    "start": {"title": "Нажали /start, правила не приняты", "where": "accepted_rules = 0"},
    "rules": {
        "title": "Правила приняты, анкета не заполнена",
        "where": "accepted_rules = 1 AND questionnaire_completed = 0",
    },
    "form": {
        "title": "Анкета заполнена, согласие нет",
        "where": "accepted_rules = 1 AND questionnaire_completed = 1 AND accepted_pd = 0",
    },
    "pd": {
        "title": "Согласие принято, в чат не вступили",
        "where": "accepted_pd = 1 AND joined = 0",
    },
    "joined": {"title": "Вступили в чат", "where": "joined = 1"},
}
