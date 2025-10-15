import os
import json
import urllib.request

def _post(url, payload, headers):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            _ = r.read()
            return True
    except Exception as e:
        print(f"[notifier] POST feilet: {e}")
        return False

def send_discord(message: str):
    """Sender melding til Discord.
       1) Hvis DISCORD_WEBHOOK finnes → bruk webhook
       2) Ellers hvis BOT-token + DM user id finnes → send DM
       3) Ellers: bare print (bygg feiler ikke)
    """
    webhook = os.getenv("DISCORD_WEBHOOK")
    token = os.getenv("DISCORD_BOT_TOKEN")
    user_id = os.getenv("DISCORD_DM_USER_ID")

    if webhook:
        ok = _post(webhook, {"content": message}, {"Content-Type":"application/json"})
        print("[notifier] webhook OK" if ok else "[notifier] webhook FAIL")
        return ok

    if token and user_id:
        try:
            # 1) Opprett (eller hent) DM kanal
            req = urllib.request.Request(
                "https://discord.com/api/v10/users/@me/channels",
                data=json.dumps({"recipient_id": user_id}).encode("utf-8"),
                headers={"Authorization": f"Bot {token}", "Content-Type":"application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                dm = json.loads(r.read().decode("utf-8"))
                ch_id = dm["id"]
            # 2) Send melding
            req2 = urllib.request.Request(
                f"https://discord.com/api/v10/channels/{ch_id}/messages",
                data=json.dumps({"content": message}).encode("utf-8"),
                headers={"Authorization": f"Bot {token}", "Content-Type":"application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req2, timeout=15) as r2:
                _ = r2.read()
            print("[notifier] DM OK")
            return True
        except Exception as e:
            print(f"[notifier] DM FAIL: {e}")
            return False

    print("[notifier] Ingen webhook/BOT secrets – printer melding:\n" + message)
    return True
