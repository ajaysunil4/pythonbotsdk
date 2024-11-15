from botbuilder.core import ActivityHandler, TurnContext, ConversationState
from botbuilder.schema import Attachment, Activity, ActivityTypes
from botbuilder.core.teams.teams_info import TeamsInfo
from azure.data.tables import UpdateMode, TableClient
import urllib.parse
from urllib.parse import quote
import logging
import uuid
import aiohttp
import json
import datetime
import asyncio

class MyBot(ActivityHandler):
    def __init__(self, conversation_state: ConversationState, table_client, conv_client):
        self.conversation_state = conversation_state
        self.table_client: TableClient = table_client
        self.conv_client = conv_client
        self.sessions = {}

    async def on_message_activity(self, turn_context: TurnContext):
        await turn_context.send_activity(Activity(type=ActivityTypes.typing))
        await asyncio.sleep(1)

        user_message = turn_context.activity.text
        try:
            user_profile = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
            username = user_profile.name
            email = user_profile.email
        except Exception as e:
            await turn_context.send_activity(f"Could not retrieve user info: {str(e)}")
            return
        
        # Session handling logic
        if email not in self.sessions:
            self.sessions[email] = {'id': str(uuid.uuid4())}
        else:
            timediff = datetime.datetime.now() - self.sessions[email]['last_query_time']
            if timediff.seconds > 300:
                self.sessions[email]['id'] = str(uuid.uuid4())
        
        self.sessions[email]['last_query_time'] = datetime.datetime.now()
        session_id = self.sessions[email]['id']  # Set session_id for consistent use
        logging.error("Step 1 Completed")
        # Handle feedback if present
        if turn_context.activity.value and "feedback" in turn_context.activity.value:
            data = turn_context.activity.value
            feedback = data.get("feedback")
            row_key = data.get("row_key")
            feedback_details = self.collect_feedback_details(data, feedback)
            feedback_text = ", ".join(feedback_details) if feedback_details else ""
            original_text = data.get("original_text", "")
            logging.info(f"Feedback: {feedback}, Details: {feedback_text}")
            await self.update_feedback_in_table(session_id, feedback, feedback_text, row_key)

            if feedback == 'negative' and not feedback_details[other_feedback]:
                await turn_context.send_activity("Thank you for your feedback!")
            # Send feedback response
            await self.handle_feedback_response(turn_context, feedback, original_text, row_key)
            return
        logging.error("Step 2 Completed")
        # API call setup
        api_url = "https://dk-fa-ai-dev.azurewebsites.net/api/chatbotResponder?code=FVQY4AF8kdsmUO0A-qrYPRter8Vw8E3Y1WgNjmAWBkluAzFuIoQoHQ%3D%3D"
        payload = {
            "question": user_message,
            "session_id": session_id,
            "username": username,
            "email": email
        }

        headers = {"Content-Type": "application/json"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        response_text = await response.text()
                        api_response = json.loads(response_text)
                        res = self.process_api_response(response_text)
                        await self.send_response_with_feedback(turn_context, res, api_response["RowKey"])
                    else:
                        await turn_context.send_activity(f"API Error: {response.status}")
        except Exception as e:
            await turn_context.send_activity(f"Error calling API: {str(e)}")

        await self.conversation_state.save_changes(turn_context)
        logging.error("Step 3 Completed")
    async def handle_feedback_response(self, turn_context: TurnContext, feedback: str, original_text: str, row_key):
        if feedback == "like":
            await turn_context.send_activity("Thank you for your feedback!")
        elif feedback == "dislike":
            await self.send_follow_up_feedback_card(turn_context, original_text, row_key)

    async def send_follow_up_feedback_card(self, turn_context: TurnContext, original_text: str, row_key):
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
                                "isRequired": True,
                                "placeholder": "Please provide more details...",
                                "wrap": True
                            }
                        ],
            "actions": [{
                "type": "Action.Submit",
                "title": "Submit",
                "msTeams": {
               "feedback": {
               "hide": True
               }},
                "data": {"feedback": "negative", "original_text": original_text, "row_key":row_key}
            }],
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2"
        }
        follow_up_card_attachment = Attachment(content_type="application/vnd.microsoft.card.adaptive", content=follow_up_card)
        await turn_context.send_activity(Activity(type=ActivityTypes.message, attachments=[follow_up_card_attachment]))

    async def send_response_with_feedback(self, turn_context: TurnContext, response_text: str, row_key):
        initial_feedback_card = {
            "type": "AdaptiveCard",
            "body": [{"type": "TextBlock", "text": response_text, "wrap": True}],
            "actions": [
                {"type": "Action.Submit", "title": "👍", "data": {"feedback": "like", "original_text": response_text, "row_key":row_key}},
                {"type": "Action.Submit", "title": "👎", "data": {"feedback": "dislike", "original_text": response_text, "row_key":row_key}}
            ],
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2"
        }
        await turn_context.send_activity(Activity(type=ActivityTypes.message, attachments=[Attachment(content_type="application/vnd.microsoft.card.adaptive", content=initial_feedback_card)]))

    def process_api_response(self, response_text):
        base_url = "https://delekus.sharepoint.com/sites/DelekKBArticles/Shared%20Documents/General/Delek%20KB's/"
        
        try:
            api_response = json.loads(response_text)
            answer = api_response.get("answer", "No content available")
            row_key = api_response.get("RowKey")
            citations = api_response.get("citations", [])
            
            if citations:
                formatted_citations = "\n\n**Citations:**\n"
                
                def convert_to_docx(cite):
                    # Decode the citation for easier manipulation
                    decoded_cite = urllib.parse.unquote(cite)
                    # Check the extension and only replace it if not already .docx
                    if not decoded_cite.lower().endswith(".docx"):
                        import re
                        decoded_cite = re.sub(r'(\.[^.]+)$', '.docx', decoded_cite)
                    # Re-encode to make it URL-safe
                    return urllib.parse.quote(decoded_cite)
                
                formatted_citations += "\n".join(
                    [f"- [{urllib.parse.unquote(cite).replace('.pdf', '.docx')}]({base_url}{convert_to_docx(cite)})"
                    for cite in citations]
                )
                return f"{answer}{formatted_citations}"
            
            return answer
        except json.JSONDecodeError:
            return "Failed to parse JSON response"

    async def update_feedback_in_table(self, session_id, feedback, feedback_text, row_key):
        try:
            # Query for the entity using the `session_id` as a filter
            query = f"RowKey eq '{row_key}'"
            entities = list(self.table_client.query_entities(query_filter=query))

            if not entities:
                entities = list(self.conv_client.query_entities(query_filter=query))
                
                if not entities:
                    logging.warning(f"No entity found for session_id: {session_id}. Skipping feedback update.")
                    return
                entity = entities[0]
                entity['feedback'] = feedback
                entity['feedback_text'] = feedback_text

                # Update the entity in Table Storage
                self.table_client.create_entity(entity=entity)
                return
            entity = entities[0]
            entity['feedback'] = feedback
            entity['feedback_text'] = feedback_text

            # Update the entity in Table Storage
            self.table_client.update_entity(entity=entity, mode=UpdateMode.MERGE)
            logging.info(f"Feedback successfully updated for session {session_id}")
        except Exception as e:
            logging.error(f"Failed to update feedback for session {session_id}: {e}")


    def collect_feedback_details(self, data, feedback_type):
        feedback_details = []
        if data.get("citation_miss") == "true":
            feedback_details.append("Citations are missing")
        if data.get("citation_wrong") == "true":
            feedback_details.append("Citations are wrong")
        if data.get("false_response") == "true":
            feedback_details.append("Response is not from my data")
        if data.get("inacc_or_irrel") == "true":
            feedback_details.append("Inaccurate or irrelevant")
        if data.get("others") == "true":
            other_feedback = data.get("other_feedback_details")
            if other_feedback:
                feedback_details.append(f"{other_feedback}")
        if data.get("other_feedback_details"):
            feedback_details.append(f"{other_feedback}")
        return feedback_details
