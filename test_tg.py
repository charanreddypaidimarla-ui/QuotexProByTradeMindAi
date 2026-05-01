import configparser
import requests
import os

config = configparser.ConfigParser()
config.read('settings/config.ini')

tg_token = config['settings'].get('tg_token')
tg_chat_id = config['settings'].get('tg_chat_id')

res = requests.post(
    f"https://api.telegram.org/bot{tg_token}/sendMessage",
    json={"chat_id": tg_chat_id, "text": "Test message from server"},
    timeout=10
)
print(res.json())
