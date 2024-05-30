import config, requests
import logging
from requests.exceptions import SSLError

def message(response):
    try:
        if config.DISCORD_WEBHOOK_URL and config.DISCORD_WEBBHOOK_ENABLED==True:
                        chat_message = {
                            "username": "SkyBot StrategyAlert",
                            "avatar_url": "https://i.imgur.com/4M34hi2.png",
                            "content": f"{response}"
                        }
                        requests.post(config.DISCORD_WEBHOOK_URL, json=chat_message)
    except SSLError as e:
            logging.error(f"Failed to send Discord message: {e}")



#import config, requests, time
#from threading import Timer

#class MessageBuffer:
#    def __init__(self, send_interval=60, max_messages=10):
#        self.buffer = []
#        self.send_interval = send_interval
#        self.max_messages = max_messages
#        self.message_count = 0
#        self.timer = Timer(self.send_interval, self.send_messages)
#        self.timer.start()
#
#    def add_message(self, response):
#        self.buffer.append(response)
#        self.message_count += 1
#        if self.message_count >= self.max_messages:
#            self.send_messages()
#
#    def send_messages(self):
#        if config.DISCORD_WEBHOOK_URL and config.DISCORD_WEBBHOOK_ENABLED==True and self.buffer:
#            chat_message = {
#                "username": "SkyBot StrategyAlert",
#                "avatar_url": "https://i.imgur.com/4M34hi2.png",
#                "content": "\n".join(self.buffer)
#            }
#            requests.post(config.DISCORD_WEBHOOK_URL, json=chat_message)
#            self.buffer = []
#            self.message_count = 0
#        self.timer = Timer(self.send_interval, self.send_messages)
#        self.timer.start()

#message_buffer = MessageBuffer()

#def message(response):
#    message_buffer.add_message(response)