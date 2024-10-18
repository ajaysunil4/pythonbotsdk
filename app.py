# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import sys
import traceback
import aiohttp
import json
from datetime import datetime
from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import ChannelAccount
from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    TurnContext,
    BotFrameworkAdapter,
)
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.schema import Activity, ActivityTypes

# from bot import MyBot
# from config import DefaultConfig

class MyBot(ActivityHandler):
    async def on_message_activity(self, turn_context: TurnContext):
        user_message = turn_context.activity.text
        sys_id = "6dbf66761b6f7510acf9c9541a4bcb3e"
        api_url = "https://snowassistant.azurewebsites.net/api/user_query"
        payload = {"sys_id": sys_id, "question": user_message}
        headers = {"Content-Type": "application/json"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        response_text = await response.text()
                        try:
                            api_response = json.loads(response_text)
                            content = api_response.get("content", "No content available")
                        except json.JSONDecodeError:
                            content = "Failed to parse JSON response"

                        await turn_context.send_activity(f"{content}")
                    else:
                        await turn_context.send_activity(f"API Error: {response.status}")
        except aiohttp.ClientError as e:
            await turn_context.send_activity(f"Error calling API: {str(e)}")
        except Exception as e:
            await turn_context.send_activity(f"Unexpected error: {str(e)}")



    async def on_members_added_activity(
        self,
        members_added: ChannelAccount,
        turn_context: TurnContext
    ):
        for member_added in members_added:
            if member_added.id != turn_context.activity.recipient.id:
                await turn_context.send_activity("Hello and welcome!")


class DefaultConfig:
    """ Bot Configuration """

    PORT = 3978
    # APP_ID = ""
    # APP_PASSWORD = ""
    APP_ID = "2dc376e5-3cc8-4be0-ba93-d1d1e279d7d2"
    APP_PASSWORD = "QMD8Q~We6W68M6TkuzKsmYVemsntQuUIzXXo~dBx"
    
CONFIG = DefaultConfig()
# Create adapter.
# See https://aka.ms/about-bot-adapter to learn more about how bots work.
SETTINGS = BotFrameworkAdapterSettings(CONFIG.APP_ID, CONFIG.APP_PASSWORD)
ADAPTER = BotFrameworkAdapter(SETTINGS)


# Catch-all for errors.
async def on_error(context: TurnContext, error: Exception):
    # This check writes out errors to console log .vs. app insights.
    # NOTE: In production environment, you should consider logging this to Azure
    #       application insights.
    print(f"\n [on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()

    # Send a message to the user
    await context.send_activity("The bot encountered an error or bug.")
    await context.send_activity(
        "To continue to run this bot, please fix the bot source code."
    )
    # Send a trace activity if we're talking to the Bot Framework Emulator
    if context.activity.channel_id == "emulator":
        # Create a trace activity that contains the error object
        trace_activity = Activity(
            label="TurnError",
            name="on_turn_error Trace",
            timestamp=datetime.utcnow(),
            type=ActivityTypes.trace,
            value=f"{error}",
            value_type="https://www.botframework.com/schemas/error",
        )
        # Send a trace activity, which will be displayed in Bot Framework Emulator
        await context.send_activity(trace_activity)


ADAPTER.on_turn_error = on_error

# Create the Bot
BOT = MyBot()


# Listen for incoming requests on /api/messages
async def messages(req: Request) -> Response:
    # Main bot message handler.
    if "application/json" in req.headers["Content-Type"]:
        body = await req.json()
    else:
        return Response(status=415)

    activity = Activity().deserialize(body)
    auth_header = req.headers["Authorization"] if "Authorization" in req.headers else ""

    response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
    if response:
        return json_response(data=response.body, status=response.status)
    return Response(status=201)


APP = web.Application(middlewares=[aiohttp_error_middleware])
APP.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    try:
        web.run_app(APP)
    except Exception as error:
        raise error
