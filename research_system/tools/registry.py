"""
Tool registry for managing all research tools with typed output validation
"""

from typing import Dict, Any, Callable, Optional, List, get_origin, get_args
from dataclasses import dataclass
import inspect
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolMetadata:
    """Metadata for a registered tool"""
    name: str
    description: str
    category: str
    function: Callable
    parameters: Dict[str, Any]
    output_type: Any = None
    requires_api_key: bool = False
    cost_per_use: float = 0.0
    rate_limit: Optional[int] = None


class ToolRegistry:
    """Central registry for all research tools with output validation"""
    
    def __init__(self):
        self._tools: Dict[str, ToolMetadata] = {}
        self._categories: Dict[str, List[str]] = {}
    
    def register(
        self,
        name: str,
        description: str,
        category: str,
        function: Callable,
        output_type: Optional[Any] = None,
        requires_api_key: bool = False,
        cost_per_use: float = 0.0,
        rate_limit: Optional[int] = None
    ) -> None:
        """Register a new tool with output type validation
        
        Args:
            name: Tool name (must be unique)
            description: Tool description
            category: Tool category
            function: Callable function
            output_type: Expected output type (supports typing.List[T])
            requires_api_key: Whether tool requires API key
            cost_per_use: Cost per use in USD
            rate_limit: Rate limit per minute
        """
        
        # Check for duplicate registration
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered")
        
        # Extract parameter information
        sig = inspect.signature(function)
        parameters = {}
        
        for param_name, param in sig.parameters.items():
            param_info = {
                "type": "Any",
                "default": None,
                "required": param.default == inspect.Parameter.empty
            }
            
            # Get type annotation if available
            if param.annotation != inspect.Parameter.empty:
                if hasattr(param.annotation, '__name__'):
                    param_info["type"] = param.annotation.__name__
                else:
                    param_info["type"] = str(param.annotation)
            
            # Get default value if available
            if param.default != inspect.Parameter.empty:
                param_info["default"] = param.default
            
            parameters[param_name] = param_info
        
        # Get output type from function annotation if not provided
        if output_type is None and sig.return_annotation != inspect.Parameter.empty:
            output_type = sig.return_annotation
        
        # Create tool metadata
        metadata = ToolMetadata(
            name=name,
            description=description,
            category=category,
            function=function,
            parameters=parameters,
            output_type=output_type,
            requires_api_key=requires_api_key,
            cost_per_use=cost_per_use,
            rate_limit=rate_limit
        )
        
        # Register tool
        self._tools[name] = metadata
        
        # Update category index
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(name)
        
        logger.info(f"Registered tool: {name} in category: {category}")
    
    def get_tool(self, name: str) -> Optional[ToolMetadata]:
        """Get tool by name"""
        return self._tools.get(name)
    
    def get_tools_by_category(self, category: str) -> List[ToolMetadata]:
        """Get all tools in a category"""
        tool_names = self._categories.get(category, [])
        return [self._tools[name] for name in tool_names]
    
    def execute_tool(self, name: str, validate_output: bool = True, **kwargs) -> Any:
        """Execute a tool by name with optional output validation
        
        Args:
            name: Tool name
            validate_output: Whether to validate output type
            **kwargs: Tool parameters
            
        Returns:
            Tool execution result
            
        Raises:
            ValueError: If tool not found or parameters invalid
            TypeError: If output type validation fails
        """
        
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool not found: {name}")
        
        # Validate parameters
        if not self.validate_parameters(name, **kwargs):
            raise ValueError(f"Invalid parameters for tool: {name}")
        
        try:
            logger.debug(f"Executing tool: {name} with params: {kwargs}")
            result = tool.function(**kwargs)
            
            # Validate output type if requested and type is specified
            if validate_output and tool.output_type is not None:
                if not self._validate_output_type(result, tool.output_type):
                    raise TypeError(
                        f"Tool {name} returned {type(result)} but expected {tool.output_type}"
                    )
            
            logger.debug(f"Tool {name} executed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Tool {name} execution failed: {e}")
            raise
    
    def _validate_output_type(self, output: Any, expected_type: Any) -> bool:
        """Validate output matches expected type
        
        Supports:
        - Basic types (int, str, dict, etc.)
        - List[T] from typing module
        - Optional[T] from typing module
        """
        
        # Handle None case
        if output is None:
            # Check if Optional type
            origin = get_origin(expected_type)
            if origin is Union:
                args = get_args(expected_type)
                return type(None) in args
            return expected_type is type(None)
        
        # Get the origin type for generics
        origin = get_origin(expected_type)
        
        # Handle List[T] validation
        if origin is list or origin is List:
            if not isinstance(output, list):
                return False
            
            # Get the element type
            args = get_args(expected_type)
            if args:
                element_type = args[0]
                # Validate each element
                return all(self._validate_output_type(item, element_type) for item in output)
            return True
        
        # Handle Dict[K, V] validation
        if origin is dict or origin is Dict:
            if not isinstance(output, dict):
                return False
            
            args = get_args(expected_type)
            if args and len(args) == 2:
                key_type, value_type = args
                # Validate all keys and values
                for k, v in output.items():
                    if not self._validate_output_type(k, key_type):
                        return False
                    if not self._validate_output_type(v, value_type):
                        return False
            return True
        
        # Handle Optional[T]
        if origin is Union:
            args = get_args(expected_type)
            # Try each type in the union
            return any(self._validate_output_type(output, arg) for arg in args)
        
        # Handle basic types
        if expected_type in [int, str, float, bool, dict, list, tuple]:
            return isinstance(output, expected_type)
        
        # Handle class types
        if inspect.isclass(expected_type):
            return isinstance(output, expected_type)
        
        # Default to type check
        return type(output) == expected_type
    
    def list_tools(self) -> List[str]:
        """List all registered tool names"""
        return list(self._tools.keys())
    
    def list_categories(self) -> List[str]:
        """List all tool categories"""
        return list(self._categories.keys())
    
    def get_tool_info(self, name: str) -> Dict[str, Any]:
        """Get detailed information about a tool"""
        tool = self.get_tool(name)
        if not tool:
            return {}
        
        return {
            "name": tool.name,
            "description": tool.description,
            "category": tool.category,
            "parameters": tool.parameters,
            "output_type": str(tool.output_type) if tool.output_type else None,
            "requires_api_key": tool.requires_api_key,
            "cost_per_use": tool.cost_per_use,
            "rate_limit": tool.rate_limit
        }
    
    def validate_parameters(self, name: str, **kwargs) -> bool:
        """Validate parameters for a tool"""
        tool = self.get_tool(name)
        if not tool:
            return False
        
        # Check required parameters
        for param_name, param_info in tool.parameters.items():
            if param_info["required"] and param_name not in kwargs:
                logger.error(f"Missing required parameter: {param_name} for tool: {name}")
                return False
        
        # Check for unknown parameters (warning only)
        for param_name in kwargs:
            if param_name not in tool.parameters:
                logger.warning(f"Unknown parameter: {param_name} for tool: {name}")
        
        return True
    
    def get_tools_requiring_api_key(self) -> List[str]:
        """Get list of tools that require API keys"""
        return [
            name for name, tool in self._tools.items()
            if tool.requires_api_key
        ]
    
    def get_tool_cost(self, name: str) -> float:
        """Get cost per use for a tool"""
        tool = self.get_tool(name)
        return tool.cost_per_use if tool else 0.0
    
    def calculate_total_cost(self, tool_uses: Dict[str, int]) -> float:
        """Calculate total cost for multiple tool uses
        
        Args:
            tool_uses: Dictionary of tool name to number of uses
            
        Returns:
            Total cost in USD
        """
        total = 0.0
        for tool_name, count in tool_uses.items():
            total += self.get_tool_cost(tool_name) * count
        return total


# Import typing utilities for validation
from typing import Union, Dict, List


# Global tool registry instance
tool_registry = ToolRegistry()