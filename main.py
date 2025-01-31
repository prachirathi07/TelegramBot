from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from pymongo import MongoClient
from datetime import datetime, UTC
from dotenv import load_dotenv
import os
import logging
import sys
from services.gemini_service import GeminiService
from database.models import ChatHistory
from services.web_search import WebSearchService
from services.file_handler import FileHandler
from config.config import Config
from database.db_operations import DatabaseOperations
import speech_recognition as sr
import requests
import smtplib
import asyncio
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, Optional, Any, List
import random

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load and verify environment variables
load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


if not MONGODB_URI or not TELEGRAM_TOKEN:
    logger.error("Missing environment variables!")
    sys.exit(1)

# MongoDB setup
try:
    client = MongoClient(Config.MONGODB_URI, serverSelectionTimeoutMS=5000)
    # Test the connection
    client.server_info()
    db = client[Config.DB_NAME]
    users_collection = db['users']
    logger.info("MongoDB connection successful!")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    raise

# Add to your global variables
gemini_service = GeminiService()
web_search_service = WebSearchService()
file_handler = FileHandler()
db_ops = DatabaseOperations()

class DatabaseManager:
    """Handles all database operations."""
    def __init__(self):
        self.client = AsyncIOMotorClient(Config.MONGODB_URI)
        self.db = self.client['telegram_bot']
        self.users = self.db.users
        self.chat_history = self.db.chat_history

    async def save_user(self, user_data: Dict[str, Any]) -> None:
        """Save user data to database."""
        await self.users.update_one(
            {"user_id": user_data["user_id"]},
            {"$set": user_data},
            upsert=True
        )

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve user data from database."""
        user_data = await self.users.find_one({"user_id": user_id})
        return user_data  # Ensure this returns a valid user object or None

    async def save_chat_history(self, user_id: int, message: str, response: str):
        """Save chat history to the database."""
        chat_data = {
            "user_id": user_id,
            "user_message": message,
            "bot_response": response,
            "timestamp": datetime.now(UTC)
        }
        await self.chat_history.insert_one(chat_data)

async def format_message(text: str) -> str:
    """Format message with emojis and better structure"""
    formatted_text = text

    # Add section breaks for lists if they exist
    if any(line.strip().startswith(('-', '•', '*', '1.')) for line in text.split('\n')):
        formatted_text = formatted_text.replace('\n-', '\n• ')
        formatted_text = formatted_text.replace('\n*', '\n• ')

    # Handle bold headings correctly
    bold_headings = ['Note:', 'Important:', 'Key point:', 'Remember:', 'Warning:']
    for phrase in bold_headings:
        if phrase in formatted_text:
            formatted_text = formatted_text.replace(phrase, f"\n\n<b>{phrase}</b>\n")
    
    # Add section emojis based on content
    lower_text = formatted_text.lower()
    if 'example' in lower_text:
        formatted_text = "💡 " + formatted_text
    elif any(word in lower_text for word in ['error', 'warning', 'caution']):
        formatted_text = "⚠️ " + formatted_text
    elif any(word in lower_text for word in ['success', 'complete', 'done']):
        formatted_text = "✅ " + formatted_text
    else:
        formatted_text = "🤖 " + formatted_text

    # Add line breaks for better readability
    formatted_text = formatted_text.replace('\n', '\n\n')
    
    return formatted_text

async def start_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    user_data = {
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_interaction": datetime.now(UTC)
    }
    
    # Check if the user is already registered
    registration_msg = ""
    existing_user = db['users'].find_one({"user_id": user.id})

    if not existing_user:
        # Register the user in the database
        db['users'].insert_one(user_data)
        registration_msg = "You have been successfully registered! 🎉"
    

    # Request contact
    contact_button = KeyboardButton("Share Contact", request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True)
    
    welcome_msg = f"{registration_msg}\n\nWelcome {user.first_name}! You are already registered as {user.username} ✨!"
    await update.message.reply_text(welcome_msg, reply_markup=reply_markup)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle contact sharing."""
    contact = update.effective_message.contact
    user_id = update.effective_user.id

    if contact and contact.user_id == user_id:
        # Save the user's phone number in the database
        users_collection.update_one(
            {'user_id': user_id},
            {'$set': {'phone_number': contact.phone_number}}
        )
        await update.message.reply_text("Contact information saved successfully!")
    else:
        await update.message.reply_text("Please share your own contact information.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages."""
    user_message = update.message.text
    response = await get_gemini_response(user_message)
    await update.message.reply_text(response)

    # Save chat history
    await db_ops.save_chat_history(update.effective_user.id, user_message, response)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        photo = update.message.photo[-1]  # Get the largest photo
        
        # Show processing message
        processing_msg = await update.message.reply_text(
            "🔄 Processing your image... Please wait."
        )
        
        try:
            # Download photo
            file = await context.bot.get_file(photo.file_id)
            photo_data = await file.download_as_bytearray()
            
            # Analyze with Gemini
            analysis = await gemini_service.analyze_image(photo_data)
            
            # Format the analysis
            formatted_analysis = await format_message(analysis)
            
            # Save metadata
            await db_ops.save_file_metadata({
                'user_id': user_id,
                'file_id': photo.file_id,
                'file_name': f"photo_{photo.file_id}",
                'file_type': 'photo',
                'analysis': formatted_analysis,
                'timestamp': datetime.now(UTC)
            })
            
            await update.message.reply_text(
                formatted_analysis
            )
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            await update.message.reply_text(
                "❌ Sorry, I couldn't analyze this image. Please try again."
            )
        finally:
            # Clean up processing message
            await processing_msg.delete()
            
    except Exception as e:
        logger.error(f"Error in photo handler: {e}")
        await update.message.reply_text(
            "❌ Sorry, something went wrong. Please try again later."
        )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        document = update.message.document
        file_ext = os.path.splitext(document.file_name)[1].lower()
        
        if file_ext not in ['.pdf', '.PDF']:
            await update.message.reply_text(
                "⚠️ Sorry, I can only process PDF files at the moment."
            )
            return

        # Show processing message
        processing_msg = await update.message.reply_text(
            "🔄 Processing your file... Please wait."
        )
        
        try:
            # Download file
            file = await context.bot.get_file(document.file_id)
            file_path = f"downloads/{document.file_name}"
            await file.download_to_drive(file_path)
            
            # Process with file handler
            analysis = await file_handler.process_file(file_path, file_ext)
            
            # Format the analysis
            formatted_analysis = await format_message(analysis)
            
            # Save metadata
            await db_ops.save_file_metadata({
                'user_id': user_id,
                'file_id': document.file_id,
                'file_name': document.file_name,
                'file_type': file_ext,
                'analysis': formatted_analysis,
                'timestamp': datetime.now(UTC)
            })
            
            await update.message.reply_text(
                formatted_analysis
            )
            
        except Exception as e:
            logger.error(f"Error processing file: {e}")
            await update.message.reply_text(
                "❌ Sorry, I couldn't analyze this file. Please try again."
            )
        finally:
            # Clean up processing message
            await processing_msg.delete()
            
    except Exception as e:
        logger.error(f"Error in document handler: {e}")
        await update.message.reply_text(
            "❌ Sorry, something went wrong. Please try again later."
        )

async def handle_websearch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text(
                "ℹ️ Please provide a search query.\nExample: /websearch artificial intelligence"
            )
            return

        query = ' '.join(context.args)
        user_id = update.effective_user.id
        username = update.effective_user.username
        
        # Show searching message
        search_msg = await update.message.reply_text(
            "🔍 Searching the web... Please wait."
        )
        
        try:
            # Perform web search
            search_data = await web_search_service.search(query)
            
            # Format and send summary
            summary_text = f"Search results for: {query}\n\n"
            summary_text += await format_message(search_data['summary'])
            await update.message.reply_text(
                summary_text
            )
            
            # Send results
            if search_data['results']:
                for i, result in enumerate(search_data['results'], 1):
                    result_text = f"{i}. {result['title']}\n"
                    if result['link']:
                        result_text += f"🔗 {result['link']}\n"
                    result_text += f"{result['snippet']}\n"
                    
                    await update.message.reply_text(
                        result_text,
                        disable_web_page_preview=True
                    )
            
            # Save to MongoDB
            db['search_history'].insert_one({
                'user_id': user_id,
                'username': username,
                'query': query,
                'results': search_data,
                'timestamp': datetime.now(UTC)
            })
            
        except Exception as e:
            logger.error(f"Search processing error: {e}")
            await update.message.reply_text(
                "❌ An error occurred while processing the search results."
            )
            
    except Exception as e:
        logger.error(f"Error in web search: {e}")
        await update.message.reply_text(
            "❌ Sorry, I couldn't complete the web search. Please try again later."
        )

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        voice = update.message.voice

        # Download the voice message
        file = await context.bot.get_file(voice.file_id)
        file_path = f"downloads/voice_{user_id}.ogg"
        await file.download_to_drive(file_path)

        # Convert OGG to WAV (if necessary)
        wav_file_path = f"downloads/voice_{user_id}.wav"
        os.system(f"ffmpeg -i {file_path} {wav_file_path}")

        # Recognize speech using SpeechRecognition
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_file_path) as source:
            audio = recognizer.record(source)  # Read the entire audio file

        # Convert speech to text
        text = recognizer.recognize_google(audio)
        await update.message.reply_text(f"You said: {text}")

    except Exception as e:
        logger.error(f"Error processing voice message: {e}")
        await update.message.reply_text("❌ Sorry, I couldn't understand the voice message.")

async def get_gemini_response(user_message):
    """Call the Gemini API to get a response from Gemini 1.5 Flash."""
    url = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json={"contents": [{"parts": [{"text": user_message}]}]},
            params={"key": GEMINI_API_KEY}  # Send API key as a parameter
        )
        
        if response.status_code == 200:
            return response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "No response")
        else:
            return f"Error: {response.status_code}, {response.text}"

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = (
        "Welcome to the Bot! Here are some commands you can use:\n\n"
        "/start - Register and start using the bot.\n"
        "Start Chat - Begin a conversation with the bot.\n"
        "Analyze Image - Send an image for analysis.\n"
        "Analyze PDF - Send a PDF for analysis.\n"
        "/websearch - Perform a web search.\n"
        "About - Learn more about this bot.\n"
        "Share Contact - Share your contact information with the bot."
    )
    await update.message.reply_text(help_text)

async def fetch_quiz_questions(topic: str) -> List[Dict[str, Any]]:
    """Fetch quiz questions based on the topic from the Gemini API."""
    url = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"
    prompt = f"Generate a multiple-choice quiz on {topic}. Provide 5 questions, each with 4 options and the correct answer."

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                params={"key": GEMINI_API_KEY},
                timeout=10.0
            )

            # Log the response status and content
            logger.info(f"API Response Status: {response.status_code}")
            logger.info(f"API Response Content: {response.text}")

            if response.status_code != 200:
                logger.error(f"API Error: {response.status_code}, {response.text}")
                return []

            response_data = response.json()
            logger.info(f"API Response: {response_data}")
            questions = parse_quiz_questions(response_data)  # Ensure this function is implemented correctly
            return questions if questions else []

    except Exception as e:
        logger.error(f"Error fetching questions: {e}")
        return []

def parse_quiz_questions(response_data) -> List[Dict[str, Any]]:
    """Parse the API response to extract quiz questions."""
    questions = []
    
    # Check if candidates list is not empty
    if not response_data.get("candidates"):
        logger.error("No candidates found in the response.")
        return questions  # Return an empty list if no candidates

    # Extract the text from the response
    text_content = response_data['candidates'][0]['content']['parts'][0]['text']
    
    # Split the text into individual questions based on the format
    question_blocks = text_content.split("\n\n")  # Split by double newlines

    for block in question_blocks:
        if block.strip():  # Ensure the block is not empty
            # Split the question and options
            lines = block.split("\n")
            question = lines[0]  # The first line is the question
            options = [line for line in lines[1:] if line]  # Remaining lines are options
            
            # Extract the correct answer from the last line
            correct_answer = options[-1].split("**Correct Answer: ")[-1].strip()
            options = options[:-1]  # Remove the correct answer line from options
            
            questions.append({
                "question": question,
                "options": options,
                "answer": correct_answer  # Store the correct answer
            })
    
    return questions

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the quiz by asking for a topic."""
    if not context.args:
        await update.message.reply_text("ℹ️ Please provide a topic for the quiz.\nExample: /quiz python")
        return

    topic = ' '.join(context.args)  # Join the arguments to form the topic

    # Send a message indicating that the quiz is being generated
    await update.message.reply_text("🔄 Generating your quiz... Please wait.")

    questions = await fetch_quiz_questions(topic)

    if questions:
        context.user_data['quiz_questions'] = questions
        context.user_data['current_question'] = 0
        context.user_data['score'] = 0
        await ask_question(update, context)
    else:
        await update.message.reply_text("Sorry, I couldn't find any questions for that topic. Try another one.")

async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask the current question using inline buttons."""
    user_data = context.user_data
    current_question_index = user_data['current_question']
    questions = user_data['quiz_questions']

    if current_question_index >= len(questions):
        # Save quiz results to the database
        await db_ops.save_quiz_results(
            user_id=update.effective_user.id,
            topic=' '.join(context.args),  # Assuming you have the topic stored
            questions=[q['question'] for q in questions],
            user_answers=user_data.get('user_answers', []),
            score=user_data['score']
        )
        await update.message.reply_text(f"Quiz completed! Your final score: {user_data['score']}/{len(questions)} 🎉")
        return

    question = questions[current_question_index]
    question_text = question['question']
    options = question['options']
    
    # Create inline buttons
    keyboard = [[InlineKeyboardButton(opt, callback_data=opt) for opt in options]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(question_text, reply_markup=reply_markup)

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the user's answer to the quiz question."""
    user_data = context.user_data
    current_question_index = user_data['current_question']
    questions = user_data['quiz_questions']
    question = questions[current_question_index]

    # Store user's answer
    if 'user_answers' not in user_data:
        user_data['user_answers'] = []
    user_data['user_answers'].append(update.callback_query.data)

    if update.callback_query.data == question['answer']:
        user_data['score'] += 1
        await update.callback_query.answer("✅ Correct!")
    else:
        await update.callback_query.answer(f"❌ Incorrect! The correct answer was: {question['answer']}")

    user_data['current_question'] += 1
    await ask_question(update.callback_query.message, context)

class TelegramBot:
    """Main bot class handling all Telegram interactions."""
    def __init__(self):
        self.db = DatabaseManager()
        self.app = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()
        self.setup_handlers()

    def setup_handlers(self):
        """Set up all message handlers."""
        self.app.add_handler(CommandHandler('start', self.start_chat))
        self.app.add_handler(CommandHandler('help', self.help_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.app.add_handler(CommandHandler('websearch', self.handle_websearch))
        self.app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))  # Handle image uploads
        self.app.add_handler(MessageHandler(filters.Document.MimeType("application/pdf"), self.handle_document))  # Handle PDF uploads
        self.app.add_handler(CallbackQueryHandler(self.handle_answer))  # Handle quiz answers
          
    async def start_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        await start_chat(update, context)

    async def start_quiz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the quiz by asking for a topic."""
        await start_quiz(update, context)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user messages."""
        await handle_message(update, context)

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await handle_photo(update, context)

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await handle_document(update, context)

    async def handle_websearch(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await handle_websearch(update, context)

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await handle_voice(update, context)

    async def handle_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await handle_contact(update, context)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await help_command(update, context)

    async def handle_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await handle_answer(update, context)

    def run(self):
        """Run the bot."""
        self.app.run_polling(drop_pending_updates=True)

def main():
    """Main function to run the bot."""
    bot = TelegramBot()
    bot.run()

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler for all updates."""
    logger.error(f"Update {update} caused error {context.error}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Sorry, something went wrong. Please try again later."
            )
    except Exception as e:
        logger.error(f"Error in error handler: {e}")

if __name__ == '__main__':
    main()