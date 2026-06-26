# Telegram onboarding bot with Rich Messages

Бот проводит пользователя по этапам:

1. Правила чата
2. PDF/письмо
3. Согласие на обработку персональных данных
4. Генерация ссылки с заявкой на вступление
5. Автоматическое одобрение заявки после проверки прохождения онбординга

## Что добавлено в этой версии

- `sendRichMessage` через прямой вызов Bot API.
- Fallback на обычные HTML-сообщения, если Rich Messages не поддерживаются клиентом/библиотекой/сервером.
- Тексты вынесены в `texts.py`.
- Кнопки остаются обычными `InlineKeyboardButton`.

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Заполните `.env`:

```env
BOT_TOKEN=...
TARGET_CHAT_ID=-100...
USE_RICH_MESSAGES=1
```

## Важно

Бот должен быть администратором группы/супергруппы и иметь право приглашать пользователей.

## Запуск

```bash
python bot.py
```

## Как отключить Rich Messages

В `.env`:

```env
USE_RICH_MESSAGES=0
```

Тогда бот будет отправлять обычные HTML-сообщения.
