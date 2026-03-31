"""
Telegram -> ClickUp bot for Vercel webhooks.
Any Telegram text or voice note can become a task in one fixed ClickUp list.
"""

import html
import json
import os
import re
import unicodedata
from http.server import BaseHTTPRequestHandler

import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CLICKUP_API_KEY = os.environ.get("CLICKUP_API_KEY", "")
CLICKUP_LIST_ID = os.environ.get("CLICKUP_LIST_ID", "")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_TRANSCRIBE_MODEL = os.environ.get("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
OPENAI_TASK_MODEL = os.environ.get("OPENAI_TASK_MODEL", "gpt-4o-mini")

CLICKUP_BASE = "https://api.clickup.com/api/v2"
OPENAI_TRANSCRIPT_URL = "https://api.openai.com/v1/audio/transcriptions"

PRIORITY_LABELS = {
    1: "steidzami",
    2: "augsta",
    3: "normala",
    4: "zema",
}

PRIORITY_PATTERNS = (
    (1, (
        r"\b(?:p1|priority\s*1|prioritate\s*1)\b",
        r"\b(?:steidzami|steidzams|steidzama|urgent|asap|critical|kritiska|kritisks|kritiski)\b",
    )),
    (2, (
        r"\b(?:p2|priority\s*2|prioritate\s*2)\b",
        r"\b(?:augsta|augsts|high)\b",
    )),
    (4, (
        r"\b(?:p4|priority\s*4|prioritate\s*4)\b",
        r"\b(?:zema|zems|low)\b",
    )),
    (3, (
        r"\b(?:p3|priority\s*3|prioritate\s*3)\b",
        r"\b(?:normala|normals|normal|medium)\b",
    )),
)

TASK_PREFIX_RE = re.compile(
    r"^\s*(?:/task\b)?\s*"
    r"(?:(?:lu?dzu|please)\s+)?"
    r"(?:(?:izveido|izveidot|pievieno|pieliec|uztaisi|create|add|make)\s+)?"
    r"(?:(?:jaunu|new)\s+)?"
    r"(?:(?:clickup\s+)?(?:uzdevumu|uzdevums|tasku|task))?"
    r"[\s:,-]*",
    re.IGNORECASE,
)

PRIORITY_ONLY_RE = re.compile(
    r"^\s*(?:tas\s+ir\s+)?(?:ar\s+)?(?:prioritat(?:e|i)\s*[:=-]?\s*)?"
    r"(?:p[1-4]|priority\s*[1-4]|prioritate\s*[1-4]|"
    r"steidzami|steidzams|steidzama|urgent|asap|critical|kritiska|kritisks|kritiski|"
    r"augsta|augsts|high|normala|normals|normal|medium|zema|zems|low)"
    r"[\s.!?]*$",
    re.IGNORECASE,
)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return ascii_text.lower().strip()


def escape_html(value: str) -> str:
    return html.escape(value or "", quote=True)


def get_telegram_base() -> str | None:
    if not TELEGRAM_TOKEN:
        return None
    return f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def get_telegram_file_base() -> str | None:
    if not TELEGRAM_TOKEN:
        return None
    return f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}"


def get_missing_required_env() -> list[str]:
    missing = []
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if not CLICKUP_API_KEY:
        missing.append("CLICKUP_API_KEY")
    if not CLICKUP_LIST_ID:
        missing.append("CLICKUP_LIST_ID")
    return missing


def config_error_text() -> str:
    missing = get_missing_required_env()
    if not missing:
        return ""
    return "Trukst Vercel vides mainigie: " + ", ".join(missing)


def priority_response_text(priority: int) -> str:
    mapping = {
        1: "Pieliku ka steidzamu.",
        2: "Pieliku ar augstu prioritati.",
        3: "Pieliku ClickUp.",
        4: "Pieliku ar zemu prioritati.",
    }
    return mapping.get(priority, "Pieliku ClickUp.")


def telegram_api(method: str, payload: dict | None = None) -> dict | None:
    tg_base = get_telegram_base()
    if not tg_base:
        print("Telegram API skipped: TELEGRAM_TOKEN is missing")
        return None
    try:
        resp = requests.post(f"{tg_base}/{method}", json=payload or {}, timeout=15)
        if not resp.ok:
            print(f"Telegram API error {method}: {resp.status_code} {resp.text}")
            return None
        data = resp.json()
        return data if data.get("ok") else None
    except Exception as exc:
        print(f"Telegram API exception {method}: {exc}")
        return None


def openai_chat_completion(payload: dict) -> dict | None:
    if not OPENAI_API_KEY:
        return None

    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=45,
        )
        if not resp.ok:
            print(f"OpenAI chat completion error: {resp.status_code} {resp.text}")
            return None
        return resp.json()
    except Exception as exc:
        print(f"OpenAI chat completion exception: {exc}")
        return None


def send_telegram(chat_id: int, text: str) -> None:
    telegram_api("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    })


def help_text() -> str:
    return (
        "Sveiks! Uzraksti man vienkarsi, kas ir jadara, un es to pieliksu ClickUp.\n\n"
        "Piemers:\n"
        "<code>Salabot login formu. Klienti netiek ieksa. Tas ir steidzami.</code>\n\n"
        "Ja gribi, vari lietot ari strukturizetu formu:\n"
        "<code>/task Nosaukums | Apraksts | steidzami</code>\n\n"
        "Prioritati var ierakstit ar vardiem <code>steidzami</code>, <code>augsta</code>, "
        "<code>normala</code> vai <code>zema</code>.\n\n"
        "Ja Vercel vide ir ielikts <code>OPENAI_API_KEY</code>, es varu ari parformulet "
        "skaidraku nosaukumu un salikt piezimes apraksta. Tas attiecas ari uz balss zinam."
    )


def create_clickup_task(name: str, description: str, priority: int = 3) -> dict | None:
    if not CLICKUP_API_KEY or not CLICKUP_LIST_ID:
        print("ClickUp task creation skipped: missing CLICKUP_API_KEY or CLICKUP_LIST_ID")
        return None

    payload = {
        "name": name,
        "description": description,
        "priority": priority,
    }
    try:
        resp = requests.post(
            f"{CLICKUP_BASE}/list/{CLICKUP_LIST_ID}/task",
            headers={
                "Authorization": CLICKUP_API_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        if not resp.ok:
            print(f"ClickUp error: {resp.status_code} {resp.text}")
            return None
        return resp.json()
    except Exception as exc:
        print(f"ClickUp exception: {exc}")
        return None


def parse_priority(text: str | None) -> int:
    normalized = normalize_text(text or "")
    if not normalized:
        return 3

    for priority, patterns in PRIORITY_PATTERNS:
        if any(re.search(pattern, normalized) for pattern in patterns):
            return priority

    return 3


def looks_like_priority_only(text: str) -> bool:
    return bool(PRIORITY_ONLY_RE.match(normalize_text(text)))


def strip_task_prefix(text: str) -> str:
    cleaned = TASK_PREFIX_RE.sub("", text or "", count=1).strip()
    return cleaned or (text or "").strip()


def cleanup_title(title: str) -> str:
    cleaned = strip_task_prefix(title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:,.")
    if looks_like_priority_only(cleaned):
        return ""
    return cleaned


def shorten_title(text: str, limit: int = 80) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact

    shortened = compact[: limit + 1]
    if " " in shortened:
        shortened = shortened.rsplit(" ", 1)[0]
    return shortened.rstrip(" ,.-") + "..."


def split_title_and_description(text: str) -> tuple[str, str]:
    cleaned = strip_task_prefix(text)

    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if len(lines) >= 2:
        title = cleanup_title(lines[0])
        description = "\n".join(lines[1:]).strip()
        if title:
            return title, description

    if "|" in cleaned:
        parts = [part.strip() for part in cleaned.split("|")]
        title = cleanup_title(parts[0] if parts else "")
        remainder = [part for part in parts[1:] if part]
        if remainder and looks_like_priority_only(remainder[-1]):
            remainder = remainder[:-1]
        if title:
            return title, " | ".join(remainder).strip()

    for separator in (" - ", " -- ", " : ", ". ", "\n"):
        if separator in cleaned:
            title_candidate, description_candidate = cleaned.split(separator, 1)
            title = cleanup_title(title_candidate)
            description = description_candidate.strip()
            if title and description:
                return title, description

    comma_match = re.match(r"^(.{5,90}?),\s+(.+)$", cleaned, re.DOTALL)
    if comma_match:
        title = cleanup_title(comma_match.group(1))
        description = comma_match.group(2).strip()
        if title and description:
            return title, description

    title = cleanup_title(cleaned)
    if title and title != cleaned:
        return title, cleaned

    return shorten_title(cleaned), cleaned if len(cleaned) > 80 else ""


def parse_task_text(text: str) -> tuple[str, str, int]:
    cleaned = (text or "").strip()
    priority = parse_priority(cleaned)
    if looks_like_priority_only(strip_task_prefix(cleaned)):
        return "", "", priority

    title, description = split_title_and_description(cleaned)
    if not title:
        title = shorten_title(strip_task_prefix(cleaned))

    description = description.strip()
    if looks_like_priority_only(description):
        description = ""
    if description == title:
        description = ""

    return title, description, priority


def maybe_rewrite_task_with_ai(raw_text: str) -> tuple[str, str, int] | None:
    if not OPENAI_API_KEY:
        return None

    payload = {
        "model": OPENAI_TASK_MODEL,
        "messages": [
            {
                "role": "developer",
                "content": (
                    "Convert a Telegram message into a ClickUp task in JSON. "
                    "Keep the same language as the user. "
                    "Rewrite the title to be clear and action-oriented, max 80 characters. "
                    "Put extra notes, context, and details into description. "
                    "Do not invent facts. "
                    "Priority rules: 1 urgent/steidzami, 2 high/augsta, 3 normal, 4 low/zema. "
                    "If unclear, use 3."
                ),
            },
            {
                "role": "user",
                "content": raw_text,
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "clickup_task",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "priority": {"type": "integer", "enum": [1, 2, 3, 4]},
                    },
                    "required": ["title", "description", "priority"],
                    "additionalProperties": False,
                },
            },
        },
    }

    response = openai_chat_completion(payload)
    if not response:
        return None

    try:
        content = response["choices"][0]["message"]["content"]
        data = json.loads(content)
        title = (data.get("title") or "").strip()
        description = (data.get("description") or "").strip()
        priority = int(data.get("priority") or 3)
    except Exception as exc:
        print(f"OpenAI task rewrite parse error: {exc}")
        return None

    if not title:
        return None

    priority = max(1, min(4, priority))
    return title[:80].strip(), description, priority


def get_telegram_file(file_id: str) -> tuple[bytes, str, str] | None:
    tg_file_base = get_telegram_file_base()
    if not tg_file_base:
        return None

    file_info = telegram_api("getFile", {"file_id": file_id})
    if not file_info:
        return None

    result = file_info.get("result", {})
    file_path = result.get("file_path")
    if not file_path:
        return None

    try:
        download = requests.get(f"{tg_file_base}/{file_path}", timeout=30)
        if not download.ok:
            print(f"Telegram file download error: {download.status_code} {download.text}")
            return None
        filename = os.path.basename(file_path) or f"{file_id}.ogg"
        return download.content, filename, file_path
    except Exception as exc:
        print(f"Telegram file download exception: {exc}")
        return None


def transcribe_audio(audio_bytes: bytes, filename: str, mime_type: str) -> str | None:
    if not OPENAI_API_KEY:
        return None

    try:
        resp = requests.post(
            OPENAI_TRANSCRIPT_URL,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            data={
                "model": OPENAI_TRANSCRIBE_MODEL,
                "response_format": "text",
                "prompt": "Transcribe Latvian and English task descriptions accurately.",
            },
            files={"file": (filename, audio_bytes, mime_type)},
            timeout=90,
        )
        if not resp.ok:
            print(f"OpenAI transcription error: {resp.status_code} {resp.text}")
            return None

        if "application/json" in resp.headers.get("Content-Type", ""):
            return (resp.json().get("text") or "").strip()

        return resp.text.strip()
    except Exception as exc:
        print(f"OpenAI transcription exception: {exc}")
        return None


def extract_message_text(message: dict) -> tuple[str | None, str | None]:
    text = (message.get("text") or "").strip()
    if text:
        return text, None

    voice = message.get("voice")
    audio = message.get("audio")
    media = voice or audio
    if not media:
        return None, "Atbalstitas ir teksta vai balss zinas."

    if not OPENAI_API_KEY:
        return None, (
            "Balss zinu apstrade nav ieslegta. "
            "Pievieno Vercel vide <code>OPENAI_API_KEY</code>."
        )

    file_id = media.get("file_id")
    if not file_id:
        return None, "Neizdevas atrast balss failu."

    audio_file = get_telegram_file(file_id)
    if not audio_file:
        return None, "Neizdevas lejupieladet balss zinu no Telegram."

    audio_bytes, filename, file_path = audio_file
    mime_type = media.get("mime_type") or ("audio/ogg" if file_path.endswith(".oga") else "audio/mpeg")
    transcript = transcribe_audio(audio_bytes, filename, mime_type)
    if not transcript:
        return None, "Neizdevas parveidot balss zinu teksta."

    caption = (message.get("caption") or "").strip()
    combined_text = transcript if not caption else f"{caption}\n{transcript}"
    return combined_text, None


def send_task_created(
    chat_id: int,
    name: str,
    priority: int,
    task_url: str,
    transcript: str | None = None,
) -> None:
    pieces = [
        priority_response_text(priority),
        "",
        f"Pieliktais uzdevums: <b>{escape_html(name)}</b>",
    ]

    if transcript:
        pieces.extend([
            "",
            f"<i>Balss zinas teksts:</i> {escape_html(shorten_title(transcript, 140))}",
        ])

    pieces.extend([
        "",
        f'<a href="{escape_html(task_url)}">Atvert ClickUp</a>',
    ])
    send_telegram(chat_id, "\n".join(pieces))


def handle_task_creation(chat_id: int, raw_text: str, transcript: str | None = None) -> None:
    rewritten_task = maybe_rewrite_task_with_ai(raw_text)
    if rewritten_task:
        title, description, priority = rewritten_task
    else:
        title, description, priority = parse_task_text(raw_text)

    if not title:
        send_telegram(chat_id, "Nesapratu, ko tiesi pielikt ClickUp. Uzraksti to velreiz vienkarsak.")
        return

    task = create_clickup_task(title, description, priority)
    if task and task.get("url"):
        send_task_created(chat_id, title, priority, task["url"], transcript=transcript)
        return

    send_telegram(chat_id, "Nepiekluvu ClickUp. Parbaudi, vai CLICKUP_API_KEY un CLICKUP_LIST_ID ir pareizi.")


def handle_update(update: dict) -> None:
    if get_missing_required_env():
        print(config_error_text())
        return

    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    if not chat_id:
        return

    text = (message.get("text") or "").strip()
    if text in {"/start", "/help"}:
        send_telegram(chat_id, help_text())
        return

    if text.startswith("/") and not text.startswith("/task"):
        send_telegram(chat_id, help_text())
        return

    extracted_text, error_message = extract_message_text(message)
    if error_message:
        send_telegram(chat_id, error_message)
        return

    if not extracted_text:
        return

    transcript = extracted_text if (message.get("voice") or message.get("audio")) else None
    handle_task_creation(chat_id, extracted_text, transcript=transcript)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        if WEBHOOK_SECRET:
            token_header = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if token_header != WEBHOOK_SECRET:
                self.send_response(403)
                self.end_headers()
                return

        try:
            update = json.loads(body)
            handle_update(update)
        except Exception as exc:
            print(f"Webhook error: {exc}")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def do_GET(self):
        missing = get_missing_required_env()
        status_code = 200 if not missing else 500
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if missing:
            body = json.dumps({
                "status": "config_error",
                "missing": missing,
                "message": config_error_text(),
            }).encode("utf-8")
            self.wfile.write(body)
            return

        self.wfile.write(b'{"status":"Telegram ClickUp bot darbojas"}')

    def log_message(self, format, *args):
        pass
