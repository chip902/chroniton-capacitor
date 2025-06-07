"""
Microsoft Graph Client Adapter

This module provides a compatibility layer for different versions of the Microsoft Graph SDK.
"""

from typing import Dict, Any, Optional

import requests


class GraphClient:
    """
    A simple GraphClient implementation that works without relying on msgraph-core structure
    """

    def __init__(self, credentials: str):
        """
        Initialize the GraphClient with an access token.

        Args:
            credentials: Access token to authenticate with Microsoft Graph API
        """
        self.access_token = credentials
        self.base_url = "https://graph.microsoft.com/v1.0"

    async def get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Make a GET request to the Microsoft Graph API.

        Args:
            endpoint: The API endpoint (e.g., "/me/calendars")
            params: Optional query parameters

        Returns:
            The JSON response from the API
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    async def post(self, endpoint: str, json_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Make a POST request to the Microsoft Graph API.

        Args:
            endpoint: The API endpoint (e.g., "/me/calendars")
            json_data: The JSON data to send in the request body

        Returns:
            The JSON response from the API
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers, json=json_data)
        response.raise_for_status()
        return response.json()

    async def patch(self, endpoint: str, json_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Make a PATCH request to the Microsoft Graph API.

        Args:
            endpoint: The API endpoint (e.g., "/me/calendars/{id}")
            json_data: The JSON data to send in the request body

        Returns:
            The JSON response from the API
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        response = requests.patch(url, headers=headers, json=json_data)
        response.raise_for_status()
        return response.json()

    async def delete(self, endpoint: str) -> None:
        """
        Make a DELETE request to the Microsoft Graph API.

        Args:
            endpoint: The API endpoint (e.g., "/me/events/{id}")
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        response = requests.delete(url, headers=headers)
        response.raise_for_status()
