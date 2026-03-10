import json
from channels.generic.websocket import AsyncWebsocketConsumer


class AuctionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'auctions'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        # Expect a JSON message with type 'bid' and data
        data = json.loads(text_data)
        await self.channel_layer.group_send(self.room_group_name, {
            'type': 'auction.message',
            'message': data,
        })

    async def auction_message(self, event):
        message = event['message']
        await self.send(text_data=json.dumps(message))
