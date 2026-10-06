import time
from dataclasses import dataclass, field

from atlasrag.core.errors import BudgetExceeded


@dataclass
class Budget:
    max_steps: int
    timeout_seconds: float
    max_tokens: int
    max_cost: float
    started: float = field(default_factory=time.monotonic)
    steps: int = 0
    tokens: int = 0
    cost: float = 0

    def check(self) -> None:
        if time.monotonic() - self.started >= self.timeout_seconds:
            raise BudgetExceeded("deadline exceeded")

    def step(self) -> int:
        self.check()
        if self.steps >= self.max_steps:
            raise BudgetExceeded("step limit exceeded")
        self.steps += 1
        return self.steps

    def reserve(self, tokens: int, cost: float) -> None:
        self.check()
        if tokens < 0 or cost < 0:
            raise ValueError("usage cannot be negative")
        if self.tokens + tokens > self.max_tokens or self.cost + cost > self.max_cost:
            raise BudgetExceeded("token or cost limit exceeded")
        self.tokens += tokens
        self.cost += cost
