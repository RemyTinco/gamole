"""Cost tracking for LLM token usage across agent calls.

Gemini Flash pricing: $0.10/1M input tokens, $0.40/1M output tokens.
"""

import contextvars
from dataclasses import dataclass, field

# Per-request cost tracker stored in contextvars
_current_tracker: contextvars.ContextVar["CostTracker | None"] = contextvars.ContextVar(
    "cost_tracker", default=None
)

COST_PER_INPUT_TOKEN = 0.10 / 1_000_000  # $0.10 per 1M
COST_PER_OUTPUT_TOKEN = 0.40 / 1_000_000  # $0.40 per 1M


@dataclass
class AgentCost:
    agent_name: str
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def cost_usd(self) -> float:
        return (self.input_tokens * COST_PER_INPUT_TOKEN) + (self.output_tokens * COST_PER_OUTPUT_TOKEN)


@dataclass
class CostTracker:
    agents: dict[str, AgentCost] = field(default_factory=dict)

    def record(self, agent_name: str, input_tokens: int, output_tokens: int) -> None:
        if agent_name not in self.agents:
            self.agents[agent_name] = AgentCost(agent_name=agent_name)
        self.agents[agent_name].input_tokens += input_tokens
        self.agents[agent_name].output_tokens += output_tokens

    @property
    def total_input_tokens(self) -> int:
        return sum(a.input_tokens for a in self.agents.values())

    @property
    def total_output_tokens(self) -> int:
        return sum(a.output_tokens for a in self.agents.values())

    @property
    def total_cost_usd(self) -> float:
        return sum(a.cost_usd for a in self.agents.values())

    def to_dict(self) -> dict:
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "agents": {
                name: {
                    "input_tokens": a.input_tokens,
                    "output_tokens": a.output_tokens,
                    "cost_usd": round(a.cost_usd, 6),
                }
                for name, a in self.agents.items()
            },
        }


def get_tracker() -> "CostTracker | None":
    return _current_tracker.get()


def set_tracker(tracker: "CostTracker") -> contextvars.Token:
    return _current_tracker.set(tracker)


def clear_tracker(token: contextvars.Token) -> None:
    _current_tracker.reset(token)


def track_usage(agent_name: str, input_tokens: int, output_tokens: int) -> None:
    """Record token usage for the current generation's cost tracker."""
    tracker = get_tracker()
    if tracker:
        tracker.record(agent_name, input_tokens, output_tokens)
