from pymongo import MongoClient
from datetime import datetime, UTC
import logging
from config.config import Config
from database.models import ChatHistory

logger = logging.getLogger(__name__)

class DatabaseOperations:
    def __init__(self):
        try:
            self.client = MongoClient(Config.MONGODB_URI)
            self.db = self.client[Config.DB_NAME]
            # Collections
            self.users = self.db['users']
            self.chat_history = self.db['chat_history']
            self.file_metadata = self.db['file_metadata']
            self.search_history = self.db['search_history']
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    async def save_user(self, user_data: dict) -> bool:
        """Save or update user information"""
        try:
            user_id = user_data['user_id']
            existing_user = self.users.find_one({'user_id': user_id})
            
            if existing_user:
                self.users.update_one(
                    {'user_id': user_id},
                    {
                        '$set': {
                            'username': user_data.get('username'),
                            'last_interaction': datetime.now(UTC)
                        }
                    }
                )
            else:
                user_data['created_at'] = datetime.now(UTC)
                user_data['last_interaction'] = datetime.now(UTC)
                self.users.insert_one(user_data)
            
            return True
        except Exception as e:
            logger.error(f"Error saving user: {e}")
            return False

    async def update_user_contact(self, user_id: int, phone_number: str) -> bool:
        """Update user's phone number"""
        try:
            self.users.update_one(
                {'user_id': user_id},
                {
                    '$set': {
                        'phone_number': phone_number,
                        'last_interaction': datetime.now(UTC)
                    }
                }
            )
            return True
        except Exception as e:
            logger.error(f"Error updating user contact: {e}")
            return False

    async def save_chat_history(self, user_id: int, message: str, response: str) -> bool:
        """Save chat interaction"""
        try:
            chat = ChatHistory(
                user_id=user_id,
                message=message,
                response=response
            )
            self.chat_history.insert_one(chat.to_dict())
            
            # Update last interaction
            self.users.update_one(
                {'user_id': user_id},
                {'$set': {'last_interaction': datetime.now(UTC)}}
            )
            return True
        except Exception as e:
            logger.error(f"Error saving chat history: {e}")
            return False

    async def save_file_metadata(self, metadata: dict) -> bool:
        """Save file analysis metadata"""
        try:
            metadata['timestamp'] = datetime.now(UTC)
            self.file_metadata.insert_one(metadata)
            return True
        except Exception as e:
            logger.error(f"Error saving file metadata: {e}")
            return False

    async def save_search_history(self, search_data: dict) -> bool:
        """Save search history"""
        try:
            search_data['timestamp'] = datetime.now(UTC)
            self.search_history.insert_one(search_data)
            return True
        except Exception as e:
            logger.error(f"Error saving search history: {e}")
            return False

    async def get_user_stats(self, user_id: int) -> dict:
        """Get user statistics"""
        try:
            stats = {
                'total_messages': self.chat_history.count_documents({'user_id': user_id}),
                'total_files': self.file_metadata.count_documents({'user_id': user_id}),
                'total_searches': self.search_history.count_documents({'user_id': user_id}),
                'join_date': None
            }
            
            user = self.users.find_one({'user_id': user_id})
            if user:
                stats['join_date'] = user.get('created_at')
            
            return stats
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {}

    async def get_chat_history(self, user_id: int, limit: int = 10) -> list:
        """Get recent chat history for a user"""
        try:
            history = self.chat_history.find(
                {'user_id': user_id}
            ).sort('timestamp', -1).limit(limit)
            return list(history)
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return []

    async def get_user_data(self, user_id: int) -> dict:
        """Get user data from database"""
        try:
            user = self.users.find_one({'user_id': user_id})
            return user if user else {}
        except Exception as e:
            logger.error(f"Error getting user data: {e}")
            return {}

    def close(self):
        """Close database connection"""
        try:
            self.client.close()
            logger.info("Database connection closed")
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")
