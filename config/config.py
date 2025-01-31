from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    # Bot Configuration
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    
    # MongoDB Configuration
    MONGODB_URI = os.getenv('MONGODB_URI')
    DB_NAME = 'telegram_bot'
    
    # Gemini Configuration
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

    # SerpApi Configuration
    SERPAPI_KEY = os.getenv('SERPAPI_KEY')
