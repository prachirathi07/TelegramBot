import os
import fitz  # PyMuPDF for PDF handling
import logging
from PIL import Image
from io import BytesIO
from services.gemini_service import GeminiService
from config.config import Config

logger = logging.getLogger(__name__)

class FileHandler:
    def __init__(self):
        self.gemini = GeminiService()
        self.supported_images = {'.jpg', '.jpeg', '.png', '.bmp'}
        self.supported_docs = {'.pdf', '.txt'}
        # Create downloads directory if it doesn't exist
        os.makedirs("downloads", exist_ok=True)

    async def process_file(self, file_path: str, file_type: str) -> str:
        """Process different types of files and return analysis"""
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext in self.supported_images:
                return await self._process_image(file_path)
            elif file_ext == '.pdf':
                return await self.process_pdf(file_path)
            elif file_ext == '.txt':
                return await self._process_text(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")
        except Exception as e:
            logger.error(f"Error processing file: {e}")
            raise

    async def _process_image(self, file_path: str) -> str:
        """Process image files"""
        try:
            with open(file_path, 'rb') as image_file:
                image_data = image_file.read()
            return await self.gemini.analyze_image(image_data)
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            raise

    async def process_pdf(self, file_path: str) -> str:
        """Process PDF files"""
        try:
            # Extract text from PDF
            text_content = ""
            with fitz.open(file_path) as pdf:
                for page in pdf:
                    text_content += page.get_text()

            # Prepare prompt for better PDF analysis
            prompt = f"""Analyze this PDF content and provide:
            1. Main topic or subject
            2. Key points and information
            3. Important details
            4. Structure and organization
            5. Summary of content

            Content: {text_content[:4000]}"""  # Limit content length

            # Get analysis from Gemini
            analysis = await self.gemini.get_chat_response(prompt)
            return analysis

        except Exception as e:
            logger.error(f"Error processing PDF: {e}")
            raise
        finally:
            # Cleanup temporary file
            if os.path.exists(file_path):
                os.remove(file_path)

    async def _process_text(self, file_path: str) -> str:
        """Process text files"""
        try:
            with open(file_path, 'r') as text_file:
                text_content = text_file.read()
            # Prepare prompt for text analysis
            prompt = f"Analyze this text content:\n{text_content[:4000]}"  # Limit content length
            analysis = await self.gemini.get_chat_response(prompt)
            return analysis
        except Exception as e:
            logger.error(f"Error processing text: {e}")
            raise

    def cleanup(self, file_path: str):
        """Clean up temporary files"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up file: {file_path}")
        except Exception as e:
            logger.error(f"Error cleaning up file {file_path}: {e}")
