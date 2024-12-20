import asyncio
import json
import time

import psutil
from asgiref.sync import async_to_sync
from channels.consumer import AsyncConsumer
from channels.exceptions import StopConsumer
from channels.generic.websocket import WebsocketConsumer


class observations(WebsocketConsumer):
    def connect(self):
        ip = self.scope["url_route"]["kwargs"].get("ip_address", None)
        if ip:
            self.room_group_name = f"ip_{ip}"
            async_to_sync(self.channel_layer.group_add)(
                self.room_group_name, self.channel_name
            )

            # we need the below code when we stat accepting tokens in websocket connection we just need to uncomment self.accept() and use whats given below
            # ref : https://github.com/django/channels/issues/1369#issuecomment-724299511
            self.accept()
            # self.accept(
            #     "Token"
            # )

    def disconnect(self, close_code):
        # Leave room group
        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name, self.channel_name
        )

    # Receive message from room group
    def send_observation(self, event):
        message = event["message"]

        # Send message to WebSocket
        self.send(text_data=json.dumps(message))


class LoggerConsumer(AsyncConsumer):
    async def websocket_connect(self, event):
        self.connected = True

        await self.send({"type": "websocket.accept"})

        while self.connected:
            await asyncio.sleep(2)
            uptime = (time.time() - psutil.boot_time()) * 1000
            state = {
                "type": "RESOURCE",
                "cpu": f"{psutil.cpu_percent(interval=1.0):.2f}",
                "memory": f"{psutil.virtual_memory().percent:.2f}",
                "uptime": uptime,
                "load": f"{psutil.getloadavg()[1]:.2f}",
            }

            await self.send({"type": "websocket.send", "text": json.dumps(state)})

    async def disconnect(self, event):
        self.connected = False
        raise StopConsumer()
