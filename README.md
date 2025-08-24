# Domain-Agnostic PE-Grade Research Intelligence System

A production-ready, domain-aware research automation system with discipline-specific routing, advanced triangulation, and enterprise-grade evidence validation. Automatically adapts to any research domain (medicine, finance, law, technology, etc.) with specialized connectors and policies.

## 🚀 Key Features

### Core Capabilities
- **Domain-Agnostic Routing**: Automatic discipline detection (9 domains) with specialized policies
- **Parallel Multi-Provider Search**: Simultaneous execution across Tavily, Brave, Serper, SerpAPI, NPS
- **Primary Source Connectors**: Direct integration with Crossref, OpenAlex, PubMed, GDELT, Unpaywall, Semantic Scholar, CORE
- **Advanced Triangulation**: SBERT semantic clustering + Structured claim matching + MinHash syndication detection
- **Schema-Enforced Evidence**: JSON schema validation with persistent identifiers (DOI, PMID, etc.)
- **Controversy Detection**: Automatic identification and clustering of disputed claims
- **7 Mandatory Deliverables**: Enforced output contract in strict mode
- **Real-time Validation**: HTTP reachability, citation verification, quality assessment

### PE-Level Enhancements
- **Semantic Clustering**: Sentence-BERT embeddings for claim similarity (86%+ cosine threshold)
- **Syndication Control**: MinHash LSH for near-duplicate detection across domains (92% threshold)
- **Structured Claim Extraction**: Entity|Metric|Period normalization for precise triangulation
- **Content Extraction**: Trafilatura + Extruct for structured data (JSON-LD, metadata)
- **PDF Processing**: PyMuPDF/pdfplumber for academic papers with table extraction
- **Fast Analytics**: DuckDB for large-scale evidence aggregation
- **URL Normalization**: w3lib + tldextract for canonical URLs
- **Contradiction Detection**: Automatic identification of conflicting numeric claims
- **Adaptive Research Expansion (AREX)**: Refined queries with semantic reranking for uncorroborated claims
- **Snapshot Archiving**: Optional Wayback Machine integration
- **DOI Fallback Chain**: Crossref → Unpaywall → Semantic Scholar → CORE for gated content
- **Entity Normalization**: Canonical mapping for entities (USA/US/United States → united states)
- **Geographic Normalization**: ISO-3166 country code standardization
- **Domain Reputation**: Tranco ranking integration for source quality
- **Polite Crawling**: Robots.txt compliance and rate limiting
- **HTTP Caching**: ETag/Last-Modified aware caching for efficiency
- **WARC Archiving**: Local provenance capture for auditing
- **Language Detection**: Multi-language support with translation preparation

### Discipline-Specific Features
- **Medicine**: PubMed integration, clinical trial detection, 70% primary source requirement
- **Science**: arXiv/DOI prioritization, dataset detection, replication focus
- **Finance**: SEC EDGAR placeholders, quarterly report detection, FRED/OECD ready
- **Law/Policy**: EUR-Lex ready, case law detection, legislative tracking
- **Security**: CVE/NVD ready, vulnerability tracking, patch analysis
- **Travel/Tourism**: UNWTO/IATA/WTTC focus with paywall bypass, occupancy data, recovery metrics
- **Climate**: IPCC/NOAA integration ready, emissions tracking, model data
- **Technology**: GitHub/RFC detection, benchmark analysis, API documentation

## 📋 Prerequisites

- Python 3.9+
- API Keys (see Configuration)
- Optional: Redis (caching), PostgreSQL (persistence)

## 🔧 Installation

```bash
# Clone repository
git clone https://github.com/your-org/research_agent.git
cd research_agent

# Install core dependencies
pip install -e .

# Install enhanced dependencies (recommended)
pip install -r requirements.extra.txt

# Or install everything
pip install -e ".[dev]" && pip install -r requirements.extra.txt
```

## ⚙️ Configuration

### Required Environment Variables

Create a `.env` file:

```bash
# LLM Provider (choose one)
LLM_PROVIDER=openai  # or "anthropic" or "azure_openai"
OPENAI_API_KEY=sk-...  # Required for openai

# Search Providers (at least one required)
SEARCH_PROVIDERS=tavily,brave,serper  # Comma-separated list
TAVILY_API_KEY=tvly-...
BRAVE_API_KEY=BSA...
SERPER_API_KEY=...

# Core Enhancement Flags
ENABLE_PRIMARY_CONNECTORS=true  # Use discipline-specific connectors
ENABLE_SBERT_CLUSTERING=true    # Semantic similarity clustering
ENABLE_MINHASH_DEDUP=true       # Syndication detection
ENABLE_EXTRACT=true             # Enhanced content extraction
ENABLE_DUCKDB_AGG=true          # Fast analytics

# Open Access & Fallback Features (Recommended)
ENABLE_UNPAYWALL=true           # Unpaywall OA resolver for gated content
ENABLE_S2=true                  # Semantic Scholar fallback
ENABLE_CORE=true                # CORE Academic fallback

# Content Processing Features
ENABLE_PDF_TABLES=true          # Extract data from PDF tables
ENABLE_LANGDETECT=true          # Language detection for multi-language sources

# Crawling & Caching Features
ENABLE_HTTP_CACHE=true          # HTTP caching with ETag support
ENABLE_POLITENESS=true          # Robots.txt compliance
ENABLE_WARC=false               # WARC archiving (off by default)
HTTP_CACHE_DIR=./.http_cache    # Directory for HTTP cache

# Domain Quality Features
ENABLE_TRANCO=true              # Tranco domain reputation scoring
ENABLE_GEO_NORM=true            # Geographic normalization

# Quality Thresholds
MIN_TRIANGULATION_RATE=0.35     # Minimum corroboration required
MIN_CREDIBILITY=0.6             # Minimum source credibility
MAX_DOMAIN_CONCENTRATION=0.25   # Maximum single-domain concentration
STRICT=false                    # Fail fast on quality violations with detailed diagnostics
```

## 🎯 Usage

### Basic Research
```bash
# Simple topic research
python -m research_system --topic "global tourism recovery 2025"

# With depth control
python -m research_system --topic "COVID-19 vaccine efficacy" --depth deep

# Strict mode (enforces quality thresholds)
python -m research_system --topic "quantum computing advances" --strict
```

### Domain-Specific Research
The system automatically detects the domain and applies appropriate policies:

```bash
# Medical research (auto-routes to PubMed, WHO, CDC)
python -m research_system --topic "mRNA vaccine side effects clinical trials"

# Financial research (auto-routes to SEC, FRED, OECD)
python -m research_system --topic "Tesla Q3 2024 earnings analysis SEC filing"

# Security research (ready for NVD, MITRE integration)
python -m research_system --topic "CVE-2024-1234 vulnerability exploitation"

# Climate research (ready for IPCC, NOAA integration)
python -m research_system --topic "global temperature anomalies 2024 IPCC"

# Tourism research (with UNWTO paywall bypass via DOI fallback)
python -m research_system --topic "international tourist arrivals Q1 2025 recovery"
```

### Advanced Features
```bash
# Custom output directory
python -m research_system --topic "renewable energy trends" --output-dir my_research/

# Verbose mode with detailed logging
LOG_LEVEL=DEBUG python -m research_system --topic "blockchain consensus mechanisms"

# With maximum cost limit
python -m research_system --topic "AI regulation EU" --max-cost 5.00

# Full feature testing
python run_full_features.py --topic "global tourism recovery" --strict
```

## 📊 Outputs

The system generates 7 mandatory deliverables:

1. **plan.md** - Research plan with discipline routing and anchor queries
2. **source_strategy.md** - Source selection strategy and priorities
3. **acceptance_guardrails.md** - Quality criteria and validation results
4. **evidence_cards.jsonl** - Structured evidence with metadata and reachability scores
5. **source_quality_table.md** - Domain analysis and credibility metrics
6. **final_report.md** - Synthesized findings with triangulation data
7. **citation_checklist.md** - Citation validation and compliance

Additional outputs when enhanced features are enabled:
- **triangulation.json** - Paraphrase clustering results with similarity scores
- **triangulation_breakdown.md** - Detailed triangulation analysis with uncorroborated keys
- **run_manifest.json** - Execution metadata with discipline, providers, and settings
- **GAPS_AND_RISKS.md** - Generated in strict mode when thresholds not met with actionable remediation

## 🧪 Testing

```bash
# Test core functionality
python -m pytest tests/

# Test normalization features
python -m pytest tests/test_normalizations.py

# Test claim processing
python -m pytest tests/test_claim_sentences.py

# Test deduplication
python -m pytest tests/test_dedup.py

# Test clustering
python -m pytest tests/test_cluster_paraphrase.py

# Test enhanced features
python test_enhanced_features.py

# Test domain routing
python test_routing_system.py

# Integration tests
python -m pytest tests/integration/ -v
```

## 🏗️ Architecture

### System Components
```
research_system/
├── router.py              # Domain classification engine
├── policy.py              # Discipline-specific policies
├── orchestrator.py        # Core pipeline orchestration with AREX refinement
├── models.py              # Data models with reachability field
├── scoring.py             # Confidence scoring with domain priors
├── controversy.py         # Controversy detection
├── tools/
│   ├── anchor.py          # Discipline-aware query building
│   ├── claims.py          # SBERT clustering
│   ├── claim_struct.py    # Structured claim extraction with entity normalization
│   ├── claim_select.py    # Sentence selection for quotes
│   ├── dedup.py           # MinHash deduplication
│   ├── embed_cluster.py   # Hybrid clustering
│   ├── fetch.py           # Enhanced extraction with DOI fallback chain
│   ├── pdf_extract.py     # PDF text extraction
│   ├── pdf_tables.py      # PDF table extraction for stats
│   ├── duck_agg.py        # DuckDB analytics
│   ├── url_norm.py        # URL canonicalization
│   ├── metrics_lexicon.py # Metric normalization mappings
│   ├── period_norm.py     # Temporal period normalization
│   ├── num_norm.py        # Number and unit normalization
│   ├── entity_norm.py     # Entity canonicalization
│   ├── geo_norm.py        # ISO-3166 geographic normalization
│   ├── contradictions.py  # Numeric contradiction detection
│   ├── arex_refine.py     # AREX query refinement with negatives
│   ├── arex_rerank.py     # AREX semantic reranking
│   ├── doi_tools.py       # DOI extraction and Crossref API
│   ├── unpaywall.py       # Unpaywall OA resolver
│   ├── politeness.py      # Robots.txt and rate limiting
│   ├── cache.py           # HTTP caching with conditional requests
│   ├── warc_dump.py       # WARC archiving
│   ├── langpipe.py        # Language detection
│   ├── tranco_prior.py    # Domain reputation scoring
│   └── observability.py   # Triangulation breakdown and diagnostics
└── connectors/
    ├── crossref.py        # Academic papers
    ├── openalex.py        # Open academic data
    ├── pubmed.py          # Medical literature
    ├── gdelt.py           # Global news
    ├── semantics.py       # Semantic Scholar API
    ├── core.py            # CORE Academic API
    ├── edgar.py           # SEC filings (placeholder)
    └── eurlex.py          # EU law (placeholder)
```

### Discipline Routing Flow
1. Topic analyzed for discipline markers
2. Discipline determines policy (thresholds, connectors, anchors)
3. Anchor queries target discipline-specific sources
4. Connectors fetch from authoritative databases
5. DOI fallback chain bypasses paywalls (Crossref → Unpaywall → S2 → CORE)
6. Entity normalization ensures structured key collision
7. AREX uses refined queries with primary hints and negative terms
8. Semantic reranking filters tangential AREX results
9. Domain priors weight credibility by discipline
10. Clustering uses discipline-tuned thresholds
11. Guardrails enforce discipline-specific minimums
12. Observability reports uncorroborated keys and gaps

## 🔒 Security & Compliance

- Input sanitization and validation
- Domain whitelisting for primary sources
- No storage of API keys in code
- Optional PII detection (Presidio)
- Audit logging for all searches
- GDPR-compliant data handling
- Robots.txt compliance when ENABLE_POLITENESS=true
- Rate limiting to prevent server overload

## 📈 Performance

- Parallel search across all providers
- Async/await for I/O operations
- DuckDB for sub-second analytics on 10K+ cards
- MinHash O(n) deduplication
- SBERT GPU acceleration supported
- Circuit breakers prevent cascade failures
- HTTP caching reduces redundant fetches
- Conditional requests minimize bandwidth

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

MIT License - see [LICENSE](LICENSE) file.

## 🆘 Support

- Documentation: [docs/](docs/)
- Issues: [GitHub Issues](https://github.com/your-org/research_agent/issues)
- Email: research-support@your-org.com

## 🎓 Citation

If you use this system in academic work:

```bibtex
@software{research_agent_2024,
  title = {Domain-Agnostic PE-Grade Research Intelligence System},
  author = {Your Organization},
  year = {2024},
  url = {https://github.com/your-org/research_agent}
}
```

## 🔄 Recent Enhancements (v2.0)

### Paywall Bypass Strategy
- Automatic DOI extraction from gated URLs
- Crossref metadata fallback for abstracts and dates
- Unpaywall integration for Open Access versions
- Semantic Scholar and CORE as secondary sources
- Maintains primary source attribution while bypassing gates

### Entity Convergence
- Comprehensive entity aliasing (US/USA/United States)
- Organization normalization (UN Tourism/UNWTO)
- Geographic standardization via ISO-3166
- Improved structured key collision for triangulation

### AREX Refinement
- Discipline-aware negative terms to prevent drift
- Primary site hints (site:unwto.org, site:iata.org)
- Semantic reranking using SBERT or Jaccard fallback
- Filters tangential results by similarity threshold

### Stability & Performance
- HTTP caching with ETag/Last-Modified support
- Polite crawling with robots.txt compliance
- Host-level rate limiting
- WARC archiving for provenance
- PDF table extraction for buried statistics
- Language detection for multi-language sources

These enhancements significantly improve:
- Primary source accessibility (bypassing UNWTO paywalls)
- Triangulation rates (entity normalization increases key collisions)
- AREX precision (semantic filtering reduces noise)
- System stability (caching and rate limiting prevent failures)
- Evidence completeness (PDF tables capture hidden data)