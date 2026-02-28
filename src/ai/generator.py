"""
Miss Minutes - AI Response Generator
Claude API integration with query expansion and conversation memory
"""
import logging
import time
from typing import Optional, List

import anthropic

from src.config import settings, SYSTEM_PROMPT
from src.ai.rag import rag_pipeline
from src.ai.query_expansion import expand_query
from src.models.database import get_conversation_history, save_conversation_message

logger = logging.getLogger(__name__)


class AIGenerator:
    """Generate responses using Claude with RAG context"""
    
    def __init__(self):
        self.client: Optional[anthropic.AsyncAnthropic] = None
        self._initialized = False
    
    def initialize(self):
        """Initialize Anthropic client"""
        if self._initialized:
            return
        
        if not settings.anthropic_api_key:
            logger.error("ANTHROPIC_API_KEY not set")
            return
        
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._initialized = True
        logger.info("AI Generator initialized with Claude")
    
    async def generate(
        self,
        query: str,
        user_name: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> tuple[str, int, List[dict]]:
        """
        Generate a response to user's query.

        Returns: (response_text, latency_ms, sources)
        """
        if not self._initialized:
            self.initialize()

        if not self.client:
            return "I'm having trouble connecting right now. Please try again!", 0, []

        start_time = time.time()

        try:
            # Step 1: Expand the query for better retrieval
            expanded_queries = await expand_query(query, self.client)
            logger.info(f"Expanded queries: {expanded_queries}")

            # Step 2: Get RAG context with source metadata
            context, sources = rag_pipeline.get_context_with_sources(
                query=query,
                queries=expanded_queries
            )

            logger.info(f"RAG Context for '{query}': {context[:500]}...")

            # Step 3: Build system prompt
            system = SYSTEM_PROMPT
            if user_name:
                system += f"\n\nYou're talking to {user_name}."

            # Step 4: Build messages with conversation history
            messages = []

            if user_id:
                history = await get_conversation_history(user_id)
                for msg in history:
                    messages.append({"role": msg["role"], "content": msg["content"]})

            # Add current user message with RAG context
            user_message = f"""Here's relevant information from Nymbl's knowledge base:

{context}

---

User's question: {query}

IMPORTANT: The section headers (like "CEO / Co-Founder", "Leave Policy", etc.) indicate what/who the content is about. Use both the headers AND content to answer.

Please answer based on the information above. Be direct and specific - if the answer is in the context, state it clearly."""

            messages.append({"role": "user", "content": user_message})

            # Step 5: Call Claude
            response = await self.client.messages.create(
                model=settings.claude_model,
                max_tokens=1024,
                system=system,
                messages=messages
            )

            answer = response.content[0].text
            latency_ms = int((time.time() - start_time) * 1000)

            # Step 6: Save to conversation history
            if user_id:
                await save_conversation_message(user_id, "user", query)
                await save_conversation_message(user_id, "assistant", answer)

            logger.info(f"Generated response in {latency_ms}ms for: {query[:50]}...")
            return answer, latency_ms, sources

        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            latency_ms = int((time.time() - start_time) * 1000)
            return "I ran into a hiccup with my AI brain! Try asking again in a moment.", latency_ms, []

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            latency_ms = int((time.time() - start_time) * 1000)
            return "Something went wrong on my end. Let me know if this keeps happening!", latency_ms, []


# Global instance
ai_generator = AIGenerator()


# Quick responses for common greetings/commands
QUICK_RESPONSES = {
    "hello": "Hey there! 👋 I'm Nymbling, Nymbl's AI assistant. What can I help you with?",
    "hi": "Hi! I'm Nymbling. Ask me anything about Nymbl!",
    "hey": "Hey!  What can I help you with today?",
    "thanks": "You're welcome! Let me know if you need anything else. I'm here to help!",
    "thank you": "Happy to help! Reach out anytime.",
    "bye": "See you later! Don't forget to log your time on Mondays before 1.30PM EST!",
    "goodbye": "Goodbye! Remember, I'm here whenever you need help with anything."
}


def get_quick_response(message: str) -> Optional[str]:
    """Check if message matches a quick response"""
    message_lower = message.lower().strip().rstrip("!")
    return QUICK_RESPONSES.get(message_lower)
