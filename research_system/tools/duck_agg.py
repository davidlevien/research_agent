"""
DuckDB-based aggregation for fast analytics on evidence cards
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


def render_source_quality_md(jsonl_path: str) -> str:
    """
    Generate source quality markdown table using DuckDB.
    Fast and efficient for large evidence sets.
    """
    try:
        import duckdb
        
        # Connect to in-memory database
        con = duckdb.connect()
        
        # Read JSONL file into DuckDB
        con.execute("""
            CREATE TABLE cards AS 
            SELECT * FROM read_json_auto(?, 
                format='newline_delimited',
                maximum_object_size=10485760
            )
        """, [jsonl_path])
        
        # Analyze source quality
        df = con.execute("""
            WITH source_metrics AS (
                SELECT
                    COALESCE(source_domain, 'unknown') AS domain,
                    COUNT(*) AS total_cards,
                    COUNT(DISTINCT COALESCE(quote_span, claim, snippet, title)) AS unique_claims,
                    AVG(COALESCE(credibility_score, 0.5)) AS avg_credibility,
                    AVG(COALESCE(confidence, 0.5)) AS avg_confidence,
                    MIN(date) AS first_seen,
                    MAX(date) AS last_seen,
                    COUNT(DISTINCT provider) AS provider_count,
                    COUNT(DISTINCT COALESCE(claim, snippet)) AS distinct_claims
                FROM cards
                GROUP BY 1
                HAVING COUNT(*) > 0
            )
            SELECT 
                domain,
                total_cards,
                unique_claims,
                ROUND(avg_credibility, 3) AS avg_credibility,
                ROUND(avg_confidence, 3) AS avg_confidence,
                CAST(first_seen AS VARCHAR) AS first_seen,
                CAST(last_seen AS VARCHAR) AS last_seen,
                provider_count,
                ROUND(CAST(distinct_claims AS FLOAT) / CAST(total_cards AS FLOAT), 3) AS uniqueness_ratio
            FROM source_metrics
            ORDER BY avg_credibility DESC, total_cards DESC
        """).fetch_df()
        
        con.close()
        
        # Format as markdown table
        header = "| Domain | Cards | Unique Claims | Avg Credibility | Avg Confidence | First Seen | Last Seen | Providers | Uniqueness |\n"
        header += "|---|---:|---:|---:|---:|---|---|---:|---:|\n"
        
        rows = []
        for _, row in df.iterrows():
            first_seen = str(row.first_seen)[:19] if row.first_seen else "N/A"
            last_seen = str(row.last_seen)[:19] if row.last_seen else "N/A"
            
            rows.append(
                f"| {row.domain} | {row.total_cards} | {row.unique_claims} | "
                f"{row.avg_credibility:.3f} | {row.avg_confidence:.3f} | "
                f"{first_seen} | {last_seen} | {row.provider_count} | {row.uniqueness_ratio:.3f} |"
            )
        
        return header + "\n".join(rows)
        
    except ImportError:
        logger.warning("DuckDB not available, returning empty table")
        return "| Domain | Cards | Unique Claims | Avg Credibility | Avg Confidence | First Seen | Last Seen |\n|---|---|---|---|---|---|---|\n| DuckDB not installed | 0 | 0 | 0 | 0 | N/A | N/A |"
    except Exception as e:
        logger.error(f"DuckDB aggregation failed: {e}")
        return f"| Error | {str(e)} |\n|---|---|"


def analyze_triangulation(jsonl_path: str) -> Dict[str, Any]:
    """
    Analyze triangulation patterns in evidence cards using DuckDB.
    """
    try:
        import duckdb
        
        con = duckdb.connect()
        
        # Read evidence cards
        con.execute("""
            CREATE TABLE cards AS 
            SELECT * FROM read_json_auto(?, 
                format='newline_delimited',
                maximum_object_size=10485760
            )
        """, [jsonl_path])
        
        # Analyze claim corroboration
        result = con.execute("""
            WITH claim_groups AS (
                SELECT 
                    COALESCE(claim, snippet, title) AS claim_text,
                    COUNT(DISTINCT source_domain) AS domain_count,
                    COUNT(*) AS total_mentions,
                    LIST(DISTINCT source_domain) AS domains,
                    AVG(credibility_score) AS avg_credibility
                FROM cards
                WHERE claim IS NOT NULL OR snippet IS NOT NULL OR title IS NOT NULL
                GROUP BY 1
                HAVING COUNT(*) >= 2
            ),
            stats AS (
                SELECT
                    COUNT(*) AS total_claims,
                    COUNT(CASE WHEN domain_count >= 2 THEN 1 END) AS triangulated_claims,
                    COUNT(CASE WHEN domain_count >= 3 THEN 1 END) AS highly_triangulated,
                    AVG(domain_count) AS avg_domains_per_claim,
                    MAX(domain_count) AS max_domains_per_claim
                FROM claim_groups
            )
            SELECT * FROM stats
        """).fetchone()
        
        if result:
            total, triangulated, highly_tri, avg_domains, max_domains = result
            
            triangulation_rate = triangulated / max(1, total)
            high_triangulation_rate = highly_tri / max(1, total)
            
            analysis = {
                "total_corroborated_claims": total,
                "triangulated_claims": triangulated,
                "highly_triangulated_claims": highly_tri,
                "triangulation_rate": round(triangulation_rate, 3),
                "high_triangulation_rate": round(high_triangulation_rate, 3),
                "avg_domains_per_claim": round(avg_domains or 0, 2),
                "max_domains_per_claim": max_domains or 0
            }
        else:
            analysis = {
                "total_corroborated_claims": 0,
                "triangulated_claims": 0,
                "highly_triangulated_claims": 0,
                "triangulation_rate": 0,
                "high_triangulation_rate": 0,
                "avg_domains_per_claim": 0,
                "max_domains_per_claim": 0
            }
        
        con.close()
        return analysis
        
    except Exception as e:
        logger.error(f"Triangulation analysis failed: {e}")
        return {
            "error": str(e),
            "triangulation_rate": 0
        }


def generate_evidence_summary(jsonl_path: str) -> Dict[str, Any]:
    """
    Generate comprehensive evidence summary statistics using DuckDB.
    """
    try:
        import duckdb
        
        con = duckdb.connect()
        
        # Read evidence cards
        con.execute("""
            CREATE TABLE cards AS 
            SELECT * FROM read_json_auto(?, 
                format='newline_delimited',
                maximum_object_size=10485760
            )
        """, [jsonl_path])
        
        # Comprehensive statistics
        summary = {}
        
        # Basic counts
        basic_stats = con.execute("""
            SELECT
                COUNT(*) as total_cards,
                COUNT(DISTINCT source_domain) as unique_domains,
                COUNT(DISTINCT provider) as unique_providers,
                COUNT(DISTINCT COALESCE(claim, snippet, title)) as unique_claims,
                COUNT(DISTINCT DATE(date)) as date_range_days
            FROM cards
        """).fetchone()
        
        summary["total_evidence_cards"] = basic_stats[0]
        summary["unique_domains"] = basic_stats[1]
        summary["unique_providers"] = basic_stats[2]
        summary["unique_claims"] = basic_stats[3]
        summary["date_range_days"] = basic_stats[4]
        
        # Quality metrics
        quality = con.execute("""
            SELECT
                AVG(credibility_score) as avg_credibility,
                STDDEV(credibility_score) as credibility_stddev,
                AVG(confidence) as avg_confidence,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY credibility_score) as median_credibility
            FROM cards
        """).fetchone()
        
        summary["avg_credibility"] = round(quality[0] or 0, 3)
        summary["credibility_stddev"] = round(quality[1] or 0, 3)
        summary["avg_confidence"] = round(quality[2] or 0, 3)
        summary["median_credibility"] = round(quality[3] or 0, 3)
        
        # Provider distribution
        providers = con.execute("""
            SELECT 
                provider,
                COUNT(*) as count
            FROM cards
            GROUP BY provider
            ORDER BY count DESC
            LIMIT 10
        """).fetchall()
        
        summary["top_providers"] = [
            {"provider": p[0], "count": p[1]} for p in providers
        ]
        
        # Domain distribution
        domains = con.execute("""
            SELECT 
                source_domain,
                COUNT(*) as count,
                AVG(credibility_score) as avg_cred
            FROM cards
            GROUP BY source_domain
            ORDER BY count DESC
            LIMIT 10
        """).fetchall()
        
        summary["top_domains"] = [
            {"domain": d[0], "count": d[1], "avg_credibility": round(d[2] or 0, 3)} 
            for d in domains
        ]
        
        # Temporal distribution
        temporal = con.execute("""
            SELECT
                MIN(date) as earliest_date,
                MAX(date) as latest_date,
                COUNT(DISTINCT DATE(date)) as unique_dates
            FROM cards
            WHERE date IS NOT NULL
        """).fetchone()
        
        summary["date_range"] = {
            "earliest": str(temporal[0])[:10] if temporal[0] else None,
            "latest": str(temporal[1])[:10] if temporal[1] else None,
            "unique_dates": temporal[2] or 0
        }
        
        con.close()
        return summary
        
    except Exception as e:
        logger.error(f"Evidence summary generation failed: {e}")
        return {"error": str(e)}


def export_to_parquet(jsonl_path: str, output_path: str = None) -> Optional[str]:
    """
    Convert JSONL evidence cards to Parquet format for efficient storage and analysis.
    """
    try:
        import duckdb
        
        if output_path is None:
            output_path = jsonl_path.replace('.jsonl', '.parquet')
        
        con = duckdb.connect()
        
        # Read and export
        con.execute("""
            COPY (
                SELECT * FROM read_json_auto(?, 
                    format='newline_delimited',
                    maximum_object_size=10485760
                )
            ) TO ? (FORMAT PARQUET, COMPRESSION 'SNAPPY')
        """, [jsonl_path, output_path])
        
        con.close()
        
        logger.info(f"Exported evidence to Parquet: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Parquet export failed: {e}")
        return None


def validate_evidence_schema(jsonl_path: str) -> Dict[str, Any]:
    """
    Validate evidence card schema and data quality using DuckDB.
    """
    try:
        import duckdb
        
        con = duckdb.connect()
        
        # Read evidence cards
        con.execute("""
            CREATE TABLE cards AS 
            SELECT * FROM read_json_auto(?, 
                format='newline_delimited',
                maximum_object_size=10485760
            )
        """, [jsonl_path])
        
        # Check for required fields and data quality
        validation = con.execute("""
            SELECT
                COUNT(*) as total_records,
                COUNT(title) as has_title,
                COUNT(url) as has_url,
                COUNT(source_domain) as has_domain,
                COUNT(date) as has_date,
                COUNT(claim) as has_claim,
                COUNT(snippet) as has_snippet,
                COUNT(credibility_score) as has_credibility,
                COUNT(CASE WHEN credibility_score BETWEEN 0 AND 1 THEN 1 END) as valid_credibility,
                COUNT(CASE WHEN confidence BETWEEN 0 AND 1 THEN 1 END) as valid_confidence
            FROM cards
        """).fetchone()
        
        total = validation[0]
        
        issues = []
        if validation[1] < total * 0.9:
            issues.append(f"Missing titles: {total - validation[1]}/{total}")
        if validation[2] < total * 0.95:
            issues.append(f"Missing URLs: {total - validation[2]}/{total}")
        if validation[3] < total * 0.95:
            issues.append(f"Missing domains: {total - validation[3]}/{total}")
        if validation[8] < validation[7]:
            issues.append(f"Invalid credibility scores: {validation[7] - validation[8]}")
        
        result = {
            "total_records": total,
            "schema_complete": len(issues) == 0,
            "issues": issues,
            "field_coverage": {
                "title": round(validation[1] / max(1, total), 3),
                "url": round(validation[2] / max(1, total), 3),
                "domain": round(validation[3] / max(1, total), 3),
                "date": round(validation[4] / max(1, total), 3),
                "claim": round(validation[5] / max(1, total), 3),
                "snippet": round(validation[6] / max(1, total), 3),
                "credibility": round(validation[7] / max(1, total), 3)
            }
        }
        
        con.close()
        return result
        
    except Exception as e:
        logger.error(f"Schema validation failed: {e}")
        return {"error": str(e), "schema_complete": False}