import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ---------------------------------------------------
    # TODO: REPLACE THESE WITH YOUR REAL TELEGRAM CREDENTIALS
    # ---------------------------------------------------
    API_ID = 39027694  # Replace with integer
    API_HASH = "660b657dc7fc07f9bec949e9349231b7"
    BOT_TOKEN = "8478374852:AAE3LwpNk17B5iELa_iY-AaD3eGs95_HLXA"
    
    # Validation to ensure you didn't forget
    if API_HASH == "YOUR_API_HASH_HERE":
        print("⚠️  WARNING: You haven't set your API credentials in config.py yet!")