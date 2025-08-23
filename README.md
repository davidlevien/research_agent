# Research System

A production-ready research automation system with comprehensive error recovery, monitoring, and security features.

## Features

- **Multi-Agent Architecture**: Specialized agents for planning, collection, verification, and synthesis
- **Error Recovery**: Circuit breakers, fallback strategies, and partial result handling
- **Performance Optimization**: Multi-tier caching, connection pooling, and parallel execution
- **Security**: Input sanitization, PII detection, encryption, and domain validation
- **Observability**: Prometheus metrics, OpenTelemetry tracing, and comprehensive logging
- **Cost Management**: Budget controls, cost tracking, and usage alerts
- **Quality Assurance**: Evidence verification, bias detection, and fact-checking

## Installation

### Using pip

```bash
pip install -e .
```

### Using Docker

```bash
docker-compose up -d
```

## Configuration

Copy `.env.example` to `.env` and configure your API keys:

```bash
cp .env.example .env
```

Required API keys:
- OpenAI or Anthropic (for LLM operations)
- Tavily or Serper (for web search)

## Usage

### Command Line

```bash
# Basic usage
research-system -t "artificial intelligence trends 2024"

# With options
research-system \
  -t "quantum computing applications" \
  -d deep \
  -o report.md \
  -f markdown

# Using config file
research-system -t "topic" -c config.yaml
```

### Python API

```python
from research_system import ResearchOrchestrator, ResearchRequest

# Initialize
orchestrator = ResearchOrchestrator()

# Create request
request = ResearchRequest(
    topic="sustainable energy solutions",
    depth="standard"
)

# Execute research
report = await orchestrator.execute_research(request)

# Save report
with open("report.md", "w") as f:
    f.write(report.to_markdown())
```

## Architecture

### Core Components

1. **Orchestrator**: Coordinates the entire research workflow
2. **Agents**: Specialized agents for different research phases
3. **Tools**: Search, LLM, parsing, and storage tools
4. **Core Systems**:
   - Error Recovery: Circuit breakers and fallbacks
   - Performance: Caching and optimization
   - Security: Input sanitization and encryption
   - Monitoring: Metrics and tracing

### Research Workflow

1. **Planning Phase**: Decompose topic into subtopics
2. **Collection Phase**: Gather evidence from multiple sources
3. **Verification Phase**: Validate evidence quality
4. **Synthesis Phase**: Generate comprehensive report

## Monitoring

### Prometheus Metrics

Access metrics at `http://localhost:9090`

Key metrics:
- `research_requests_total`: Total research requests
- `research_duration_seconds`: Phase execution times
- `evidence_quality_score`: Evidence quality distribution
- `system_health_score`: Overall system health

### Grafana Dashboards

Access dashboards at `http://localhost:3000` (admin/admin)

### Jaeger Tracing

Access traces at `http://localhost:16686`

## Development

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit

# With coverage
pytest --cov=research_system
```

### Code Quality

```bash
# Format code
black research_system/

# Lint
ruff check research_system/

# Type checking
mypy research_system/
```

### Security Scanning

```bash
# Dependency scanning
safety check

# Code security
bandit -r research_system/
```

## Deployment

### Docker Deployment

```bash
# Build image
docker build -t research-system:latest .

# Run container
docker run -d \
  --env-file .env \
  -p 8000:8000 \
  research-system:latest
```

### Kubernetes Deployment

```bash
kubectl apply -f infrastructure/kubernetes/
```

### Environment Variables

See `.env.example` for all available configuration options.

## API Documentation

### Research Request Schema

```json
{
  "topic": "string",
  "depth": "rapid|standard|deep",
  "constraints": {
    "time_window": "string",
    "geographic_scope": ["string"],
    "source_types": ["academic", "news", "government"]
  }
}
```

### Research Report Schema

```json
{
  "report_id": "uuid",
  "topic": "string",
  "executive_summary": "string",
  "sections": [...],
  "evidence": [...],
  "metrics": {...},
  "status": "complete|partial|failed"
}
```

## Troubleshooting

### Common Issues

1. **Rate Limiting**: Configure rate limits in `.env`
2. **Memory Issues**: Adjust cache settings
3. **API Errors**: Check API keys and quotas
4. **Slow Performance**: Enable Redis caching

### Debug Mode

```bash
research-system -t "topic" -v  # Verbose output
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions, please open a GitHub issue.