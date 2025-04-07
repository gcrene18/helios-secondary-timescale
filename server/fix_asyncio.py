import asyncio
import sys

# Use the ProactorEventLoop implementation on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())