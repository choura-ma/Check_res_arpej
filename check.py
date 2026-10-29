"""Check ARPEJ residences and email the ones that weren't there on the previous run."""
import json
import os
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

import requests

API_URL = "https://www.arpej.fr/wp-json/sn/residences"
PARAMS = {
    "lang": "fr",
    "display": "map",
    "related_city[]": "52524",
    "price_from": "0",
    "price_to": "1000",
    "show_if_full": "false",        # only residences with free rooms
    "show_if_colocations": "false",
}
STATE_FILE = Path("seen.json")


def fetch_residences():
    r = requests.get(
        API_URL,
        params=PARAMS,
        headers={"User-Agent": "Mozilla/5.0 (residence watcher)"},
        timeout=60,
    )
    r.raise_for_status()
    out = {}
    for res in r.json().get("residences", []):
        extra = res.get("extra_data") or {}
        out[str(res["ID"])] = {
            "title": " ".join(res.get("title", "").split()),
            "link": res.get("link", ""),
            "city": extra.get("city", ""),
            "price_from": extra.get("price_from", ""),
            "available_rooms": extra.get("available_rooms"),
            "is_new": extra.get("is_new", False),
        }
    return out


def send_email(subject, body):
    user = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    # MAIL_TO can hold several addresses separated by commas
    recipients = [a.strip() for a in (os.environ.get("MAIL_TO") or user).split(",") if a.strip()]
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, password)
        s.sendmail(user, recipients, msg.as_string())


def describe(r):
    lines = [f"- {r['title']} ({r['city']})"]
    if r["price_from"]:
        lines.append(f"  À partir de {float(r['price_from']):.0f} €/mois")
    if r["available_rooms"] is not None:
        lines.append(f"  Logements disponibles : {r['available_rooms']}")
    if r["is_new"]:
        lines.append("  Nouvelle résidence")
    lines.append(f"  {r['link']}")
    return "\n".join(lines)


def main():
    current = fetch_residences()
    first_run = not STATE_FILE.exists()
    previous = {} if first_run else json.loads(STATE_FILE.read_text())

    new_ids = [i for i in current if i not in previous]

    if first_run:
        body = "Surveillance démarrée. Résidences actuellement listées :\n\n"
        body += "\n\n".join(describe(r) for r in current.values()) or "(aucune)"
        send_email(f"ARPEJ : surveillance démarrée ({len(current)} résidences)", body)
    elif new_ids:
        body = "\n\n".join(describe(current[i]) for i in new_ids)
        body += "\n\nPage : https://www.arpej.fr/fr/nos-residences/?related_city=52524"
        send_email(f"ARPEJ : {len(new_ids)} nouvelle(s) résidence(s)", body)

    print(f"{len(current)} listed, {len(new_ids)} new")
    STATE_FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
