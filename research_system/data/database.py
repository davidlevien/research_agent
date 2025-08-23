# research_system/data/database.py
"""
Database models and connection management
"""

import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, 
    Boolean, Text, JSON, ForeignKey, Index, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import QueuePool
import structlog

logger = structlog.get_logger()

Base = declarative_base()


class ResearchRequest(Base):
    """Research request model"""
    __tablename__ = "research_requests"
    
    id = Column(String(36), primary_key=True)
    topic = Column(String(500), nullable=False)
    depth = Column(String(20), nullable=False)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    total_cost_usd = Column(Float, default=0.0)
    execution_time_seconds = Column(Float)
    evidence_count = Column(Integer, default=0)
    
    # Relationships
    evidence = relationship("EvidenceCard", back_populates="request")
    metrics = relationship("ResearchMetrics", back_populates="request")


class EvidenceCard(Base):
    """Evidence card model"""
    __tablename__ = "evidence_cards"
    
    id = Column(String(36), primary_key=True)
    request_id = Column(String(36), ForeignKey("research_requests.id"))
    subtopic_name = Column(String(200), nullable=False)
    claim = Column(Text, nullable=False)
    supporting_text = Column(Text, nullable=False)
    source_url = Column(String(500), nullable=False)
    source_title = Column(String(500), nullable=False)
    source_domain = Column(String(100), nullable=False)
    publication_date = Column(DateTime)
    author = Column(String(200))
    credibility_score = Column(Float, nullable=False)
    relevance_score = Column(Float, nullable=False)
    is_primary_source = Column(Boolean, default=False)
    collected_at = Column(DateTime, default=datetime.utcnow)
    search_provider = Column(String(50))
    entities = Column(JSON)
    quality_indicators = Column(JSON)
    bias_indicators = Column(JSON)
    
    # Relationships
    request = relationship("ResearchRequest", back_populates="evidence")
    
    # Indexes
    __table_args__ = (
        Index("idx_request_id", "request_id"),
        Index("idx_source_domain", "source_domain"),
        Index("idx_credibility_score", "credibility_score"),
        Index("idx_collected_at", "collected_at"),
    )


class ResearchMetrics(Base):
    """Research metrics model"""
    __tablename__ = "research_metrics"
    
    id = Column(String(36), primary_key=True)
    request_id = Column(String(36), ForeignKey("research_requests.id"))
    total_sources_examined = Column(Integer, default=0)
    total_evidence_collected = Column(Integer, default=0)
    unique_domains = Column(Integer, default=0)
    avg_credibility_score = Column(Float, default=0.0)
    avg_relevance_score = Column(Float, default=0.0)
    execution_time_seconds = Column(Float, default=0.0)
    total_cost_usd = Column(Float, default=0.0)
    api_calls_made = Column(Integer, default=0)
    cache_hit_rate = Column(Float, default=0.0)
    errors_encountered = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    request = relationship("ResearchRequest", back_populates="metrics")


class CostRecord(Base):
    """Cost tracking model"""
    __tablename__ = "cost_records"
    
    id = Column(String(36), primary_key=True)
    request_id = Column(String(36), ForeignKey("research_requests.id"))
    provider = Column(String(50), nullable=False)
    operation = Column(String(100), nullable=False)
    cost_usd = Column(Float, nullable=False)
    units = Column(Integer, default=1)
    unit_type = Column(String(20), default="request")
    metadata = Column(JSON)
    recorded_at = Column(DateTime, default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index("idx_request_id", "request_id"),
        Index("idx_provider", "provider"),
        Index("idx_recorded_at", "recorded_at"),
    )


class CacheEntry(Base):
    """Cache entry model"""
    __tablename__ = "cache_entries"
    
    id = Column(String(36), primary_key=True)
    cache_key = Column(String(255), nullable=False, unique=True)
    cache_value = Column(Text, nullable=False)
    ttl_seconds = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime, default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index("idx_cache_key", "cache_key"),
        Index("idx_expires_at", "expires_at"),
        Index("idx_last_accessed", "last_accessed"),
    )


class DatabaseManager:
    """Database connection and session management"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.engine = None
        self.async_engine = None
        self.SessionLocal = None
        self.AsyncSessionLocal = None
        self._setup_engines()
    
    def _setup_engines(self):
        """Setup database engines"""
        
        database_url = self.config.get("database_url")
        if not database_url:
            raise ValueError("Database URL not configured")
        
        # Sync engine
        self.engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=self.config.get("pool_size", 20),
            max_overflow=self.config.get("max_overflow", 0),
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=self.config.get("echo", False)
        )
        
        # Async engine
        if database_url.startswith("postgresql://"):
            async_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
        else:
            async_url = database_url
        
        self.async_engine = create_async_engine(
            async_url,
            pool_size=self.config.get("pool_size", 20),
            max_overflow=self.config.get("max_overflow", 0),
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=self.config.get("echo", False)
        )
        
        # Session factories
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False
        )
        
        self.AsyncSessionLocal = sessionmaker(
            bind=self.async_engine,
            class_=AsyncSession,
            autocommit=False,
            autoflush=False
        )
    
    def create_tables(self):
        """Create all tables"""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created")
    
    def drop_tables(self):
        """Drop all tables"""
        Base.metadata.drop_all(bind=self.engine)
        logger.info("Database tables dropped")
    
    def get_session(self):
        """Get database session"""
        return self.SessionLocal()
    
    async def get_async_session(self):
        """Get async database session"""
        return self.AsyncSessionLocal()
    
    async def close(self):
        """Close database connections"""
        if self.async_engine:
            await self.async_engine.dispose()
        if self.engine:
            self.engine.dispose()
        logger.info("Database connections closed")


class DatabaseRepository:
    """Database operations repository"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    async def save_research_request(self, request_data: Dict[str, Any]) -> str:
        """Save research request"""
        
        async with self.db_manager.get_async_session() as session:
            request = ResearchRequest(**request_data)
            session.add(request)
            await session.commit()
            await session.refresh(request)
            return request.id
    
    async def get_research_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get research request by ID"""
        
        async with self.db_manager.get_async_session() as session:
            request = await session.get(ResearchRequest, request_id)
            if request:
                return {
                    "id": request.id,
                    "topic": request.topic,
                    "depth": request.depth,
                    "status": request.status,
                    "created_at": request.created_at,
                    "completed_at": request.completed_at,
                    "total_cost_usd": request.total_cost_usd,
                    "execution_time_seconds": request.execution_time_seconds,
                    "evidence_count": request.evidence_count
                }
            return None
    
    async def save_evidence_cards(self, evidence_data: List[Dict[str, Any]]) -> List[str]:
        """Save evidence cards"""
        
        async with self.db_manager.get_async_session() as session:
            evidence_cards = []
            for data in evidence_data:
                evidence = EvidenceCard(**data)
                evidence_cards.append(evidence)
                session.add(evidence)
            
            await session.commit()
            
            # Refresh to get IDs
            for evidence in evidence_cards:
                await session.refresh(evidence)
            
            return [evidence.id for evidence in evidence_cards]
    
    async def get_evidence_by_request(self, request_id: str) -> List[Dict[str, Any]]:
        """Get evidence cards by request ID"""
        
        async with self.db_manager.get_async_session() as session:
            evidence_cards = await session.query(EvidenceCard).filter(
                EvidenceCard.request_id == request_id
            ).all()
            
            return [
                {
                    "id": evidence.id,
                    "subtopic_name": evidence.subtopic_name,
                    "claim": evidence.claim,
                    "supporting_text": evidence.supporting_text,
                    "source_url": evidence.source_url,
                    "source_title": evidence.source_title,
                    "source_domain": evidence.source_domain,
                    "credibility_score": evidence.credibility_score,
                    "relevance_score": evidence.relevance_score,
                    "collected_at": evidence.collected_at
                }
                for evidence in evidence_cards
            ]
    
    async def save_cost_record(self, cost_data: Dict[str, Any]) -> str:
        """Save cost record"""
        
        async with self.db_manager.get_async_session() as session:
            cost_record = CostRecord(**cost_data)
            session.add(cost_record)
            await session.commit()
            await session.refresh(cost_record)
            return cost_record.id
    
    async def get_daily_cost(self, date: datetime) -> float:
        """Get total cost for a specific date"""
        
        async with self.db_manager.get_async_session() as session:
            result = await session.query(
                func.sum(CostRecord.cost_usd)
            ).filter(
                func.date(CostRecord.recorded_at) == date.date()
            ).scalar()
            
            return result or 0.0
    
    async def cleanup_expired_cache(self):
        """Clean up expired cache entries"""
        
        async with self.db_manager.get_async_session() as session:
            await session.query(CacheEntry).filter(
                CacheEntry.expires_at < datetime.utcnow()
            ).delete()
            await session.commit()


# Global database manager instance
db_manager = None


def init_database(config: Dict[str, Any]):
    """Initialize global database"""
    global db_manager
    db_manager = DatabaseManager(config)
    return db_manager


def get_db_manager():
    """Get global database manager"""
    return db_manager