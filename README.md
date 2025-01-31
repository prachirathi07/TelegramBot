## 🤖 Telegram Bot
📖 Overview
This AI-powered Telegram Bot enhances user interaction by performing web searches, analyzing images and PDFs, and providing intelligent responses. Built using Python and the python-telegram-bot library, it integrates Gemini API for AI-powered processing, SERP API for web searches, and uses MongoDB for efficient data storage, making it a versatile and powerful assistant.

#### ✨ Features
- ✅ User Registration (/start) – Registers users for personalized interaction.
- 🆘 Help Command (/help) – Lists all available commands and usage instructions.
- 🌐 Web Search (/websearch) – Fetches real-time search results using SERP API.
- 📷 Image Analysis – Processes and extracts insights from uploaded images.
- 📄 PDF Analysis – Reads and summarizes PDF content using AI.
- 🧠 AI-Powered Responses – Utilizes Gemini API for intelligent responses.
- 💾 MongoDB Integration – Stores user data and interactions for personalized experience.

#### 💻 Requirements
- 🐍 Python 3.x
- 📦 python-telegram-bot
- 📦 google-generativeai (Gemini API)
- 📦 serpapi (Web search integration)
- 📦 pdfplumber (PDF processing)
- 📦 pymongo (MongoDB integration)

#### 🛠️ Key Components
- Main Script (main.py) – Handles user interactions and commands.
- Web Search Module (websearch.py) – Fetches results using SERP API.
- Image Analysis (image_processing.py) – Extracts insights from uploaded images.
- PDF Analyzer (pdf_reader.py) – Summarizes and processes PDF documents.
- MongoDB Integration – Stores user data for an enhanced, personalized experience.
