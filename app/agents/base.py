"""
Base agent class and core types for the agent framework.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import UUID

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageToolCall

from app.config import get_settings

settings = get_settings()


@dataclass
class ToolResult:
    """Result from a tool execution."""

    success: bool
    data: Any = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
        }


@dataclass
class Tool:
    """Definition of a tool available to an agent."""

    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: Callable  # Async function

    def to_openai_tool(self) -> dict:
        """Convert to OpenAI tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class AgentState:
    """State passed between agents during execution."""

    user_id: str
    session_id: str
    message: str
    context_items: list = field(default_factory=list)
    entities: list = field(default_factory=list)
    preferences: dict = field(default_factory=dict)
    pending_actions: list = field(default_factory=list)
    conversation_history: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "message": self.message,
            "context_items": self.context_items,
            "entities": self.entities,
            "preferences": self.preferences,
            "pending_actions": self.pending_actions,
            "metadata": self.metadata,
        }


@dataclass
class AgentResponse:
    """Response from an agent."""

    message: str
    state: AgentState
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    clarification_options: Optional[list[str]] = None
    pending_actions: list = field(default_factory=list)
    tokens_used: int = 0
    model_used: str = ""

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "needs_clarification": self.needs_clarification,
            "clarification_question": self.clarification_question,
            "clarification_options": self.clarification_options,
            "pending_actions": self.pending_actions,
            "tokens_used": self.tokens_used,
            "model_used": self.model_used,
        }


class BaseAgent(ABC):
    """
    Base class for all agents.

    Provides:
    - Tool management
    - LLM interaction
    - State handling
    """

    def __init__(
        self,
        name: str,
        system_prompt: str,
        openai_client: Optional[AsyncOpenAI] = None,
        model: Optional[str] = None,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.openai = openai_client or AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = model or settings.chat_model
        self.tools: dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        """Register a tool for this agent."""
        self.tools[tool.name] = tool

    def get_tools_schema(self) -> list[dict]:
        """Get OpenAI tools schema for all registered tools."""
        return [tool.to_openai_tool() for tool in self.tools.values()]

    async def execute_tool(
        self,
        tool_call: ChatCompletionMessageToolCall,
        state: AgentState,
    ) -> ToolResult:
        """Execute a tool call."""
        tool_name = tool_call.function.name
        tool = self.tools.get(tool_name)

        if not tool:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {tool_name}",
            )

        try:
            args = json.loads(tool_call.function.arguments)
            result = await tool.handler(state=state, **args)
            return ToolResult(success=True, data=result)
        except json.JSONDecodeError as e:
            return ToolResult(
                success=False,
                error=f"Invalid tool arguments: {e}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Tool execution error: {e}",
            )

    async def chat(
        self,
        messages: list[dict],
        use_tools: bool = True,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> dict:
        """
        Make an LLM chat completion request.

        Returns:
            {
                "content": str,
                "tool_calls": list,
                "finish_reason": str,
                "tokens": int
            }
        """
        # Build request
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Add tools if enabled and available
        if use_tools and self.tools:
            kwargs["tools"] = self.get_tools_schema()
            kwargs["tool_choice"] = "auto"

        # Make request
        response = await self.openai.chat.completions.create(**kwargs)

        choice = response.choices[0]

        return {
            "content": choice.message.content or "",
            "tool_calls": choice.message.tool_calls or [],
            "finish_reason": choice.finish_reason,
            "tokens": response.usage.total_tokens if response.usage else 0,
        }

    def build_messages(
        self,
        state: AgentState,
        additional_context: Optional[str] = None,
    ) -> list[dict]:
        """Build the messages array for LLM request."""
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]

        # Add conversation history
        for msg in state.conversation_history[-10:]:  # Last 10 messages
            messages.append(msg)

        # Build user message with context
        user_content = state.message

        # Add context items if available
        if state.context_items:
            context_text = self._format_context(state.context_items)
            user_content = f"## Available Context:\n{context_text}\n\n## User Request:\n{user_content}"

        # Add entities if available
        if state.entities:
            entities_text = self._format_entities(state.entities)
            user_content = f"{user_content}\n\n## Known Entities:\n{entities_text}"

        # Add additional context
        if additional_context:
            user_content = f"{user_content}\n\n{additional_context}"

        messages.append({"role": "user", "content": user_content})

        return messages

    def _format_context(self, context_items: list[dict]) -> str:
        """Format context items for the prompt."""
        formatted = []
        for item in context_items[:5]:  # Limit to top 5
            source = item.get("source", "unknown")
            title = item.get("title", "")
            summary = item.get("summary") or item.get("content", "")[:500]

            formatted.append(
                f"[{source.upper()}] {title}\n{summary}\n"
            )

        return "\n---\n".join(formatted)

    def _format_entities(self, entities: list[dict]) -> str:
        """Format entities for the prompt."""
        formatted = []
        for entity in entities[:10]:
            name = entity.get("name", "")
            entity_type = entity.get("type", "")
            email = entity.get("email", "")

            if email:
                formatted.append(f"- {name} ({entity_type}): {email}")
            else:
                formatted.append(f"- {name} ({entity_type})")

        return "\n".join(formatted)

    @abstractmethod
    async def run(self, state: AgentState) -> AgentResponse:
        """
        Run the agent with the given state.

        Must be implemented by subclasses.
        """
        pass

    async def run_with_tools(
        self,
        state: AgentState,
        max_iterations: int = 10,
    ) -> AgentResponse:
        """
        Run the agent with tool execution loop.

        Handles:
        - Initial LLM call
        - Tool execution
        - Follow-up calls
        - Final response generation
        """
        messages = self.build_messages(state)
        total_tokens = 0
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Make LLM call
            result = await self.chat(messages)
            total_tokens += result["tokens"]

            # Check if we need to execute tools
            if result["tool_calls"]:
                # Add assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "content": result["content"],
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in result["tool_calls"]
                    ],
                })

                # Execute each tool
                for tool_call in result["tool_calls"]:
                    tool_result = await self.execute_tool(tool_call, state)

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result.to_dict()),
                    })

                # Continue loop for follow-up
                continue

            # No tool calls - we have a final response
            return AgentResponse(
                message=result["content"],
                state=state,
                tokens_used=total_tokens,
                model_used=self.model,
            )

        # Max iterations reached
        return AgentResponse(
            message="I was unable to complete this task within the allowed iterations.",
            state=state,
            tokens_used=total_tokens,
            model_used=self.model,
        )
