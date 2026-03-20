#!/usr/bin/env python3
"""AI Spider Worker - run this on each worker node."""
import asyncio
from src.scheduler.worker import main

asyncio.run(main())
