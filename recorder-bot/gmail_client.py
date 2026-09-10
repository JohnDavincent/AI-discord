import base64
import html
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDENTIALS = os.getenv("GMAIL_CREDENTIALS","credentials.json")
TOKEN = os.getenv("GMAIL_TOKEN","token.json")
WIB = ZoneInfo("Asia/Jakarta")

_service = None

def get_service():
    """Login pertama membuka browser lalu selanjutnya pakai token.json"""
    global _service
    if _service is not None:
        return _service

    creds = None
    if os.path.exists(TOKEN):
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN, "w") as f:
            f.write(creds.to_json())

    _service = build("gmail","v1",credentials=creds)
    return _service

@dataclass
class Email:
    id: str
    sender: str
    subject: str
    received_at: datetime
    text: str


def list_message_ids(query:str) -> list[str]:
    """Hanya id, belum isi. messages.list = 5 unit kuota."""
    svc = get_service()
    ids, token = [], None
    while True:
        resp = svc.users().messages().list(
            userId="me", q=query, maxResults=100, pageToken=token
        ).execute()
        ids += [m["id"] for m in resp.get("messages", [])]
        token = resp.get("nextPageToken")
        if not token:
            return ids



def _decode(data: str) -> str:
    data += "=" * (-len(data) % 4)          # base64url sering tanpa padding
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")


def _html_to_text(h: str) -> str:
    h = re.sub(r"<(script|style).*?</\1>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<br\s*/?>|</(p|div|tr|li|h\d)>", "\n", h, flags=re.I)
    h = re.sub(r"<[^>]+>", " ", h)
    h = html.unescape(h)
    h = re.sub(r"[ \t\xa0]+", " ", h)
    return re.sub(r"\n\s*\n+", "\n", h).strip()


def _collect(part, plain:list, htm:list):
    for p in part.get("parts",[]):
        _collect(p,plain,htm)
    data = part.get("body",{}).get("data")
    if not data:
        return

    mime = part.get("mimeType","")
    if mime == "text/plain":
        plain.append(_decode(data))
    elif mime == "text/html":
        htm.append(_decode(data))


def get_email(msg_id:str) -> Email:
    """messages.get = 20 unit kuota."""
    m = get_service().users().messages().get(
        userId = "me", id=msg_id, format="full"
    ).execute()
    hdr = {h["name"].lower() : h["value"] for h in m["payload"].get("headers", [])}
    plain, htm = [], []
    _collect(m["payload"], plain, htm)
    return Email(
        id = m["id"],
        sender = hdr.get("from", ""),
        subject=hdr.get("subject", ""),
        received_at=datetime.fromtimestamp(int(m["internalDate"]) / 1000, tz=timezone.utc),
        text="\n".join(plain) if plain else _html_to_text("\n".join(htm))
    )


def fetch_many(ids: list[str]) -> list[Email]:
    return [get_email(i) for i in ids]
