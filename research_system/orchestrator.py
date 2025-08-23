"""
Main orchestrator for the research system
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import structlog

from .models import (
    ResearchRequest, ResearchPlan, EvidenceCard, 
    ResearchReport, ResearchMetrics, ResearchSection,
    Subtopic, ResearchMethodology, ResearchConstraints
)
from .config import Config
from .core.error_recovery import ErrorRecoveryManager, CircuitBreakerConfig
from .core.performance import PerformanceOptimizer, CacheConfig
from .core.security import SecurityManager, SecurityConfig
from .monitoring.metrics import ObservabilityManager
from .agents import ResearchCrew
from .tools.search_tools import SearchTools
from .tools.llm_tools import LLMTools
from .exceptions import (
    PlanningError, CollectionError, CostLimitError,
    TimeoutError, PartialResultError
)

logger = structlog.get_logger()


class ResearchOrchestrator:
    """Main orchestrator for research operations"""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        
        # Initialize core systems
        self._init_error_recovery()
        self._init_performance()
        self._init_security()
        self._init_monitoring()
        
        # Initialize tools
        self.search_tools = SearchTools(self.config)
        self.llm_tools = LLMTools(self.config)
        
        # Initialize crew
        self.crew = ResearchCrew(self.config)
        
        # Track costs
        self.total_cost = 0.0
        self.daily_cost = 0.0
        self.last_reset = datetime.utcnow()
    
    def _init_error_recovery(self):
        """Initialize error recovery system"""
        self.error_recovery = ErrorRecoveryManager()
        
        # Register circuit breakers
        self.error_recovery.register_circuit_breaker(
            "search",
            CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=60,
                name="search"
            )
        )
        
        self.error_recovery.register_circuit_breaker(
            "llm",
            CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=120,
                name="llm"
            )
        )
    
    def _init_performance(self):
        """Initialize performance optimization"""
        cache_config = CacheConfig(
            redis_url=self.config.redis.url,
            default_ttl=self.config.performance.cache_ttl_seconds,
            enable_redis=self.config.performance.enable_redis_cache,
            enable_memory=self.config.performance.enable_memory_cache
        )
        self.performance = PerformanceOptimizer(cache_config)
    
    def _init_security(self):
        """Initialize security system"""
        security_config = SecurityConfig(
            enable_encryption=self.config.security.enable_encryption,
            enable_sanitization=self.config.security.enable_sanitization,
            enable_privacy=self.config.security.enable_privacy,
            allowed_domains=self.config.security.allowed_domains,
            blocked_patterns=self.config.security.blocked_patterns
        )
        self.security = SecurityManager(security_config)
    
    def _init_monitoring(self):
        """Initialize monitoring system"""
        self.monitoring = ObservabilityManager()
    
    async def execute_research(self, request: ResearchRequest) -> ResearchReport:
        """Execute complete research workflow"""
        
        # Start monitoring
        trace = self.monitoring.start_research_trace(request.request_id, request.topic)
        self.monitoring.metrics['active'].inc()
        
        start_time = time.time()
        
        try:
            # Sanitize input
            request.topic = self.security.sanitize_input(request.topic)
            
            # Check cost limits
            self._check_cost_limits()
            
            # Phase 1: Planning
            plan = await self._execute_planning(request)
            
            # Phase 2: Collection
            evidence = await self._execute_collection(plan)
            
            # Phase 3: Verification
            verified_evidence = await self._execute_verification(evidence)
            
            # Phase 4: Synthesis
            report = await self._execute_synthesis(request, plan, verified_evidence)
            
            # Update metrics
            execution_time = time.time() - start_time
            report.metrics.execution_time_seconds = execution_time
            report.metrics.total_cost_usd = self.total_cost
            
            # Record success
            self.monitoring.metrics['requests'].labels(
                topic_category="general",
                depth=request.depth,
                status="success"
            ).inc()
            
            return report
            
        except Exception as e:
            logger.error(f"Research failed: {e}", request_id=request.request_id)
            
            # Record failure
            self.monitoring.metrics['requests'].labels(
                topic_category="general",
                depth=request.depth,
                status="failed"
            ).inc()
            
            # Try to generate partial report
            if hasattr(e, 'partial_data'):
                return self._generate_partial_report(request, e.partial_data)
            
            raise
            
        finally:
            self.monitoring.metrics['active'].dec()
            if trace:
                trace.end()
    
    async def _execute_planning(self, request: ResearchRequest) -> ResearchPlan:
        """Execute planning phase"""
        
        start_time = time.time()
        
        try:
            # Use cached plan if available
            cache_params = {"topic": request.topic, "depth": request.depth}
            
            plan = await self.performance.cached_operation(
                "planning",
                self._generate_plan,
                cache_params,
                ttl=3600,
                force_refresh=False
            )
            
            # Record metrics
            duration = time.time() - start_time
            self.monitoring.record_phase_duration("planning", request.depth, duration)
            
            return plan
            
        except Exception as e:
            raise PlanningError(f"Planning failed: {e}")
    
    async def _generate_plan(self, topic: str, depth: str) -> ResearchPlan:
        """Generate research plan"""
        
        # Use LLM to generate plan
        prompt = f"""
        Create a research plan for: {topic}
        Depth: {depth}
        
        Generate 3-7 subtopics with search queries.
        Focus on comprehensive coverage.
        """
        
        response = await self.llm_tools.generate_text(prompt, temperature=0.7)
        
        # Parse response and create plan (simplified)
        subtopics = [
            Subtopic(
                name=f"Subtopic {i+1}",
                rationale="Important aspect to research",
                search_queries=[f"{topic} subtopic {i+1}"]
            )
            for i in range(5)
        ]
        
        methodology = ResearchMethodology(
            search_strategy="Multi-source comprehensive search",
            quality_criteria=["Credibility", "Relevance", "Recency"]
        )
        
        return ResearchPlan(
            topic=topic,
            depth=depth,
            subtopics=subtopics,
            methodology=methodology,
            constraints=ResearchConstraints(),
            budget={"max_cost_usd": 1.0}
        )
    
    async def _execute_collection(self, plan: ResearchPlan) -> List[EvidenceCard]:
        """Execute evidence collection phase"""
        
        start_time = time.time()
        all_evidence = []
        
        try:
            # Collect evidence for each subtopic
            tasks = []
            for subtopic in plan.subtopics:
                if subtopic.priority == "high" or len(tasks) < 5:
                    task = self._collect_subtopic_evidence(subtopic)
                    tasks.append(task)
            
            # Execute collection tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"Subtopic collection failed: {result}")
                    continue
                all_evidence.extend(result)
            
            # Record metrics
            duration = time.time() - start_time
            self.monitoring.record_phase_duration("collection", plan.depth, duration)
            
            if not all_evidence:
                raise CollectionError("No evidence collected")
            
            return all_evidence
            
        except Exception as e:
            if all_evidence:
                raise PartialResultError(f"Partial collection: {e}", all_evidence)
            raise CollectionError(f"Collection failed: {e}")
    
    async def _collect_subtopic_evidence(self, subtopic: Subtopic) -> List[EvidenceCard]:
        """Collect evidence for a single subtopic"""
        
        evidence_list = []
        
        for query in subtopic.search_queries[:3]:  # Limit queries
            try:
                # Search with error recovery
                results = await self.error_recovery.execute_with_recovery(
                    "search",
                    self.search_tools.multi_search,
                    fallback=self._search_fallback,
                    query=query,
                    max_results_per_provider=5
                )
                
                # Convert to evidence cards
                for result in results:
                    evidence = await self._create_evidence_card(result, subtopic.name)
                    if evidence:
                        evidence_list.append(evidence)
                
            except Exception as e:
                logger.error(f"Query failed: {query}, Error: {e}")
        
        return evidence_list
    
    async def _create_evidence_card(self, search_result: Dict, subtopic_name: str) -> Optional[EvidenceCard]:
        """Create evidence card from search result"""
        
        try:
            # Analyze with LLM
            analysis = await self.llm_tools.analyze_evidence(
                search_result,
                ["credibility", "relevance", "bias"]
            )
            
            # Extract entities
            entities = await self.llm_tools.extract_entities(
                search_result.get("snippet", "")
            )
            
            return EvidenceCard(
                subtopic_name=subtopic_name,
                claim=search_result.get("title", ""),
                supporting_text=search_result.get("snippet", ""),
                source_url=search_result.get("url", ""),
                source_title=search_result.get("title", ""),
                source_domain=self._extract_domain(search_result.get("url", "")),
                credibility_score=analysis.get("credibility", 0.5),
                relevance_score=analysis.get("relevance", 0.5),
                is_primary_source=False,
                entities=entities
            )
            
        except Exception as e:
            logger.error(f"Evidence card creation failed: {e}")
            return None
    
    async def _execute_verification(self, evidence: List[EvidenceCard]) -> List[EvidenceCard]:
        """Execute evidence verification phase"""
        
        start_time = time.time()
        verified = []
        
        for card in evidence:
            # Verify URL is safe
            if not self.security.validate_url(str(card.source_url)):
                logger.warning(f"Unsafe URL skipped: {card.source_url}")
                continue
            
            # Check quality threshold
            if card.credibility_score >= 0.3 and card.relevance_score >= 0.3:
                verified.append(card)
            
            # Record quality metrics
            self.monitoring.record_evidence_quality(
                card.source_domain,
                card.credibility_score
            )
        
        # Record phase metrics
        duration = time.time() - start_time
        self.monitoring.record_phase_duration("verification", "standard", duration)
        
        return verified
    
    async def _execute_synthesis(
        self,
        request: ResearchRequest,
        plan: ResearchPlan,
        evidence: List[EvidenceCard]
    ) -> ResearchReport:
        """Execute synthesis phase"""
        
        start_time = time.time()
        
        # Group evidence by subtopic
        subtopic_evidence = {}
        for card in evidence:
            if card.subtopic_name not in subtopic_evidence:
                subtopic_evidence[card.subtopic_name] = []
            subtopic_evidence[card.subtopic_name].append(card)
        
        # Generate sections
        sections = []
        for subtopic_name, cards in subtopic_evidence.items():
            section = await self._generate_section(subtopic_name, cards)
            sections.append(section)
        
        # Generate executive summary
        executive_summary = await self._generate_executive_summary(
            request.topic,
            sections,
            evidence
        )
        
        # Calculate metrics
        metrics = self._calculate_metrics(evidence, time.time() - start_time)
        
        # Create report
        report = ResearchReport(
            request_id=request.request_id,
            topic=request.topic,
            executive_summary=executive_summary,
            sections=sections,
            evidence=evidence,
            methodology=plan.methodology,
            metrics=metrics,
            limitations=self._identify_limitations(evidence),
            recommendations=self._generate_recommendations(evidence)
        )
        
        # Record synthesis metrics
        duration = time.time() - start_time
        self.monitoring.record_phase_duration("synthesis", request.depth, duration)
        
        return report
    
    async def _generate_section(
        self,
        title: str,
        evidence: List[EvidenceCard]
    ) -> ResearchSection:
        """Generate a report section"""
        
        # Synthesize evidence into narrative
        evidence_text = "\n".join([
            f"- {card.claim}: {card.supporting_text[:200]}"
            for card in evidence[:10]
        ])
        
        prompt = f"""
        Synthesize the following evidence about {title}:
        
        {evidence_text}
        
        Create a coherent narrative that:
        1. Identifies key themes
        2. Highlights important findings
        3. Notes any contradictions
        4. Draws insights
        
        Length: 200-400 words
        """
        
        content = await self.llm_tools.generate_text(prompt, temperature=0.5)
        
        return ResearchSection(
            title=title,
            content=content,
            evidence_ids=[card.id for card in evidence],
            confidence=sum(card.confidence for card in evidence) / len(evidence),
            word_count=len(content.split())
        )
    
    async def _generate_executive_summary(
        self,
        topic: str,
        sections: List[ResearchSection],
        evidence: List[EvidenceCard]
    ) -> str:
        """Generate executive summary"""
        
        section_summaries = "\n".join([
            f"{s.title}: {s.content[:200]}..."
            for s in sections
        ])
        
        prompt = f"""
        Create an executive summary for research on: {topic}
        
        Section summaries:
        {section_summaries}
        
        Total evidence pieces: {len(evidence)}
        Average credibility: {sum(e.credibility_score for e in evidence) / len(evidence):.2f}
        
        Create a 150-250 word executive summary that:
        1. Summarizes key findings
        2. Highlights most important insights
        3. Notes overall confidence level
        4. Mentions any significant limitations
        """
        
        return await self.llm_tools.generate_text(prompt, temperature=0.5)
    
    def _calculate_metrics(
        self,
        evidence: List[EvidenceCard],
        synthesis_time: float
    ) -> ResearchMetrics:
        """Calculate research metrics"""
        
        unique_domains = len(set(card.source_domain for card in evidence))
        
        return ResearchMetrics(
            total_sources_examined=len(evidence) * 2,  # Estimate
            total_evidence_collected=len(evidence),
            unique_domains=unique_domains,
            avg_credibility_score=sum(e.credibility_score for e in evidence) / len(evidence),
            avg_relevance_score=sum(e.relevance_score for e in evidence) / len(evidence),
            execution_time_seconds=synthesis_time,
            total_cost_usd=self.total_cost,
            api_calls_made=len(evidence) * 3,  # Estimate
            cache_hit_rate=self.performance.metrics._calculate_cache_hit_rate("search")
        )
    
    def _identify_limitations(self, evidence: List[EvidenceCard]) -> List[str]:
        """Identify research limitations"""
        
        limitations = []
        
        # Check for recency
        if not any(card.publication_date for card in evidence):
            limitations.append("Unable to verify publication dates for most sources")
        
        # Check for diversity
        unique_domains = len(set(card.source_domain for card in evidence))
        if unique_domains < 5:
            limitations.append(f"Limited source diversity ({unique_domains} unique domains)")
        
        # Check for primary sources
        primary_count = sum(1 for card in evidence if card.is_primary_source)
        if primary_count < len(evidence) * 0.2:
            limitations.append("Limited primary source material")
        
        return limitations
    
    def _generate_recommendations(self, evidence: List[EvidenceCard]) -> List[str]:
        """Generate research recommendations"""
        
        recommendations = []
        
        # Check for gaps
        if len(evidence) < 20:
            recommendations.append("Expand search to include more sources")
        
        # Check quality
        avg_quality = sum(e.credibility_score for e in evidence) / len(evidence)
        if avg_quality < 0.7:
            recommendations.append("Seek higher quality sources from academic or government domains")
        
        # Check for bias
        if any(card.bias_indicators for card in evidence if card.bias_indicators):
            recommendations.append("Consider sources with different perspectives to balance potential bias")
        
        return recommendations
    
    def _check_cost_limits(self):
        """Check if cost limits are exceeded"""
        
        # Reset daily counter if needed
        if (datetime.utcnow() - self.last_reset).days >= 1:
            self.daily_cost = 0.0
            self.last_reset = datetime.utcnow()
        
        # Check limits
        if self.daily_cost >= self.config.cost_management.max_daily_cost_usd:
            raise CostLimitError(
                "Daily cost limit exceeded",
                self.daily_cost,
                self.config.cost_management.max_daily_cost_usd
            )
        
        # Alert if approaching limit
        if self.daily_cost >= self.config.cost_management.max_daily_cost_usd * self.config.cost_management.alert_threshold:
            logger.warning(f"Approaching daily cost limit: ${self.daily_cost:.2f}")
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        try:
            return urlparse(url).netloc
        except:
            return "unknown"
    
    async def _search_fallback(self, query: str, **kwargs) -> List[Dict]:
        """Fallback search strategy"""
        from .tools.search_tools import search_with_single_provider
        return await search_with_single_provider(query, provider="tavily")
    
    def _generate_partial_report(
        self,
        request: ResearchRequest,
        partial_evidence: List[EvidenceCard]
    ) -> ResearchReport:
        """Generate partial report from available data"""
        
        return ResearchReport(
            request_id=request.request_id,
            topic=request.topic,
            executive_summary="Partial report - not all data could be collected",
            sections=[],
            evidence=partial_evidence,
            methodology=ResearchMethodology(
                search_strategy="Partial",
                quality_criteria=[]
            ),
            metrics=ResearchMetrics(),
            limitations=["Incomplete data collection due to errors"],
            recommendations=["Retry research with resolved issues"],
            status="partial"
        )