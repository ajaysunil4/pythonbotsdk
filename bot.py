# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import ChannelAccount
import aiohttp
import json

class MyBot(ActivityHandler):
    async def on_message_activity(self, turn_context: TurnContext):
        user_message = turn_context.activity.text  # Get the user's message
        sys_id = "6dbf66761b6f7510acf9c9541a4bcb3e"  # The sys_id for the API

        # Call the external API
        api_url = "https://dk-fa-ai-dev.azurewebsites.net/api/messages?code=xjQnL2hYS78iWva_QrpUk3plEg_S84CwaNS6YZNIqJY1AzFu8ROTkg=="
        payload = {
            "question": user_message
        }  # Prepare JSON payload

        headers = {
            "Content-Type": "application/json"
        }  # Set the headers

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        # Try to parse the response as JSON
                        response_text = await response.text()
                        try:
                            api_response = json.loads(response_text)  # Manually parse JSON from string
                            content = api_response.get("answer", "No content available")  # Extract 'content' field
                        except json.JSONDecodeError:
                            content = "Failed to parse JSON response"

                        await turn_context.send_activity(f"{content}")
                    else:
                        await turn_context.send_activity(f"API Error: {response.status}")
        except Exception as e:
            await turn_context.send_activity(f"Error calling API: {str(e)}")
        # await turn_context.send_activity(f"{user_message}")


    async def on_members_added_activity(
        self,
        members_added: ChannelAccount,
        turn_context: TurnContext
    ):
        for member_added in members_added:
            if member_added.id != turn_context.activity.recipient.id:
                await turn_context.send_activity("Hello and welcome!")
