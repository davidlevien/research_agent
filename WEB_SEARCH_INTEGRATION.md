# Web Search Provider Integration Summary

## Key Changes Made (v8.26.4)

### 1. Provider Registry Updates
- **File**: `research_system/providers/registry.py`
- **Changes**: 
  - Renamed `register_paid_providers()` to `register_web_search_providers()`
  - Added proper registration for Tavily, Brave, Serper, and SerpAPI
  - Fixed lambda functions to properly create SearchRequest objects
  - Added informative logging when providers are registered
  - Recognized these providers have free tiers, not "paid only"

### 2. Provider Profiles Configuration
- **File**: `research_system/resources/provider_profiles.yaml`
- **Changes**:
  - Added web search providers (tavily, brave, serper, serpapi) to relevant categories:
    - `general`: All 4 providers as primary options
    - `news`: Web search providers for current news
    - `macro`: Web search for latest economic data
  - Created new `trends` profile specifically for current/latest queries
  - Providers now selected based on query needs, not artificial free/paid distinction

### 3. Collection Module Updates
- **File**: `research_system/orchestrator.py`
- **Changes**:
  - Updated import from deprecated `collection_enhanced` to `collection`
  - Web search providers now properly integrated in collection flow

### 4. Intent Classification Fix
- **File**: `research_system/config/settings.py`
- **Changes**:
  - Fixed `quality_for_intent()` to handle Intent enum objects
  - Now properly extracts `.value` from Intent enum before processing

### 5. Test Fixes
- **File**: `tests/test_smoke_research.py`
- **Changes**:
  - Fixed test to use proper `OrchestratorSettings` instead of global `Settings`
  - Fixed test structure to work with temporary directories
  - All smoke tests now passing

## How Web Search Providers Work

1. **Environment Configuration** (`.env` file):
   ```bash
   SEARCH_PROVIDERS=tavily,brave,serper
   TAVILY_API_KEY=tvly-YOUR_KEY_HERE
   BRAVE_API_KEY=BSA-YOUR_KEY_HERE
   SERPER_API_KEY=YOUR_KEY_HERE
   SERPAPI_API_KEY=YOUR_KEY_HERE
   ```

2. **Two Collection Paths**:
   - **`parallel_provider_search`**: Uses providers from `SEARCH_PROVIDERS` env variable
   - **`collect_from_free_apis`**: Uses providers from `PROVIDERS` registry

3. **Provider Selection**:
   - Based on query intent and topic routing
   - Web search providers prioritized for:
     - Trends and current events
     - News and recent developments
     - General queries requiring broad coverage
   - Specialized providers (OECD, World Bank, etc.) for domain-specific queries

4. **Free Tier Recognition**:
   - All 4 providers (Tavily, Brave, Serper, SerpAPI) offer free tiers
   - No longer artificially separated as "paid only"
   - Used based on API key availability and query needs

## Testing

All critical smoke tests passing:
- ✅ `test_seed_accepts_strings` - String seed handling
- ✅ `test_canonical_id_exists` - Deduplication import fix
- ✅ `test_doi_resolver_exists` - DOI resolution
- ✅ `test_evidence_io_handles_multiple_types` - Evidence I/O

## Next Steps

1. **API Key Configuration**: Users should add their free tier API keys to `.env`
2. **Provider Monitoring**: Track which providers return best results for different query types
3. **Rate Limiting**: Ensure proper rate limiting for free tier quotas
4. **Fallback Logic**: Implement graceful fallback when providers hit limits

## Benefits

- **Better Coverage**: Web search providers provide current, broad coverage
- **Cost Effective**: Free tiers sufficient for most research needs
- **Query Appropriate**: Providers selected based on query intent, not payment status
- **Redundancy**: Multiple providers ensure resilience if one fails
