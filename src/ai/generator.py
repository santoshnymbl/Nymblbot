"""
Miss Minutes - AI Response Generator
Claude API integration
"""
import logging
import time
from typing import Optional

import anthropic

from src.config import settings, SYSTEM_PROMPT
from src.ai.rag import rag_pipeline

logger = logging.getLogger(__name__)


class AIGenerator:
    """Generate responses using Claude with RAG context"""
    
    def __init__(self):
        self.client: Optional[anthropic.Anthropic] = None
        self._initialized = False
    
    def initialize(self):
        """Initialize Anthropic client"""
        if self._initialized:
            return
        
        if not settings.anthropic_api_key:
            logger.error("ANTHROPIC_API_KEY not set")
            return
        
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._initialized = True
        logger.info("AI Generator initialized with Claude")
    
    async def generate(
        self,
        query: str,
        user_name: Optional[str] = None,
        thread_context: Optional[str] = None
    ) -> tuple[str, int]:
        """
        Generate a response to user's query.
        
        Returns: (response_text, latency_ms)
        """
        if not self._initialized:
            self.initialize()
        
        if not self.client:
            return "I'm having trouble connecting right now. Please try again!", 0
        
        start_time = time.time()
        
        try:
            # Get RAG context
            context = rag_pipeline.get_context(query)
            
            # DEBUG: Log the context being sent
            logger.info(f"RAG Context for '{query}': {context[:500]}...")
            
            # Build system prompt with user context
            system = SYSTEM_PROMPT
            if user_name:
                system += f"\n\nYou're talking to {user_name}."
            
            # Build user message with context
            user_message = f"""Here's relevant information from Nymbl's knowledge base:

{context}

---

User's question: {query}

IMPORTANT: The section headers (like "CEO / Co-Founder", "Leave Policy", etc.) indicate what/who the content is about. Use both the headers AND content to answer.

Please answer based on the information above. Be direct and specific - if the answer is in the context, state it clearly."""

            # DEBUG: Log full message length
            logger.info(f"Full user message length: {len(user_message)} chars")

            # Add thread context if available
            messages = []
            if thread_context:
                messages.append({"role": "user", "content": f"Previous context:\n{thread_context}"})
                messages.append({"role": "assistant", "content": "I understand the context."})
            
            messages.append({"role": "user", "content": user_message})
            
            # Call Claude
            response = self.client.messages.create(
                model=settings.claude_model,
                max_tokens=1024,
                system=system,
                messages=messages
            )
            
            answer = response.content[0].text
            latency_ms = int((time.time() - start_time) * 1000)
            
            logger.info(f"Generated response in {latency_ms}ms for: {query[:50]}...")
            return answer, latency_ms
            
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            latency_ms = int((time.time() - start_time) * 1000)
            return "I ran into a hiccup with my AI brain! 🕐 Try asking again in a moment.", latency_ms
        
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            latency_ms = int((time.time() - start_time) * 1000)
            return "Something went wrong on my end. Let me know if this keeps happening!", latency_ms


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
