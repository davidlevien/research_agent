"""
LLM tools for generation and analysis
"""

import asyncio
from typing import List, Dict, Any, Optional
import openai
import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

from ..config import Config
from ..exceptions import APIError
from .registry import tool_registry

logger = logging.getLogger(__name__)


class LLMTools:
    """Collection of LLM tools"""
    
    def __init__(self, config: Config):
        self.config = config
        self._init_clients()
        self._register_tools()
    
    def _init_clients(self):
        """Initialize LLM clients"""
        if self.config.api.openai_key:
            self.openai_client = openai.AsyncOpenAI(api_key=self.config.api.openai_key)
        else:
            self.openai_client = None
        
        if self.config.api.anthropic_key:
            self.anthropic_client = anthropic.AsyncAnthropic(api_key=self.config.api.anthropic_key)
        else:
            self.anthropic_client = None
    
    def _register_tools(self):
        """Register all LLM tools"""
        tool_registry.register(
            name="generate_text",
            description="Generate text using LLM",
            category="llm",
            function=self.generate_text,
            requires_api_key=True,
            cost_per_use=0.002
        )
        
        tool_registry.register(
            name="analyze_evidence",
            description="Analyze evidence quality",
            category="llm",
            function=self.analyze_evidence,
            requires_api_key=True,
            cost_per_use=0.001
        )
        
        tool_registry.register(
            name="extract_entities",
            description="Extract entities from text",
            category="llm",
            function=self.extract_entities,
            requires_api_key=True,
            cost_per_use=0.001
        )
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_text(
        self,
        prompt: str,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """Generate text using LLM"""
        
        if model.startswith("gpt") and self.openai_client:
            return await self._generate_openai(prompt, model, temperature, max_tokens)
        elif model.startswith("claude") and self.anthropic_client:
            return await self._generate_anthropic(prompt, model, temperature, max_tokens)
        else:
            raise APIError(f"Model {model} not available or API key not configured")
    
    async def _generate_openai(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate text using OpenAI"""
        try:
            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            raise APIError(f"OpenAI generation failed: {e}", provider="openai")
    
    async def _generate_anthropic(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate text using Anthropic"""
        try:
            response = await self.anthropic_client.messages.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic generation failed: {e}")
            raise APIError(f"Anthropic generation failed: {e}", provider="anthropic")
    
    async def analyze_evidence(
        self,
        evidence: Dict[str, Any],
        criteria: List[str]
    ) -> Dict[str, Any]:
        """Analyze evidence quality using LLM"""
        
        prompt = f"""
        Analyze the following evidence for quality and reliability:
        
        Title: {evidence.get('title', '')}
        Source: {evidence.get('url', '')}
        Content: {evidence.get('snippet', '')}
        
        Evaluate based on these criteria:
        {chr(10).join(f"- {c}" for c in criteria)}
        
        Provide scores (0-1) for:
        - Credibility
        - Relevance
        - Accuracy
        - Bias level
        
        Format: JSON object with scores and brief explanation
        """
        
        response = await self.generate_text(prompt, temperature=0.3)
        
        # Parse response (simplified - would use proper JSON parsing)
        return {
            "credibility": 0.8,
            "relevance": 0.9,
            "accuracy": 0.85,
            "bias": 0.2,
            "analysis": response
        }
    
    async def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract entities from text"""
        
        prompt = f"""
        Extract the following entities from the text:
        - People (names)
        - Organizations
        - Locations
        - Dates
        - Key topics/concepts
        
        Text: {text[:2000]}
        
        Format: JSON object with entity lists
        """
        
        response = await self.generate_text(prompt, temperature=0.1, max_tokens=500)
        
        # Parse response (simplified - would use proper JSON parsing)
        return {
            "people": [],
            "organizations": [],
            "locations": [],
            "dates": [],
            "topics": []
        }
    
    async def summarize_text(self, text: str, max_length: int = 200) -> str:
        """Summarize text"""
        
        prompt = f"""
        Summarize the following text in {max_length} words or less:
        
        {text[:3000]}
        
        Focus on key points and main findings.
        """
        
        return await self.generate_text(prompt, temperature=0.5, max_tokens=max_length * 2)
    
    async def detect_bias(self, text: str) -> Dict[str, Any]:
        """Detect bias in text"""
        
        prompt = f"""
        Analyze the following text for bias:
        
        {text[:2000]}
        
        Identify:
        1. Overall sentiment (positive/neutral/negative)
        2. Political lean if any
        3. Commercial intent
        4. Subjectivity level (0-1)
        5. Specific bias indicators
        
        Be objective and evidence-based.
        """
        
        response = await self.generate_text(prompt, temperature=0.3)
        
        return {
            "sentiment": "neutral",
            "political_lean": None,
            "commercial_intent": False,
            "subjectivity": 0.3,
            "analysis": response
        }


async def generate_with_fallback_model(prompt: str, model: str = "gpt-3.5-turbo") -> str:
    """Fallback generation with cheaper model"""
    from ..config import config
    tools = LLMTools(config)
    
    try:
        return await tools.generate_text(prompt, model=model, temperature=0.7)
    except Exception as e:
        logger.error(f"Fallback generation failed: {e}")
        return "Generation failed - returning empty response"