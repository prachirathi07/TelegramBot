import google.generativeai as genai
import logging
from PIL import Image
import io
from config.config import Config

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        try:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.chat_model = genai.GenerativeModel('gemini-pro')
            self.vision_model = genai.GenerativeModel('gemini-1.5-flash')
            logger.info("Gemini service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini service: {e}")
            raise

    async def analyze_image(self, image_data: bytes) -> str:
        try:
            image = Image.open(io.BytesIO(image_data))
            
            prompt = """Analyze this image in detail and provide:
            1. Main subject or focus
            2. Key objects and elements
            3. Colors and visual composition
            4. Any text visible in the image
            5. Context or setting
            6. Notable details or unique features
            7. Overall mood or atmosphere
            
            Please be specific and descriptive."""
            
            response = self.vision_model.generate_content([prompt, image])
            if response.parts:  # Check if response has parts
                return response.text
            return "Sorry, I couldn't analyze this image properly."
            
        except Exception as e:
            logger.error(f"Error analyzing image: {e}")
            return f"Error analyzing image: {str(e)}"

    async def get_chat_response(self, message: str) -> str:
        try:
            response = self.chat_model.generate_content(message)
            if response.parts:  # Check if response has parts
                return response.text
            return "Sorry, I couldn't process your message properly."
        except Exception as e:
            logger.error(f"Error getting chat response: {e}")
            return f"Error processing message: {str(e)}"
