from botbuilder.core import ActivityHandler, TurnContext, ConversationState, MessageFactory
from botbuilder.core.teams import TeamsActivityHandler
from botbuilder.schema import Attachment, Activity, ActivityTypes, SuggestedActions, CardAction, ActionTypes
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


class MyBot(TeamsActivityHandler):
    def __init__(self, conversation_state: ConversationState, table_client, conv_client):
        self.conversation_state = conversation_state
        self.table_client: TableClient = table_client
        self.conv_client = conv_client
        self.sessions = {}

    async def on_message_activity(self, turn_context: TurnContext):
        await turn_context.send_activity(Activity(type=ActivityTypes.typing))
        await asyncio.sleep(1)

        user_message = turn_context.activity.text
        action_payload = turn_context.activity.value 
        try:
            user_profile = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
            username = user_profile.name
            email = user_profile.email
        except Exception as e:
            await turn_context.send_activity(f"Could not retrieve user info: {str(e)}")
            return
        
        # Handle reset context action
        if action_payload and action_payload.get("action") == "reset_context":
            await self.clear_user_context(email, turn_context)
            # await turn_context.send_activity("Your context has been reset. Is there anything else I could assist you with?")
            return
        elif action_payload and action_payload.get("action") == "cancel":
            await turn_context.send_activity("Reset action canceled. Let me know if I can help you with something else.")
            return

        # # Handle other messages like "help"
        # if user_message == "clear context":
        #     await self.send_reset_context_button(turn_context)
        #     return
        
        user_input = turn_context.activity.text.strip().lower()
        if user_input == "clear context":
            await self.send_reset_context_button(turn_context)
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
            feedback_details, other = self.collect_feedback_details(data, feedback)
            feedback_text = ", ".join(feedback_details) if feedback_details else ""
            original_text = data.get("original_text", "")
            logging.info(f"Feedback: {feedback}, Details: {feedback_text}")

            if feedback == 'negative':
                await self.update_feedback_in_table(session_id, "dislike", feedback_text, row_key, other)
                await turn_context.send_activity("Thank you for your feedback!")
            # Send feedback response
            if feedback != "dislike":
                await self.update_feedback_in_table(session_id, feedback, feedback_text, row_key)
            await self.handle_feedback_response(turn_context, feedback, original_text, row_key)
            return
        if turn_context.activity.value and turn_context.activity.value.get("action") == "clear_context":
            await self.send_reset_context_button(turn_context)
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
            data = turn_context.activity.value
            feedback_details = data.get("other_feedback_details", "")
            # await self.send_follow_up_feedback_card(turn_context, original_text, row_key)
            if not feedback_details:
                follow_up_card = self.create_follow_up_card_with_error(original_text, row_key)
                await turn_context.send_activity(Activity(type=ActivityTypes.message, attachments=[follow_up_card]))
            else:
                await self.send_follow_up_feedback_card(turn_context, original_text, row_key)
                await self.close_feedback_form(turn_context)
    async def send_follow_up_feedback_card(self, turn_context: TurnContext, original_text: str, row_key):
        follow_up_card = {
            "type": "AdaptiveCard",
                        "body": [
                            { "type": "TextBlock", "text": "Submit Feedback", "weight": "bolder", "size": "large", "wrap": True },
                            { "type": "TextBlock", "text": "Your feedback will improve this experience.", "isSubtle": True, "wrap": True },
                            { "type": "TextBlock", "text": "Why wasn't the response helpful?", "wrap": True },
                            { "type": "Input.Toggle", "title": "Citations are missing", "id": "citation_miss" },
                            { "type": "Input.Toggle", "title": "Citations are wrong", "id": "citation_wrong" },
                            { "type": "Input.Toggle", "title": "Response is not from my data", "id": "false_response" },
                            { "type": "Input.Toggle", "title": "Inaccurate or irrelevant", "id": "inacc_or_irrel" },
                            { "type": "Input.Toggle", "title": "Others", "id": "others" },
                            { "type": "Input.Text", "id": "other_feedback_details", "isMultiline": True, "isRequired": True, "placeholder": "Please provide more details...", "wrap": True }
                        ],
            "actions": [{ "type": "Action.Submit", "title": "Submit", "data": {"feedback": "negative", "original_text": original_text, "row_key":row_key }
            }],
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2"
        }
        follow_up_card_attachment = Attachment(content_type="application/vnd.microsoft.card.adaptive", content=follow_up_card)
        await turn_context.send_activity(Activity(type=ActivityTypes.message, attachments=[follow_up_card_attachment]))

    def create_follow_up_card_with_error(self, original_text, row_key):
        follow_up_card = {
            "type": "AdaptiveCard",
            "body": [
                { "type": "TextBlock", "text": "Submit Feedback", "weight": "bolder", "size": "large", "wrap": True },
                { "type": "TextBlock", "text": "Your feedback will improve this experience.", "isSubtle": True, "wrap": True },
                { "type": "TextBlock", "text": "Why wasn't the response helpful?", "wrap": True },
                { "type": "Input.Toggle", "title": "Citations are missing", "id": "citation_miss" },
                { "type": "Input.Toggle", "title": "Citations are wrong", "id": "citation_wrong" },
                { "type": "Input.Toggle", "title": "Response is not from my data", "id": "false_response" },
                { "type": "Input.Toggle", "title": "Inaccurate or irrelevant", "id": "inacc_or_irrel" },
                { "type": "Input.Toggle", "title": "Others", "id": "others" },
                { "type": "Input.Text", "id": "other_feedback_details", "isMultiline": True, "isRequired": True, "placeholder": "Please provide more details...", "wrap": True },
                { "type": "TextBlock", "id": "error_message", "text": "This field is required.", "color": "attention", "isVisible": True }
            ],
            "actions": [
                { "type": "Action.Submit", "title": "Submit", "msTeams": { "feedback": { "hide": True } },
                    "data": { "feedback": "negative", "original_text": original_text, "row_key": row_key }
                }
            ],
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2"
        }
        return Attachment(content_type="application/vnd.microsoft.card.adaptive", content=follow_up_card)

    async def close_feedback_form(self, turn_context: TurnContext):
        # Send an empty card to effectively close the form
        empty_card = {
            "type": "AdaptiveCard",
            "body": [],
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2"
        }
        empty_card_attachment = Attachment(content_type="application/vnd.microsoft.card.adaptive", content=empty_card)
        await turn_context.send_activity(Activity(type=ActivityTypes.message, attachments=[empty_card_attachment]))

    async def send_response_with_feedback(self, turn_context: TurnContext, response_text: str, row_key):
        initial_feedback_card = {
            "type": "AdaptiveCard",
            "body": [ { "type": "TextBlock", "text": response_text, "wrap": True },
                { "type": "ActionSet",
                    "actions": [
                        { "type": "Action.Submit", "title": "👍", "data": {"feedback": "like", "original_text": response_text, "row_key": row_key}},
                        { "type": "Action.Submit", "title": "👎", "data": {"feedback": "dislike", "original_text": response_text, "row_key": row_key}}
                    ]
                },
                { "type": "ActionSet",
                    "actions": [
                        { "type": "Action.Submit", "title": "Clear Context", "data": {"action": "clear_context"}}
                    ]
                }
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

    async def update_feedback_in_table(self, session_id, feedback, feedback_text, row_key, other=None):
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
            entity['PartitionKey'] = "Feedback"
            if other:
                entity['other_feedback'] = other
            # Update the entity in Table Storage
            self.table_client.create_entity(entity=entity)
            # return
            # entity = entities[0]
            # entity['feedback'] = feedback
            # entity['feedback_text'] = feedback_text
            # if other:
            #     entity['other_feedback'] = other

            # # Update the entity in Table Storage
            # self.table_client.update_entity(entity=entity, mode=UpdateMode.MERGE)
            logging.info(f"Feedback successfully updated for session {session_id}")
        except Exception as e:
            logging.error(f"Failed to update feedback for session {session_id}: {e}")


    def collect_feedback_details(self, data, feedback_type):
        feedback_details = []
        other = None
        if data.get("citation_miss") == "true":
            feedback_details.append("Citations are missing")
        if data.get("citation_wrong") == "true":
            feedback_details.append("Citations are wrong")
        if data.get("false_response") == "true":
            feedback_details.append("Response is not from my data")
        if data.get("inacc_or_irrel") == "true":
            feedback_details.append("Inaccurate or irrelevant")
        if data.get("others") == "true":
                feedback_details.append(f"Other")
        if data.get("other_feedback_details","") != "":
            other = data.get("other_feedback_details")
        return (feedback_details, other)

    async def send_reset_context_button(self, turn_context: TurnContext):
        reset_context_card = {
            "type": "AdaptiveCard",
            "body": [
                { "type": "TextBlock", "text": "Would you like to reset your session context?", "wrap": True }
            ],
            "actions": [
                { "type": "Action.Submit", "title": "Reset Context", "data": {"action": "reset_context"} },
                { "type": "Action.Submit", "title": "Cancel", "data": {"action": "cancel"} }
            ],
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.2"
        }
        reset_context_card_attachment = Attachment(
            content_type="application/vnd.microsoft.card.adaptive",
            content=reset_context_card
        )
        await turn_context.send_activity(Activity(type=ActivityTypes.message, attachments=[reset_context_card_attachment]))


    async def clear_user_context(self, email, turn_context: TurnContext):
        """
        Clears the user context stored in the session.
        """
        if email in self.sessions:
            del self.sessions[email]
        await turn_context.send_activity("Your context has been reset. Is there anything else I could assist you with?")
