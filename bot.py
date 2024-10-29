import uuid
from botbuilder.core import ActivityHandler, TurnContext, ConversationState
from botbuilder.schema import ChannelAccount
import aiohttp
import json

class MyBot(ActivityHandler):
    def __init__(self, conversation_state: ConversationState):
        self.conversation_state = conversation_state
        self.session_id = None

    async def on_message_activity(self, turn_context: TurnContext):
        user_message = turn_context.activity.text

        if not self.session_id:
            self.session_id = str(uuid.uuid4())
        print("Session ID: ",self.session_id)
        api_url = "https://dk-fa-ai-dev.azurewebsites.net/api/chatbotResponder?code=FVQY4AF8kdsmUO0A-qrYPRter8Vw8E3Y1WgNjmAWBkluAzFuIoQoHQ%3D%3D"
        payload = {
            "question": user_message,
            "session_id": self.session_id 
        } 

        headers = {
            "Content-Type": "application/json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, headers=headers) as response:
                    if response.status == 200:

                        response_text = await response.text()
                        try:
                            api_response = json.loads(response_text) 
                            content = api_response.get("answer", "No content available")
                        except json.JSONDecodeError:
                            content = "Failed to parse JSON response"

                        await turn_context.send_activity(f"{content}")
                    else:
                        await turn_context.send_activity(f"API Error: {response.status}")
        except Exception as e:
            await turn_context.send_activity(f"Error calling API: {str(e)}")

        await self.conversation_state.save_changes(turn_context)
