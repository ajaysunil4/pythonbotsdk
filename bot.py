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
        # Step 1: Check if the activity contains feedback data
        if turn_context.activity.value:
            # Case: User clicked Like or Dislike
            if "feedback" in turn_context.activity.value:
                feedback_type = turn_context.activity.value["feedback"]

                # Send feedback popup with checkboxes based on Like or Dislike
                await self.send_feedback_popup(turn_context, feedback_type)
                return  # Exit to avoid further processing
                
            # Case: User submitted feedback from the popup
            elif "action" in turn_context.activity.value and turn_context.activity.value["action"] == "submit_feedback":
                feedback_type = turn_context.activity.value["feedback_type"]
                feedback_details = turn_context.activity.value.get("feedback_details", [])

                # Save or process feedback details here
                feedback_response = ", ".join(feedback_details)
                await turn_context.send_activity(f"Thank you for your feedback on '{feedback_type}'. Details: {feedback_response}")
                return  # Exit to avoid further processing

        # Step 2: Process user's initial message if no feedback data
        user_message = turn_context.activity.text
        response_text = message_content
        await self.send_response_with_feedback(turn_context, response_text)

        # Save changes to conversation state
        await self.conversation_state.save_changes(turn_context)

            
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
                        await self.send_response_with_feedback(turn_context, message_content)
                    else:
                        await turn_context.send_activity(f"API Error: {response.status}")
        
        except Exception as e:
            await turn_context.send_activity(f"Error calling API: {str(e)}")
        await self.conversation_state.save_changes(turn_context)
        
    async def send_response_with_feedback(self, turn_context: TurnContext, response_text: str, show_feedback_buttons=True):
        # Adaptive Card with conditional feedback buttons
        feedback_card = {
            "type": "AdaptiveCard",
            "body": [
                {
                    "type": "TextBlock",
                    "text": response_text,
                    "wrap": True,
                }
            ],
            "actions": [],
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2"
        }

        if show_feedback_buttons:
            feedback_card["actions"] = [
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
        else:
            feedback_card["body"].append({
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

    async def send_feedback_popup(self, turn_context: TurnContext, feedback_type: str):
        # Define feedback options based on Like or Dislike
        feedback_options = {
            "like": ["Helpful", "Clear", "Relevant"],
            "dislike": ["Not relevant", "Hard to understand", "Inaccurate"]
        }

        popup_card = {
            "type": "AdaptiveCard",
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"Please tell us why you chose to {feedback_type} this response:",
                    "wrap": True,
                    "weight": "Bolder"
                },
                {
                    "type": "Input.ChoiceSet",
                    "id": "feedback_details",
                    "style": "expanded",
                    "isMultiSelect": True,
                    "choices": [{"title": option, "value": option} for option in feedback_options[feedback_type]]
                }
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "Submit Feedback",
                    "data": {
                        "action": "submit_feedback",
                        "feedback_type": feedback_type
                    }
                }
            ],
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2"
        }

        adaptive_card_attachment = Attachment(
            content_type="application/vnd.microsoft.card.adaptive",
            content=popup_card
        )

        # Send the popup Adaptive Card as an activity
        await turn_context.send_activity(
            Activity(
                type=ActivityTypes.message,
                attachments=[adaptive_card_attachment]
            )
        )
