#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os

class DefaultConfig:
    """ Bot Configuration """

    PORT = 3978
    APP_ID = os.environ.get("2dc376e5-3cc8-4be0-ba93-d1d1e279d7d2", "")
    APP_PASSWORD = os.environ.get("QMD8Q~We6W68M6TkuzKsmYVemsntQuUIzXXo~dBx", "")
