# import uuid
# from botbuilder.core import ActivityHandler, TurnContext, ConversationState
# import aiohttp
# import json

# class MyBot(ActivityHandler):
#     def __init__(self, conversation_state: ConversationState):
#         self.conversation_state = conversation_state
#         self.session_id = None

#     async def on_message_activity(self, turn_context: TurnContext):
#         user_message = turn_context.activity.text

#         # Generate session ID if not already set
#         if not self.session_id:
#             self.session_id = str(uuid.uuid4())
#         print("Session ID: ", self.session_id)

#         # Define the API endpoint and payload
#         api_url = "https://dk-fa-ai-dev.azurewebsites.net/api/chatbotResponder?code=FVQY4AF8kdsmUO0A-qrYPRter8Vw8E3Y1WgNjmAWBkluAzFuIoQoHQ%3D%3D"
#         payload = {
#             "question": user_message,
#             "session_id": self.session_id
#         } 

#         headers = {
#             "Content-Type": "application/json"
#         }

#         try:
#             # Send request to API
#             async with aiohttp.ClientSession() as session:
#                 async with session.post(api_url, json=payload, headers=headers) as response:
#                     if response.status == 200:
#                         # Read the API response
#                         response_text = await response.text()
#                         try:
#                             # Parse JSON response
#                             api_response = json.loads(response_text)
#                             answer = api_response.get("answer", "No content available")
#                             citations = api_response.get("citations", [])

#                             # Log the citations for debugging
#                             print("Citations received from API:", citations)

#                             # Check if citations are in the expected list format
#                             if isinstance(citations, list) and citations:
#                                 formatted_citations = "\n".join(
#                                     [f"- {cite}" for cite in citations]
#                                 )
#                             else:
#                                 formatted_citations = "No citations available"

#                             # Format the message to include both answer and citations
#                             message_content = f"**Answer:** {answer}\n\n**Citations:**\n{formatted_citations}"

#                         except json.JSONDecodeError:
#                             message_content = "Failed to parse JSON response"
                        
#                         # Send the formatted response to the user
#                         await turn_context.send_activity(message_content)
#                     else:
#                         # Handle non-200 response
#                         await turn_context.send_activity(f"API Error: {response.status}")
        
#         except Exception as e:
#             # Handle any exceptions that occur during the API call
#             await turn_context.send_activity(f"Error calling API: {str(e)}")

#         # Save conversation state changes
#         await self.conversation_state.save_changes(turn_context)



from botbuilder.core import ActivityHandler, TurnContext, ConversationState
from botbuilder.core.teams import TeamsInfo
import uuid
import aiohttp
import json

class MyBot(ActivityHandler):
    def __init__(self, conversation_state: ConversationState):
        self.conversation_state = conversation_state
        self.session_id = None

    async def on_message_activity(self, turn_context: TurnContext):
        user_message = turn_context.activity.text

        # Generate session ID if not already set
        if not self.session_id:
            self.session_id = str(uuid.uuid4())
        print("Session ID: ", self.session_id)

        try:
            # Fetch the user's profile details from Teams
            user_profile = await TeamsInfo.get_member(turn_context, turn_context.activity.from_property.id)
            username = user_profile.name  # Full name of the user
            email = user_profile.email  # Email address of the user
        except Exception as e:
            # Handle any exceptions if user profile fetch fails
            await turn_context.send_activity(f"Could not retrieve user info: {str(e)}")
            return

        # Define the API endpoint and payload
        api_url = "https://dk-fa-ai-dev.azurewebsites.net/api/chatbotResponder?code=FVQY4AF8kdsmUO0A-qrYPRter8Vw8E3Y1WgNjmAWBkluAzFuIoQoHQ%3D%3D"
        payload = {
            "question": user_message,
            "session_id": self.session_id,
            "username": username,
            "email": email
        }

        headers = {
            "Content-Type": "application/json"
        }

        try:
            # Send request to API
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        # Read the API response
                        response_text = await response.text()
                        try:
                            # Parse JSON response
                            api_response = json.loads(response_text)
                            answer = api_response.get("answer", "No content available")
                            citations = api_response.get("citations", [])

                            # Log the citations for debugging
                            print("Citations received from API:", citations)

                            # Check if citations are in the expected list format
                            if isinstance(citations, list) and citations:
                                formatted_citations = "\n".join(
                                    [f"- {cite}" for cite in citations]
                                )
                            else:
                                formatted_citations = "No citations available"

                            # Format the message to include both answer and citations
                            message_content = f"**Answer:** {answer}\n\n**Citations:**\n{formatted_citations}"

                        except json.JSONDecodeError:
                            message_content = "Failed to parse JSON response"
                        
                        # Send the formatted response to the user
                        await turn_context.send_activity(message_content)
                    else:
                        # Handle non-200 response
                        await turn_context.send_activity(f"API Error: {response.status}")
        
        except Exception as e:
            # Handle any exceptions that occur during the API call
            await turn_context.send_activity(f"Error calling API: {str(e)}")

        # Save conversation state changes
        await self.conversation_state.save_changes(turn_context)
