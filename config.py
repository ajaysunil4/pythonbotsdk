#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os

class DefaultConfig:
    """ Bot Configuration """

    APP_ID = os.environ.get("MicrosoftAppId", "2dc376e5-3cc8-4be0-ba93-d1d1e279d7d2")
    APP_PASSWORD = os.environ.get("MicrosoftAppPassword", "QMD8Q~We6W68M6TkuzKsmYVemsntQuUIzXXo~dBx")
    TENANT_ID = os.environ.get("MicrosoftTenantID", "3a7dd6e2-0a63-4ec5-bac5-e702961f4ab9")
    
    # APP_ID = os.environ.get("MicrosoftAppId", "")
    # APP_PASSWORD = os.environ.get("MicrosoftAppPassword", "")
    # TENANT_ID = os.environ.get("MicrosoftTenantID", "")