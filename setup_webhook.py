#!/usr/bin/env python3
"""
Reģistrē Telegram webhook pēc Vercel deploy.
Palaiž vienu reizi: python setup_webhook.py
"""

import sys
import requests

def main():
    token   = input("Telegram token: ").strip()
    url     = input("Vercel URL (piem. https://tavs-projekts.vercel.app): ").strip().rstrip("/")
    secret  = input("Webhook secret (nospied Enter, lai izlaistu): ").strip()

    webhook_url = f"{url}/api/webhook"
    payload = {"url": webhook_url}
    if secret:
        payload["secret_token"] = secret

    resp = requests.post(
        f"https://api.telegram.org/bot{token}/setWebhook",
        json=payload,
        timeout=10,
    )
    data = resp.json()

    if data.get("ok"):
        print(f"\nWebhook iestatīts: {webhook_url}")
        print("Bots ir gatavs!")
    else:
        print(f"\nKļūda: {data}")
        sys.exit(1)

if __name__ == "__main__":
    main()
