import config, requests

def message(response):
    if config.DISCORD_WEBHOOK_URL and config.DISCORD_WEBBHOOK_ENABLED==True:
                    chat_message = {
                        "username": "SkyBot StrategyAlert",
                        "avatar_url": "https://i.imgur.com/4M34hi2.png",
                        "content": f"{response}"
                    }
                    requests.post(config.DISCORD_WEBHOOK_URL, json=chat_message)