"""
Agent definitions for the research system
"""

from crewai import Agent, Task, Crew, Process
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

from .models import ResearchRequest, ResearchPlan, EvidenceCard
from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for an agent"""
    role: str
    goal: str
    backstory: str
    verbose: bool = True
    allow_delegation: bool = False
    max_iter: int = 5
    memory: bool = True


class ResearchAgents:
    """Factory for creating research agents"""
    
    def __init__(self, config: Config):
        self.config = config
    
    def create_planner_agent(self) -> Agent:
        """Create research planner agent"""
        return Agent(
            role="Research Planner",
            goal="Create comprehensive research plans with optimal subtopic decomposition",
            backstory="""You are an expert research planner with decades of experience 
            in information architecture and research methodology. You excel at breaking 
            down complex topics into manageable subtopics and creating effective 
            search strategies.""",
            verbose=True,
            allow_delegation=False,
            max_iter=3,
            memory=True
        )
    
    def create_collector_agent(self) -> Agent:
        """Create evidence collector agent"""
        return Agent(
            role="Evidence Collector",
            goal="Gather high-quality, relevant evidence from diverse sources",
            backstory="""You are a meticulous evidence collector with expertise in 
            information retrieval and source evaluation. You know how to find 
            authoritative sources and extract the most relevant information.""",
            verbose=True,
            allow_delegation=False,
            max_iter=5,
            memory=True
        )
    
    def create_verifier_agent(self) -> Agent:
        """Create evidence verifier agent"""
        return Agent(
            role="Evidence Verifier",
            goal="Verify evidence quality, detect bias, and ensure factual accuracy",
            backstory="""You are a critical thinker and fact-checker with expertise 
            in identifying misinformation, bias, and logical fallacies. You ensure 
            all evidence meets high quality standards.""",
            verbose=True,
            allow_delegation=False,
            max_iter=3,
            memory=True
        )
    
    def create_synthesizer_agent(self) -> Agent:
        """Create research synthesizer agent"""
        return Agent(
            role="Research Synthesizer",
            goal="Synthesize evidence into coherent, insightful research reports",
            backstory="""You are a master synthesizer who excels at combining 
            diverse pieces of evidence into comprehensive, well-structured reports. 
            You identify patterns, draw insights, and present findings clearly.""",
            verbose=True,
            allow_delegation=False,
            max_iter=3,
            memory=True
        )
    
    def create_quality_agent(self) -> Agent:
        """Create quality assurance agent"""
        return Agent(
            role="Quality Assurance Specialist",
            goal="Ensure research meets all quality standards and requirements",
            backstory="""You are a quality assurance expert who ensures all 
            research outputs meet the highest standards for accuracy, completeness, 
            and reliability.""",
            verbose=True,
            allow_delegation=False,
            max_iter=2,
            memory=True
        )


class ResearchTasks:
    """Factory for creating research tasks"""
    
    @staticmethod
    def create_planning_task(request: ResearchRequest, agent: Agent) -> Task:
        """Create research planning task"""
        return Task(
            description=f"""
            Create a comprehensive research plan for: {request.topic}
            
            Requirements:
            - Identify 3-7 key subtopics based on depth level ({request.depth})
            - Generate specific search queries for each subtopic
            - Define quality criteria and methodology
            - Consider constraints: {request.constraints}
            
            Output: Detailed research plan with subtopics and search strategies
            """,
            agent=agent,
            expected_output="Research plan with subtopics and methodology"
        )
    
    @staticmethod
    def create_collection_task(subtopic: str, queries: List[str], agent: Agent) -> Task:
        """Create evidence collection task"""
        return Task(
            description=f"""
            Collect evidence for subtopic: {subtopic}
            
            Search queries to use:
            {chr(10).join(f"- {q}" for q in queries)}
            
            Requirements:
            - Find diverse, authoritative sources
            - Extract relevant claims and supporting text
            - Record source metadata
            - Aim for 10-20 pieces of evidence
            
            Output: List of evidence cards with complete metadata
            """,
            agent=agent,
            expected_output="Collection of evidence cards"
        )
    
    @staticmethod
    def create_verification_task(evidence: List[EvidenceCard], agent: Agent) -> Task:
        """Create evidence verification task"""
        return Task(
            description=f"""
            Verify the quality and accuracy of {len(evidence)} evidence pieces.
            
            Requirements:
            - Check source credibility
            - Identify potential bias
            - Verify factual claims where possible
            - Score relevance and confidence
            - Flag any quality issues
            
            Output: Verified evidence with quality scores and indicators
            """,
            agent=agent,
            expected_output="Verified evidence with quality metrics"
        )
    
    @staticmethod
    def create_synthesis_task(
        topic: str,
        evidence: List[EvidenceCard],
        agent: Agent
    ) -> Task:
        """Create research synthesis task"""
        return Task(
            description=f"""
            Synthesize research findings on: {topic}
            
            Available evidence: {len(evidence)} pieces
            
            Requirements:
            - Create executive summary
            - Organize findings into logical sections
            - Identify key insights and patterns
            - Note limitations and gaps
            - Provide recommendations
            
            Output: Comprehensive research report
            """,
            agent=agent,
            expected_output="Complete research report"
        )
    
    @staticmethod
    def create_quality_task(report: Any, requirements: Dict, agent: Agent) -> Task:
        """Create quality assurance task"""
        return Task(
            description=f"""
            Review research report for quality and completeness.
            
            Quality criteria:
            - Accuracy of information
            - Completeness of coverage
            - Logical structure
            - Evidence support for claims
            - Clarity of presentation
            
            Requirements: {requirements}
            
            Output: Quality assessment with improvement suggestions
            """,
            agent=agent,
            expected_output="Quality assessment report"
        )


class ResearchCrew:
    """Orchestrates the research crew"""
    
    def __init__(self, config: Config):
        self.config = config
        self.agent_factory = ResearchAgents(config)
        self.task_factory = ResearchTasks()
    
    def create_crew(self, request: ResearchRequest) -> Crew:
        """Create a crew for the research request"""
        
        # Create agents
        planner = self.agent_factory.create_planner_agent()
        collector = self.agent_factory.create_collector_agent()
        verifier = self.agent_factory.create_verifier_agent()
        synthesizer = self.agent_factory.create_synthesizer_agent()
        qa_specialist = self.agent_factory.create_quality_agent()
        
        # Create tasks (simplified for initial crew creation)
        planning_task = self.task_factory.create_planning_task(request, planner)
        
        # Create crew
        crew = Crew(
            agents=[planner, collector, verifier, synthesizer, qa_specialist],
            tasks=[planning_task],  # Additional tasks added dynamically
            process=Process.sequential,
            verbose=True,
            memory=True
        )
        
        return crew
    
    def execute_research(self, request: ResearchRequest) -> Dict[str, Any]:
        """Execute the research process"""
        crew = self.create_crew(request)
        
        try:
            result = crew.kickoff()
            return {
                "status": "success",
                "result": result
            }
        except Exception as e:
            logger.error(f"Research execution failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }