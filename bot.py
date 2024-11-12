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
        # Check if feedback data is present in the activity
        if turn_context.activity.value and "feedback" in turn_context.activity.value:
            feedback = turn_context.activity.value["feedback"]
            original_text = turn_context.activity.value["original_text"]
            user_id = turn_context.activity.from_property.id

            # Store feedback status in session
            self.sessions[user_id] = {"feedback_given": True}

            # Update the message to remove buttons and show "Thank you" message
            await self.send_response_with_feedback(turn_context, original_text, show_feedback_buttons=False)
            return  # Exit to avoid further processing

        # Process user message as normal
        user_message = turn_context.activity.text
        user_id = turn_context.activity.from_property.id

        # Check if feedback has been given already for this session
        if user_id not in self.sessions:
            self.sessions[user_id] = {"feedback_given": False}
        
        show_feedback_buttons = not self.sessions[user_id]["feedback_given"]

        # Example response text
        response_text = original_text

        # Send the response with feedback buttons or "Thank you" message if feedback was given
        await self.send_response_with_feedback(turn_context, response_text, show_feedback_buttons)
        
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
                        # await turn_context.send_activity(message_content)
                        await self.send_response_with_feedback(turn_context, message_content, show_feedback_buttons)
                    else:
                        await turn_context.send_activity(f"API Error: {response.status}")
        
        except Exception as e:
            await turn_context.send_activity(f"Error calling API: {str(e)}")
        await self.conversation_state.save_changes(turn_context)
        
    async def send_response_with_feedback(self, turn_context: TurnContext, response_text: str, show_feedback_buttons=True):
        # Define an Adaptive Card with a ColumnSet for text and buttons
        feedback_card = {
            "type": "AdaptiveCard",
            "body": [
                {
                    "type": "ColumnSet",
                    "columns": [
                        {
                            "type": "Column",
                            "width": "stretch",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": response_text,
                                    "wrap": True
                                }
                            ]
                        },
                        {
                            "type": "Column",
                            "width": "auto",
                            "items": []
                        }
                    ]
                }
            ],
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2"
        }

        # Add feedback buttons in the right column if feedback hasn't been given
        if show_feedback_buttons:
            feedback_card["body"][0]["columns"][1]["items"] = [
                {
                    "type": "ActionSet",
                    "actions": [
                        {
                            "type": "Action.Submit",
                            "title": "👍",
                            "data": { "feedback": "like", "original_text": response_text }
                        },
                        {
                            "type": "Action.Submit",
                            "title": "👎",
                            "data": { "feedback": "dislike", "original_text": response_text }
                        }
                    ]
                }
            ]
        else:
            # Show "Thank you" message in place of the buttons
            feedback_card["body"][0]["columns"][1]["items"].append({
                "type": "TextBlock",
                "text": "Thank you for your feedback!",
                "wrap": True,
                "horizontalAlignment": "Right"
            })

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
