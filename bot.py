from botbuilder.core import ActivityHandler, TurnContext, ConversationState
from botbuilder.schema import Attachment, Activity, ActivityTypes
from botbuilder.core.teams.teams_info import TeamsInfo
import uuid
import aiohttp
import json
import datetime
import asyncio

class MyBot(ActivityHandler):
    def __init__(self, conversation_state: ConversationState):
        self.conversation_state = conversation_state
        self.sessions = {}

    async def on_message_activity(self, turn_context: TurnContext):
        
        await turn_context.send_activity(Activity(type=ActivityTypes.typing))
        await asyncio.sleep(1)  # Small delay to simulate thinking time
        
        if turn_context.activity.value:
            data = turn_context.activity.value
            if "feedback" in data:
                feedback = data["feedback"]
                original_text = data["original_text"]
                
                if feedback == "like":
                    feedback_message = "Thank you for your positive feedback!"
                    await turn_context.send_activity(feedback_message)
                    return

                elif feedback == "dislike":
                    # Feedback card with "Others" option and conditional input field
                    follow_up_card = {
                        "type": "AdaptiveCard",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": "Submit Feedback",
                                "weight": "bolder",
                                "size": "large",
                                "wrap": True
                            },
                            {
                                "type": "TextBlock",
                                "text": "Your feedback will improve this experience.",
                                "isSubtle": True,
                                "wrap": True
                            },
                            {
                                "type": "TextBlock",
                                "text": "Why wasn't the response helpful?",
                                "wrap": True
                            },
                            {
                                "type": "Input.Toggle",
                                "title": "Citations are missing",
                                "id": "citation_miss"
                            },
                            {
                                "type": "Input.Toggle",
                                "title": "Citations are wrong",
                                "id": "citation_wrong"
                            },
                            {
                                "type": "Input.Toggle",
                                "title": "Response is not from my data",
                                "id": "false_response"
                            },
                            {
                                "type": "Input.Toggle",
                                "title": "Inaccurate or irrelevant",
                                "id": "inacc_or_irrel"
                            },
                            {
                                "type": "Input.Toggle",
                                "title": "Others",
                                "id": "others"
                            },
                            {
                                "type": "Input.Text",
                                "id": "other_feedback_details",
                                "isMultiline": True,
                                "placeholder": "Please provide more details...",
                                "wrap": True
                            }
                        ],
                        "actions": [
                            {
                                "type": "Action.Submit",
                                "title": "Submit",
                                "data": {
                                    "feedback_type": "negative",
                                    "original_text": original_text
                                }
                            }
                        ],
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "version": "1.2"
                    }

                    follow_up_card_attachment = Attachment(
                        content_type="application/vnd.microsoft.card.adaptive",
                        content=follow_up_card
                    )
                    await turn_context.send_activity(
                        Activity(
                            type=ActivityTypes.message,
                            attachments=[follow_up_card_attachment]
                        )
                    )
                    return

            elif "feedback_type" in data:
                feedback_type = data.get("feedback_type")
                original_text = data.get("original_text", "")
                feedback_details = self.collect_feedback_details(data, feedback_type)

                # If the user hasn't selected anything, return an error message
                if not feedback_details and feedback_type == "negative":
                    await turn_context.send_activity("You haven't provided any feedback. Please select at least one option.")
                    return

                # Generate final feedback message
                final_message = self.finalize_feedback(feedback_type, feedback_details)

                # Send the final feedback response
                await turn_context.send_activity(final_message)
                return

        user_message = turn_context.activity.text
        try:
            user_profile = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
            username = user_profile.name
            email = user_profile.email
        except Exception as e:
            await turn_context.send_activity(f"Could not retrieve user info: {str(e)}")
            return
        
        # Session handling logic
        if email not in self.sessions.keys():
            self.sessions[email] = {}
            self.sessions[email]['id'] = str(uuid.uuid4())
        else:
            timediff = datetime.datetime.now() - self.sessions[email]['last_query_time']
            if timediff.seconds > 300:
                self.sessions[email]['id'] = str(uuid.uuid4())
        self.sessions[email]['last_query_time'] = datetime.datetime.now()

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

                            if isinstance(citations, list) and citations:
                                formatted_citations = "\n\n**Citations:**\n" + "\n".join(
                                    [f"- {cite}" for cite in citations]
                                )
                                message_content = f"{answer}{formatted_citations}"
                            else:
                                message_content = answer
                        except json.JSONDecodeError:
                            message_content = "Failed to parse JSON response"
                        
                        # Send the response along with feedback options
                        await self.send_response_with_feedback(turn_context, message_content)
                    else:
                        await turn_context.send_activity(f"API Error: {response.status}")
        except Exception as e:
            await turn_context.send_activity(f"Error calling API: {str(e)}")

        # Save conversation state
        await self.conversation_state.save_changes(turn_context)

    async def send_response_with_feedback(self, turn_context: TurnContext, response_text: str):
        """Send the response to the user with feedback options."""
        initial_feedback_card = {
            "type": "AdaptiveCard",
            "body": [
                {
                    "type": "TextBlock",
                    "text": response_text,
                    "wrap": True
                },
                {
                    "type": "TextBlock",
                    "text": "",
                    "wrap": True,
                    "separator": True
                }
            ],
            "actions": [
                {
                    "type": "Action.Submit",
                    "title": "👍",
                    "data": {
                        "feedback": "like",
                        "original_text": response_text
                    },
                    "horizontalAlignment": "Right"
                },
                {
                    "type": "Action.Submit",
                    "title": "👎",
                    "data": {
                        "feedback": "dislike",
                        "original_text": response_text
                    },
                    "horizontalAlignment": "Right"
                }
            ],
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2"
        }

        adaptive_card_attachment = Attachment(
            content_type="application/vnd.microsoft.card.adaptive",
            content=initial_feedback_card
        )
        await turn_context.send_activity(
            Activity(
                type=ActivityTypes.message,
                attachments=[adaptive_card_attachment]
            )
        )

    def collect_feedback_details(self, data, feedback_type):
        feedback_details = []
        
        # Add selected feedback reasons
        if data.get("citation_miss"):
            feedback_details.append("Citations are missing")
        if data.get("citation_wrong"):
            feedback_details.append("Citations are wrong")
        if data.get("false_response"):
            feedback_details.append("Response is not from my data")
        if data.get("inacc_or_irrel"):
            feedback_details.append("Inaccurate or irrelevant")
        
        # Check for "Others" feedback
        if data.get("others"):
            other_feedback = data.get("other_feedback_details")
            if other_feedback:
                feedback_details.append(f"Other: {other_feedback}")
        
        return feedback_details

    def finalize_feedback(self, feedback_type, feedback_details):
        if feedback_type == "negative":
            if not feedback_details:
                return "No feedback provided. Please select at least one option."
            else:
                return f"Thank you for your feedback."
