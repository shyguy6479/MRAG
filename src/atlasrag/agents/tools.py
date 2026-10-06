import ast
import math
import operator
from typing import Any, cast
from uuid import UUID

from pydantic import Field

from atlasrag.core.errors import InvalidInput
from atlasrag.core.models import Contract, Filters, ToolSpec
from atlasrag.core.storage import Database
from atlasrag.retrieval.engine import RetrievalEngine, Snapshot


class CalculatorInput(Contract):
    expression: str = Field(min_length=1, max_length=200)


class DocumentInput(Contract):
    document_id: UUID


class SearchInput(Contract):
    query: str = Field(min_length=1, max_length=4000)
    filters: Filters = Field(default_factory=Filters)
    top_k: int = Field(default=6, ge=1, le=20)


class SectionInput(Contract):
    section: str = Field(min_length=1, max_length=200)
    query: str = Field(min_length=1, max_length=4000)


TOOL_SCHEMAS = [
    ToolSpec(
        name="calculator",
        description="Evaluate bounded arithmetic without executing code.",
        input_schema=CalculatorInput.model_json_schema(),
    ),
    ToolSpec(
        name="search_documents",
        description="Search the current indexed corpus.",
        input_schema=SearchInput.model_json_schema(),
    ),
    ToolSpec(
        name="retrieve_document",
        description="Inspect stored chunks for one document.",
        input_schema=DocumentInput.model_json_schema(),
    ),
    ToolSpec(
        name="get_document_metadata",
        description="Inspect document provenance and status.",
        input_schema=DocumentInput.model_json_schema(),
    ),
    ToolSpec(
        name="search_by_section",
        description="Restrict retrieval to a named section.",
        input_schema=SectionInput.model_json_schema(),
    ),
]


def calculate(expression: str) -> float:
    CalculatorInput(expression=expression)
    try:
        root = ast.parse(expression, mode="eval")
        if len(list(ast.walk(root))) > 40:
            raise ValueError("too many operations")

        def visit(node: ast.AST) -> float:
            match node:
                case ast.Constant(value=value) if type(value) in {int, float}:
                    result = float(cast(int | float, value))
                case ast.UnaryOp(op=ast.USub(), operand=operand):
                    result = -visit(operand)
                case ast.UnaryOp(op=ast.UAdd(), operand=operand):
                    result = visit(operand)
                case ast.BinOp(left=left, op=op, right=right):
                    operations = {
                        ast.Add: operator.add,
                        ast.Sub: operator.sub,
                        ast.Mult: operator.mul,
                        ast.Div: operator.truediv,
                        ast.Mod: operator.mod,
                    }
                    if type(op) not in operations:
                        raise ValueError("operator not allowed")
                    result = operations[type(op)](visit(left), visit(right))
                case _:
                    raise ValueError("expression not allowed")
            if not math.isfinite(result) or abs(result) > 1e15:
                raise ValueError("result out of bounds")
            return result

        return visit(root.body)
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError, RecursionError) as exc:
        raise InvalidInput("unsupported arithmetic expression") from exc


class DocumentTools:
    def __init__(self, db: Database, engine: RetrievalEngine) -> None:
        self.db, self.engine = db, engine

    def call(self, name: str, arguments: dict[str, Any], snapshot: Snapshot) -> Any:
        if name == "calculator":
            return calculate(CalculatorInput.model_validate(arguments).expression)
        if name in {"retrieve_document", "get_document_metadata"}:
            value = DocumentInput.model_validate(arguments)
            info, evidence = self.db.document(value.document_id)
            return info if name == "get_document_metadata" else evidence
        if name == "search_documents":
            args = SearchInput.model_validate(arguments)
            return self.engine.search(
                snapshot, args.query, args.filters, "hybrid_reranked", args.top_k
            )
        if name == "search_by_section":
            args_section = SectionInput.model_validate(arguments)
            return self.engine.search(
                snapshot,
                args_section.query,
                Filters(section=args_section.section),
                "hybrid_reranked",
                6,
            )
        raise InvalidInput("tool not allowed")
