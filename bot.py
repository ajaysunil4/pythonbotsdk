from botbuilder.core import ActivityHandler, TurnContext, ConversationState
from botbuilder.schema import Attachment, Activity, ActivityTypes
from botbuilder.core.teams.teams_info import TeamsInfo
import uuid
import aiohttp
import json
import datetime

class MyBot(ActivityHandler):
    def __init__(self, conversation_state: ConversationState):
        self.conversation_state = conversation_state
        self.sessions = {}

    async def on_message_activity(self, turn_context: TurnContext):
        if turn_context.activity.value and "feedback" in turn_context.activity.value:
            feedback = turn_context.activity.value["feedback"]
            # original_text = turn_context.activity.value["original_text"]

            # Acknowledge the feedback
            if feedback == "like":
                await turn_context.send_activity("Thank you for your feedback! 👍")
            elif feedback == "dislike":
                await turn_context.send_activity("Thank you for the feedback. We'll work to improve. 👎")
            return
        
        user_message = turn_context.activity.text
        try:
            user_profile = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
            username = user_profile.name
            email = user_profile.email
        except Exception as e:
            await turn_context.send_activity(f"Could not retrieve user info: {str(e)}")
            return
        if email not in self.sessions.keys():
            self.sessions[email] = {}
            self.sessions[email]['id'] = str(uuid.uuid4())
        else:
            timediff = datetime.datetime.now() - self.sessions[email]['last_query_time']
            if timediff.seconds > 300:
                self.sessions[email]['id'] = str(uuid.uuid4())
        self.sessions[email]['last_query_time'] = datetime.datetime.now()
        print("Session ID: ", self.sessions[email])

       

        # Define the API endpoint and payload 
        api_url = "https://dk-fa-ai-dev.azurewebsites.net/api/chatbotResponder?code=FVQY4AF8kdsmUO0A-qrYPRter8Vw8E3Y1WgNjmAWBkluAzFuIoQoHQ%3D%3D"
        payload = {
            "question": user_message,
            "session_id": self.sessions[email]['id'],
            "username": username,
            "email": email
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
                            answer = api_response.get("answer", "No content available")
                            citations = api_response.get("citations", [])

                            print("Citations received from API:", citations)

                            # Include citations only if they are available
                            if isinstance(citations, list) and citations:
                                formatted_citations = "\n\n**Citations:**\n" + "\n".join(
                                    [f"- {cite}" for cite in citations]
                                )
                                message_content = f"{answer}{formatted_citations}"
                            else:
                                message_content = answer

                        except json.JSONDecodeError:
                            message_content = "Failed to parse JSON response"
                        await turn_context.send_activity(message_content)
                        # Step 3: Send the feedback card after sending the answer
                        await self.send_feedback_card(turn_context)
                    else:
                        await turn_context.send_activity(f"API Error: {response.status}")
        
        except Exception as e:
            await turn_context.send_activity(f"Error calling API: {str(e)}")
        await self.conversation_state.save_changes(turn_context)
        
    # Method to send feedback card
    async def send_feedback_card(self, turn_context: TurnContext, response_text: str):
        # Adaptive card with Like and Dislike buttons
        feedback_card = {
            "type": "AdaptiveCard",
            "body": [
                {
                    "type": "TextBlock",
                    "text": response_text,
                    "wrap": True,
                    "weight": "Bolder"
                }
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "👍",
                    "data": { "feedback": "like" }
                },
                {
                    "type": "Action.Submit",
                    "title": "👎",
                    "data": { "feedback": "dislike" }
                }
            ],
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2"
        }

        adaptive_card_attachment = Attachment(
            content_type="application/vnd.microsoft.card.adaptive",
            content=feedback_card
        )

        # Send the Adaptive Card as an activity
        await turn_context.send_activity(
            Activity(
                type=ActivityTypes.message,
                attachments=[adaptive_card_attachment]
            )
        )