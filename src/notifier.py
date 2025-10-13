import requests
from src.config import DISCORD_WEBHOOK
def send_discord(msg:str)->bool:
    if not DISCORD_WEBHOOK: return False
    try:
        r=requests.post(DISCORD_WEBHOOK, json={"content":msg}, timeout=15)
        return r.ok
    except Exception:
        return False
