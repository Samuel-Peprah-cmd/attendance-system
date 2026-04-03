import os
import requests
from flask import current_app

class PaystackService:
    BASE_URL = "https://api.paystack.co"

    @classmethod
    def get_headers(cls):
        secret_key = os.environ.get("PAYSTACK_SECRET_KEY")
        return {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json"
        }

    @classmethod
    def initialize_transaction(cls, email, amount_ghs, reference, metadata=None):
        """Creates a checkout link for the frontend"""
        url = f"{cls.BASE_URL}/transaction/initialize"
        
        payload = {
            "email": email,
            "amount": int(amount_ghs * 100), # Convert to pesewas
            "reference": reference,
            "currency": "GHS",
            "channels": ["card", "mobile_money", "bank"], # Allowed channels in Ghana
            "metadata": metadata or {}
        }

        response = requests.post(url, json=payload, headers=cls.get_headers())
        if response.status_code == 200:
            return response.json().get("data")
        return None

    @classmethod
    def verify_transaction(cls, reference):
        """Checks if a payment actually succeeded"""
        url = f"{cls.BASE_URL}/transaction/verify/{reference}"
        response = requests.get(url, headers=cls.get_headers())
        
        if response.status_code == 200:
            return response.json().get("data")
        return None