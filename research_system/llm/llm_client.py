"""
LLM Client - Provider Interface for Claims and Synthesis

Handles communication with OpenAI, Anthropic, or other LLM providers.
"""

import json
import logging
from typing import Optional, Dict, Any
from research_system.config.settings import Settings

logger = logging.getLogger(__name__)

class LLMClient:
    """Unified LLM client for multiple providers"""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.provider = self.settings.LLM_PROVIDER
        self.model_name = self._get_model_name()
        self._client = None
        self._initialize_client()
    
    def _get_model_name(self) -> str:
        """Get the model name based on provider"""
        if self.provider == "openai":
            return getattr(self.settings, 'OPENAI_MODEL', 'gpt-4-turbo-preview')
        elif self.provider == "anthropic":
            return getattr(self.settings, 'ANTHROPIC_MODEL', 'claude-3-opus-20240229')
        elif self.provider == "azure_openai":
            return getattr(self.settings, 'AZURE_OPENAI_DEPLOYMENT_RESEARCHER', 'gpt-4')
        else:
            return "unknown"
    
    def _initialize_client(self):
        """Initialize the appropriate LLM client"""
        try:
            if self.provider == "openai":
                import openai
                openai.api_key = self.settings.OPENAI_API_KEY
                if self.settings.OPENAI_API_BASE:
                    openai.api_base = self.settings.OPENAI_API_BASE
                if self.settings.OPENAI_ORG_ID:
                    openai.organization = self.settings.OPENAI_ORG_ID
                self._client = openai
                
            elif self.provider == "anthropic":
                import anthropic
                self._client = anthropic.Anthropic(
                    api_key=self.settings.ANTHROPIC_API_KEY
                )
                
            elif self.provider == "azure_openai":
                import openai
                openai.api_type = "azure"
                openai.api_key = self.settings.AZURE_OPENAI_API_KEY
                openai.api_base = self.settings.AZURE_OPENAI_ENDPOINT
                openai.api_version = "2024-02-15-preview"
                self._client = openai
                
        except ImportError as e:
            logger.error(f"Failed to import {self.provider} client: {e}")
            self._client = None
        except Exception as e:
            logger.error(f"Failed to initialize {self.provider} client: {e}")
            self._client = None
    
    def extract_claims(self, prompt: str) -> str:
        """Extract claims using LLM"""
        if not self._client:
            raise RuntimeError(f"LLM client not initialized for {self.provider}")
        
        try:
            if self.provider == "openai" or self.provider == "azure_openai":
                return self._openai_extract_claims(prompt)
            elif self.provider == "anthropic":
                return self._anthropic_extract_claims(prompt)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
                
        except Exception as e:
            logger.error(f"LLM claim extraction failed: {e}")
            raise
    
    def synthesize(self, prompt: str) -> str:
        """Generate synthesis using LLM"""
        if not self._client:
            raise RuntimeError(f"LLM client not initialized for {self.provider}")
        
        try:
            if self.provider == "openai" or self.provider == "azure_openai":
                return self._openai_synthesize(prompt)
            elif self.provider == "anthropic":
                return self._anthropic_synthesize(prompt)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
                
        except Exception as e:
            logger.error(f"LLM synthesis failed: {e}")
            raise
    
    def _openai_extract_claims(self, prompt: str) -> str:
        """Extract claims using OpenAI"""
        messages = [
            {
                "role": "system",
                "content": "You are a research assistant that extracts atomic, verifiable claims from evidence. "
                          "You must only extract information directly stated in the evidence, without inference or addition. "
                          "Output valid JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        response = self._client.ChatCompletion.create(
            model=self.model_name,
            messages=messages,
            temperature=0.3,  # Lower temperature for more consistent extraction
            max_tokens=4000,
            response_format={"type": "json_object"} if self.provider == "openai" else None
        )
        
        return response.choices[0].message.content
    
    def _anthropic_extract_claims(self, prompt: str) -> str:
        """Extract claims using Anthropic"""
        system_prompt = """You are a research assistant that extracts atomic, verifiable claims from evidence. 
        You must only extract information directly stated in the evidence, without inference or addition. 
        Output valid JSON only."""
        
        message = self._client.messages.create(
            model=self.model_name,
            max_tokens=4000,
            temperature=0.3,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        return message.content[0].text
    
    def _openai_synthesize(self, prompt: str) -> str:
        """Generate synthesis using OpenAI"""
        messages = [
            {
                "role": "system",
                "content": "You are an executive research analyst creating synthesis from verified claims. "
                          "You must only use information from the provided claims and reference claim IDs. "
                          "Be objective, concise, and highlight key insights, contradictions, and gaps. "
                          "Output valid JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        response = self._client.ChatCompletion.create(
            model=self.model_name,
            messages=messages,
            temperature=0.5,  # Moderate temperature for synthesis
            max_tokens=4000,
            response_format={"type": "json_object"} if self.provider == "openai" else None
        )
        
        return response.choices[0].message.content
    
    def _anthropic_synthesize(self, prompt: str) -> str:
        """Generate synthesis using Anthropic"""
        system_prompt = """You are an executive research analyst creating synthesis from verified claims. 
        You must only use information from the provided claims and reference claim IDs. 
        Be objective, concise, and highlight key insights, contradictions, and gaps. 
        Output valid JSON only."""
        
        message = self._client.messages.create(
            model=self.model_name,
            max_tokens=4000,
            temperature=0.5,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        return message.content[0].text
    
    def rerank(self, query: str, candidates: list[str], top_k: int = 10) -> list[tuple[float, str]]:
        """Rerank candidates based on relevance to query"""
        if not self._client:
            # Return original order if no client
            return [(1.0 / (i + 1), c) for i, c in enumerate(candidates[:top_k])]
        
        try:
            if self.provider == "openai" or self.provider == "azure_openai":
                return self._openai_rerank(query, candidates, top_k)
            elif self.provider == "anthropic":
                return self._anthropic_rerank(query, candidates, top_k)
            else:
                # Default scoring
                return [(1.0 / (i + 1), c) for i, c in enumerate(candidates[:top_k])]
                
        except Exception as e:
            logger.warning(f"LLM reranking failed: {e}")
            return [(1.0 / (i + 1), c) for i, c in enumerate(candidates[:top_k])]
    
    def _openai_rerank(self, query: str, candidates: list[str], top_k: int) -> list[tuple[float, str]]:
        """Rerank using OpenAI"""
        prompt = f"""Score the relevance of each document to the query on a scale of 0-10.
Query: {query}

Documents:
"""
        for i, candidate in enumerate(candidates[:20], 1):  # Limit to 20 for token limits
            prompt += f"\n[{i}] {candidate[:200]}..."
        
        prompt += "\n\nOutput JSON with scores: {\"scores\": {\"1\": 8.5, \"2\": 6.2, ...}}"
        
        messages = [
            {"role": "system", "content": "You are a relevance scoring system. Output JSON only."},
            {"role": "user", "content": prompt}
        ]
        
        response = self._client.ChatCompletion.create(
            model=self.model_name,
            messages=messages,
            temperature=0.1,
            max_tokens=500
        )
        
        try:
            scores_data = json.loads(response.choices[0].message.content)
            scores = scores_data.get("scores", {})
            
            scored_candidates = []
            for i, candidate in enumerate(candidates[:20], 1):
                score = float(scores.get(str(i), 5.0)) / 10.0
                scored_candidates.append((score, candidate))
            
            # Add remaining candidates with low scores
            for candidate in candidates[20:]:
                scored_candidates.append((0.3, candidate))
            
            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            return scored_candidates[:top_k]
            
        except:
            return [(1.0 / (i + 1), c) for i, c in enumerate(candidates[:top_k])]
    
    def _anthropic_rerank(self, query: str, candidates: list[str], top_k: int) -> list[tuple[float, str]]:
        """Rerank using Anthropic"""
        prompt = f"""Score the relevance of each document to the query on a scale of 0-10.
Query: {query}

Documents:
"""
        for i, candidate in enumerate(candidates[:20], 1):
            prompt += f"\n[{i}] {candidate[:200]}..."
        
        prompt += "\n\nOutput JSON with scores: {\"scores\": {\"1\": 8.5, \"2\": 6.2, ...}}"
        
        message = self._client.messages.create(
            model=self.model_name,
            max_tokens=500,
            temperature=0.1,
            system="You are a relevance scoring system. Output JSON only.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        try:
            scores_data = json.loads(message.content[0].text)
            scores = scores_data.get("scores", {})
            
            scored_candidates = []
            for i, candidate in enumerate(candidates[:20], 1):
                score = float(scores.get(str(i), 5.0)) / 10.0
                scored_candidates.append((score, candidate))
            
            for candidate in candidates[20:]:
                scored_candidates.append((0.3, candidate))
            
            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            return scored_candidates[:top_k]
            
        except:
            return [(1.0 / (i + 1), c) for i, c in enumerate(candidates[:top_k])]