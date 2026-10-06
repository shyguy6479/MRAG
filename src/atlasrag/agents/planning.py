import re
from dataclasses import dataclass


@dataclass(frozen=True)
class QueryPlan:
    intent: str
    original: str
    rewritten: str
    queries: list[str]
    expression: str | None = None


def plan_query(
    question: str, memory: list[str], rewrite: bool = True, decompose: bool = True
) -> QueryPlan:
    lower = question.lower().strip(" .!?")
    if lower in {"hi", "hello", "hey", "thanks", "thank you", "help"}:
        return QueryPlan("conversation", question, question, [])
    expression = re.sub(r"^(?:calculate|compute|what is)\s+", "", lower).strip(" ?")
    if re.fullmatch(r"[\d\s.+*/()%\-]+", expression) and any(c.isdigit() for c in expression):
        return QueryPlan("calculation", question, question, [], expression)
    rewritten = question
    if (
        rewrite
        and memory
        and re.search(r"\b(they|those|these|that|it|its|this|them|their|which one)\b", lower)
    ):
        # Only the latest relevant user topic is selected; no raw answer/history concatenation.
        topic = memory[-1][:700]
        rewritten = f"{question} Regarding the previous research question: {topic}"
    if any(word in lower for word in ["compare", "difference", "versus", "trade-off", "tradeoff"]):
        intent = "comparison"
    elif any(word in lower for word in ["summarize", "summary", "overview"]):
        intent = "summarization"
    elif any(word in lower for word in ["why", "how does", "relationship", "impact"]):
        intent = "multi_hop"
    elif "metadata" in lower:
        intent = "metadata"
    else:
        intent = "factual"
    queries = [rewritten]
    if decompose and intent in {"comparison", "multi_hop"}:
        topic = re.sub(r"^(compare|explain|what are|how does)\s+", "", rewritten, flags=re.I)
        parts = re.split(r"\s+(?:versus|vs\.?|and)\s+", topic, maxsplit=1, flags=re.I)
        if len(parts) == 2:
            queries.extend([f"{part} mechanisms results limitations" for part in parts])
        else:
            queries.extend([f"{topic} methods benefits", f"{topic} limitations trade-offs"])
    return QueryPlan(intent, question, rewritten, list(dict.fromkeys(queries))[:3])
