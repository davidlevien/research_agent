from .registry import Registry, ToolSpec
from .search_models import SearchRequest, SearchHit
from . import search_tavily, search_brave, search_serper, search_serpapi, search_nps

def register_search_tools(registry: Registry):
    """Register search tools if not already registered."""
    # Check if tools are already registered to avoid duplicates
    if "search_tavily" not in registry._tools:
        registry.register(ToolSpec(
            name="search_tavily",
            fn=lambda **k: search_tavily.run(SearchRequest(**k)),
            input_model=SearchRequest,
            output_model=list[SearchHit],
            description="Tavily web search (parallel provider)"
        ))
    
    if "search_brave" not in registry._tools:
        registry.register(ToolSpec(
            name="search_brave",
            fn=lambda **k: search_brave.run(SearchRequest(**k)),
            input_model=SearchRequest,
            output_model=list[SearchHit],
            description="Brave web search (parallel provider)"
        ))
    
    if "search_serper" not in registry._tools:
        registry.register(ToolSpec(
            name="search_serper",
            fn=lambda **k: search_serper.run(SearchRequest(**k)),
            input_model=SearchRequest,
            output_model=list[SearchHit],
            description="Serper.dev Google search (parallel provider)"
        ))
    
    if "search_serpapi" not in registry._tools:
        registry.register(ToolSpec(
            name="search_serpapi",
            fn=lambda **k: search_serpapi.run(SearchRequest(**k)),
            input_model=SearchRequest,
            output_model=list[SearchHit],
            description="SerpAPI Google search (parallel provider)"
        ))
    
    if "search_nps" not in registry._tools:
        registry.register(ToolSpec(
            name="search_nps",
            fn=lambda **k: search_nps.run(SearchRequest(**k)),
            input_model=SearchRequest,
            output_model=list[SearchHit],
            description="National Park Service domain search (parallel provider)"
        ))