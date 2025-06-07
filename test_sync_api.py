#!/usr/bin/env python
"""
Test script to verify sync API endpoints for agent registration and heartbeat.
This script simulates what the remote agent would do when connecting to the server.
"""

import asyncio
import aiohttp
import json
import sys
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('sync_api_test')

# Default server URL (can be overridden via command line)
SERVER_URL = "http://ark:8008"


async def test_sync_api(server_url):
    """Test the sync API endpoints."""
    logger.info(f"Testing sync API at {server_url}")

    async with aiohttp.ClientSession() as session:
        # 1. Test agent registration endpoint
        agent_data = {
            "name": "Test Agent",
            "version": "1.0.0",
            "network_name": "test-network",
            "hostname": "test-host",
            "capabilities": ["calendar_sync", "event_notifications"],
            "status": "online",
            "last_seen": datetime.now().isoformat()
        }

        # Test /sync/agents endpoint (should be accessible now that we fixed the router prefix)
        registration_url = f"{server_url}/sync/agents"
        logger.info(f"Testing agent registration at: {registration_url}")

        try:
            async with session.post(registration_url, json=agent_data) as response:
                if response.status == 200:
                    result = await response.json()
                    agent_id = result.get("id")
                    logger.info(
                        f"✅ Agent registration successful! Received agent_id: {agent_id}")

                    # 2. Now test heartbeat endpoint with the received agent_id
                    if agent_id:
                        heartbeat_url = f"{server_url}/sync/agents/{agent_id}/heartbeat"
                        heartbeat_data = {
                            "status": "online",
                            "last_sync": datetime.now().isoformat(),
                            "events_synced": 0
                        }

                        logger.info(
                            f"Testing agent heartbeat at: {heartbeat_url}")
                        async with session.post(heartbeat_url, json=heartbeat_data) as heartbeat_response:
                            if heartbeat_response.status == 200:
                                logger.info("✅ Heartbeat successful!")
                                heartbeat_result = await heartbeat_response.json()
                                logger.info(
                                    f"Heartbeat response: {json.dumps(heartbeat_result, indent=2)}")
                            else:
                                logger.error(
                                    f"❌ Heartbeat failed with status {heartbeat_response.status}")
                                if heartbeat_response.status == 404:
                                    logger.error(
                                        "404: Heartbeat endpoint not found!")
                                text = await heartbeat_response.text()
                                logger.error(f"Response: {text}")
                else:
                    logger.error(
                        f"❌ Agent registration failed with status {response.status}")
                    if response.status == 404:
                        logger.error(
                            "404: Registration endpoint not found! Check if sync_router is properly included in main.py")
                    text = await response.text()
                    logger.error(f"Response: {text}")
        except aiohttp.ClientError as e:
            logger.error(f"❌ Connection error: {e}")
            logger.error("Check if the server is running and accessible")


async def main():
    """Main entry point."""
    # Get server URL from command line if provided
    server_url = sys.argv[1] if len(sys.argv) > 1 else SERVER_URL
    await test_sync_api(server_url)

if __name__ == "__main__":
    asyncio.run(main())
