# database/models.py
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional, List, Dict, Any
import httpx

API_KEY = "AIzaSyA3zKZ8dsiQBnLgREiRGpe9vymJvIsDDqw"
@dataclass
class User:
    user_id: int
    chat_id: int
    username: Optional[str]
    first_name: str
    created_at: datetime
    last_interaction: datetime
    phone_number: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'chat_id': self.chat_id,
            'username': self.username,
            'first_name': self.first_name,
            'created_at': self.created_at,
            'last_interaction': self.last_interaction,
            'phone_number': self.phone_number
        }

@dataclass
class ChatHistory:
    user_id: int
    message: str
    response: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'message': self.message,
            'response': self.response,
            'timestamp': self.timestamp
        }

@dataclass
class FileMetadata:
    user_id: int
    file_id: str
    file_name: str
    file_type: str
    analysis: str
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'file_id': self.file_id,
            'file_name': self.file_name,
            'file_type': self.file_type,
            'analysis': self.analysis,
            'timestamp': self.timestamp
        }

@dataclass
class SearchHistory:
    user_id: int
    query: str
    results: List[Dict[str, str]]
    summary: str
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'query': self.query,
            'results': self.results,
            'summary': self.summary,
            'timestamp': self.timestamp
        }

def create_user(data: Dict[str, Any]) -> User:
    """Create a User instance from dictionary data"""
    return User(
        user_id=data['user_id'],
        chat_id=data['chat_id'],
        username=data.get('username'),
        first_name=data['first_name'],
        created_at=data.get('created_at', datetime.now(UTC)),
        last_interaction=data.get('last_interaction', datetime.now(UTC)),
        phone_number=data.get('phone_number')
    )

def create_chat_history(data: Dict[str, Any]) -> ChatHistory:
    """Create a ChatHistory instance from dictionary data"""
    return ChatHistory(
        user_id=data['user_id'],
        message=data['message'],
        response=data['response'],
        timestamp=data.get('timestamp', datetime.now(UTC))
    )

def create_file_metadata(data: Dict[str, Any]) -> FileMetadata:
    """Create a FileMetadata instance from dictionary data"""
    return FileMetadata(
        user_id=data['user_id'],
        file_id=data['file_id'],
        file_name=data['file_name'],
        file_type=data['file_type'],
        analysis=data['analysis'],
        timestamp=data.get('timestamp', datetime.now(UTC))
    )

def create_search_history(data: Dict[str, Any]) -> SearchHistory:
    """Create a SearchHistory instance from dictionary data"""
    return SearchHistory(
        user_id=data['user_id'],
        query=data['query'],
        results=data['results'],
        summary=data['summary'],
        timestamp=data.get('timestamp', datetime.now(UTC))
    )

async def fetch_quiz_questions(topic: str):
    """Fetch quiz questions using Google's Gemini API."""
    URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"

    prompt = f"Generate a multiple-choice quiz on {topic}. Provide 5 questions, each with 4 options and the correct answer."
    
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1024
        }
    }
    
    params = {
        "key": API_KEY
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(URL, headers=headers, json=payload, params=params)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None
# database/db_operations.py
from pymongo import MongoClient
from .models import User, ChatHistory
from config.config import Config
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    async def __init__(self):
        self.client = MongoClient(Config.MONGODB_URI)
        self.db = self.client[Config.DB_NAME]
        self.users = self.db.users
        self.chat_history = self.db.chat_history

    async def save_user(self, user: User):
        try:
            return self.users.update_one(
                {'user_id': user.user_id},
                {
                    '$set': {
                        'chat_id': user.chat_id,
                        'username': user.username,
                        'first_name': user.first_name,
                        'phone_number': user.phone_number,
                        'last_interaction': user.last_interaction
                    },
                    '$setOnInsert': {
                        'created_at': user.created_at
                    }
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error saving user: {e}")
            raise

    async def get_user(self, user_id):
        return self.users.find_one({'user_id': user_id})

    async def save_chat_history(self, chat_history: ChatHistory):
        try:
            return self.chat_history.insert_one({
                'user_id': chat_history.user_id,
                'message': chat_history.message,
                'response': chat_history.response,
                'timestamp': chat_history.timestamp
            })
        except Exception as e:
            logger.error(f"Error saving chat history: {e}")
            raise
