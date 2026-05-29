---
name: notify-testers
description: Use when the user wants to tell the OneStack dev & testers Telegram group ("Project KVOTAFLOW") about a shipped fix, patch note, changelog, or release — drafts a concise Russian note and sends it as the kvota_error_bot. Triggers include "уведоми тестеров", "напиши тестеру", "отправь записку/патчноут тестеру", "отправь changelog в группу", "сообщи в группу разработки", "notify testers", "ping the dev group", "post to telegram dev group".
allowed-tools:
  - Read
  - Write
  - Bash
---

# notify-testers

Send a patch note / changelog / short update to the **dev & testers** Telegram
group ("Project KVOTAFLOW") as the project bot **`kvota_error_bot`**.

Complements the [`changelog`](../changelog/skill.md) skill: `changelog` drafts
the markdown release entry; this skill pushes a concise, human-friendly note to
the group so testers (e.g. Agasi) know a fix shipped and what to re-check.

Invoke via `/notify-testers`, by trigger phrase, or "use the notify-testers skill".

## Target (do not guess — these are fixed)

| What | Value |
|------|-------|
| Telegram group | **Project KVOTAFLOW** (dev + testers) |
| `chat_id` | `-1003909027498` |
| Sender bot | `kvota_error_bot` (must remain a member of the group) |
| Bot token | `TELEGRAM_BOT_TOKEN` — lives **only** in the `kvota-onestack` VPS container env |

> Telegram bots cannot list the groups they belong to, and the bot's updates go
> to the app webhook (`/api/telegram/webhook`), which only stores per-user
> pairings (`telegram_users`) — **not** group chats. So the `chat_id` above is
> the canonical source; if the group is ever recreated, capture the new id from
> a member and update this table.

## Steps

1. **Draft** the note in user-facing Russian (see format below).
2. **Show the draft to the user and get explicit approval** — this posts to a
   real group with the client's testers. Never send unreviewed.
3. **Send as the bot from the VPS** so the token never leaves the server.
   Base64 the message to avoid all shell/Cyrillic quoting issues:

```bash
# Write the approved note to a UTF-8 file, then:
NOTE_FILE=/path/to/note.txt
B64=$(base64 -w0 "$NOTE_FILE")
ssh beget-kvota "docker exec -i kvota-onestack python -" <<PY
import os, json, base64, urllib.request, urllib.parse
token = os.environ["TELEGRAM_BOT_TOKEN"]
msg = base64.b64decode("$B64").decode("utf-8")
data = urllib.parse.urlencode({"chat_id": "-1003909027498", "text": msg}).encode("utf-8")
url = f"https://api.telegram.org/bot{token}/sendMessage"
try:
    body = json.loads(urllib.request.urlopen(url, data=data, timeout=15).read().decode())
    print("OK", body.get("ok"), "msg_id", body.get("result", {}).get("message_id"))
except urllib.error.HTTPError as e:
    print("HTTPError", e.code, e.read().decode())
PY
```

   - Plain text is sent by default (no `parse_mode`) — robust against `_ * [ ]`
     in feature names. Only add `parse_mode=html`/`md` if you deliberately want
     formatting, and escape accordingly.
   - A successful send returns `OK True msg_id <n>`. Relay the msg_id to the user.

## Note format (Russian, concise)

Keep it scannable — testers read on mobile:

```
🔧 <Заголовок: что и где> (<ссылка на задачу/строку, если есть>)

<1–2 предложения: что было не так и что теперь работает.>

Важно:
• <граничные случаи / что НЕ изменилось, если важно>

Уже на проде (app.kvotaflow.ru). Можно перепроверить: <короткий сценарий>. Спасибо за репорт! 🙌
```

Guidelines:
- One fix per note; lead with the symptom the tester reported, not the code.
- Name the exact place to re-check (page / Incoterms / stage) so QA is fast.
- Mention prod explicitly only after the Deploy workflow is green.
- No internal jargon (table names, function names) — testers aren't devs.

## Future upgrade (optional)

The official `telegram` plugin's `reply` tool can post as a bot without SSH, but
needs one-time setup: put `kvota_error_bot`'s token in
`~/.claude/channels/telegram/.env` (`/telegram:configure <token>`) and relaunch
Claude with `--channels plugin:telegram@claude-plugins-official`. Until that's
set up, the VPS Bot-API path above is the reliable method.
