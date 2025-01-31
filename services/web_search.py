import requests
import logging
from services.gemini_service import GeminiService
from config.config import Config

logger = logging.getLogger(__name__)

class WebSearchService:
    def __init__(self):
        self.gemini = GeminiService()
        self.search_url = "https://serpapi.com/search"
        self.api_key = Config.SERPAPI_KEY

    async def search(self, query: str, num_results: int = 5) -> dict:
        try:
            logger.info(f"Starting SerpApi search for: {query}")
            
            # Parameters for Google search via SerpApi
            params = {
                'q': query,
                'api_key': self.api_key,
                'engine': 'google',
                'num': num_results,
                'gl': 'us',  # Google country
                'hl': 'en'   # Language
            }
            
            response = requests.get(
                self.search_url,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract organic search results
            organic_results = data.get('organic_results', [])
            results = []
            
            for result in organic_results[:num_results]:
                results.append({
                    'title': result.get('title', 'No title'),
                    'link': result.get('link', ''),
                    'snippet': result.get('snippet', 'No description available')
                })
            
            logger.info(f"Found {len(results)} results")
            
            if not results:
                return {
                    'results': [],
                    'summary': "No search results found."
                }
            
            # Format results for summary
            results_text = "\n\n".join([
                f"Title: {r['title']}\nURL: {r['link']}\nDescription: {r['snippet']}"
                for r in results
            ])
            
            # Get AI summary of results
            summary_prompt = f"Summarize these search results for '{query}':\n\n{results_text}"
            ai_summary = await self.gemini.get_chat_response(summary_prompt)
            
            return {
                'results': results,
                'summary': ai_summary
            }
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            raise 