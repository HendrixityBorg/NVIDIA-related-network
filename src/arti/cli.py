from __future__ import annotations

import argparse
import json
import os
from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel

from .models import CommercialDirectness, FactStatus, RelationDirection, RelationType
from .repository import SnapshotRepository
from .service import InvalidCursorError, NotFoundError, ResearchService


class CLIParseError(ValueError):
    """Argparse failure rendered through the CLI's stable JSON error envelope."""


class JSONArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CLIParseError(message)


def bounded_int(minimum: int, maximum: int):
    def parse(value: str) -> int:
        parsed = int(value)
        if not minimum <= parsed <= maximum:
            raise argparse.ArgumentTypeError(
                f"must be between {minimum} and {maximum}"
            )
        return parsed

    return parse


def json_default(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, (date, Enum)):
        return value.isoformat() if isinstance(value, date) else value.value
    raise TypeError(f"cannot serialize {type(value).__name__}")


def output(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=json_default))


def build_parser() -> argparse.ArgumentParser:
    parser = JSONArgumentParser(
        prog="arti", description="Query the frozen NVIDIA relationship snapshot"
    )
    parser.add_argument(
        "--data",
        default=os.getenv("ARTI_DATA_PATH"),
        help="snapshot JSON path (defaults to checked-in data)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    company = sub.add_parser("company", help="resolve a company by id, ticker or alias")
    company.add_argument("query")

    relationships = sub.add_parser("relationships", help="query relationships")
    relationships.add_argument("--company")
    relationships.add_argument(
        "--type", action="append", choices=[item.value for item in RelationType]
    )
    relationships.add_argument(
        "--direction", action="append", choices=[item.value for item in RelationDirection]
    )
    relationships.add_argument(
        "--status", action="append", choices=[item.value for item in FactStatus]
    )
    relationships.add_argument(
        "--commercial-directness",
        action="append",
        choices=[item.value for item in CommercialDirectness],
    )
    relationships.add_argument("--min-confidence", type=bounded_int(0, 100), default=0)
    relationships.add_argument("--min-relevance", type=bounded_int(0, 100), default=0)
    relationships.add_argument("--product")
    relationships.add_argument("--as-of", type=date.fromisoformat)
    relationships.add_argument(
        "--include-unknown", action=argparse.BooleanOptionalAction, default=True
    )
    relationships.add_argument("--limit", type=bounded_int(1, 100), default=20)
    relationships.add_argument("--cursor")

    evidence = sub.add_parser("evidence", help="query evidence or show evidence for one relationship")
    evidence.add_argument("relationship_id", nargs="?")
    evidence.add_argument("--publisher")
    evidence.add_argument("--source-family")
    evidence.add_argument("--published-from", type=date.fromisoformat)
    evidence.add_argument("--published-to", type=date.fromisoformat)
    evidence.add_argument("--human-verified", action=argparse.BooleanOptionalAction)
    evidence.add_argument("--limit", type=bounded_int(1, 100), default=20)
    evidence.add_argument("--cursor")

    graph = sub.add_parser("graph", help="build a one-hop relationship graph")
    graph.add_argument("--company", required=True)
    graph.add_argument(
        "--type", action="append", choices=[item.value for item in RelationType]
    )
    graph.add_argument(
        "--direction", action="append", choices=[item.value for item in RelationDirection]
    )
    graph.add_argument(
        "--status", action="append", choices=[item.value for item in FactStatus]
    )
    graph.add_argument(
        "--commercial-directness",
        action="append",
        choices=[item.value for item in CommercialDirectness],
    )
    graph.add_argument("--min-confidence", type=bounded_int(0, 100), default=0)
    graph.add_argument("--min-relevance", type=bounded_int(0, 100), default=0)
    graph.add_argument("--product")
    graph.add_argument("--as-of", type=date.fromisoformat)
    graph.add_argument(
        "--include-unknown", action=argparse.BooleanOptionalAction, default=True
    )
    graph.add_argument("--limit", type=bounded_int(1, 100), default=100)
    graph.add_argument("--cursor")

    sub.add_parser("serve", help="start the HTTP API")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except CLIParseError as exc:
        output({"error": {"code": "invalid_input", "message": str(exc)}})
        return 2
    if args.command == "serve":
        from .api import main as serve

        serve()
        return 0

    try:
        service = ResearchService(SnapshotRepository(args.data))
        if args.command == "company":
            output({"data": service.resolve_entity(args.query)})
        elif args.command == "relationships":
            page = service.list_relationships(
                company=args.company,
                relation_types={RelationType(item) for item in args.type}
                if args.type
                else None,
                directions={RelationDirection(item) for item in args.direction}
                if args.direction
                else None,
                statuses={FactStatus(item) for item in args.status}
                if args.status
                else None,
                commercial_directness={
                    CommercialDirectness(item) for item in args.commercial_directness
                }
                if args.commercial_directness
                else None,
                min_confidence=args.min_confidence,
                min_relevance=args.min_relevance,
                product=args.product,
                as_of=args.as_of,
                include_unknown=args.include_unknown,
                limit=args.limit,
                cursor=args.cursor,
            )
            output(
                {
                    "data": page.items,
                    "pagination": {
                        "total": page.total,
                        "limit": page.limit,
                        "next_cursor": page.next_cursor,
                    },
                }
            )
        elif args.command == "evidence":
            page = service.list_evidence(
                relationship_id=args.relationship_id,
                publisher=args.publisher,
                source_family=args.source_family,
                published_from=args.published_from,
                published_to=args.published_to,
                human_verified=args.human_verified,
                limit=args.limit,
                cursor=args.cursor,
            )
            output(
                {
                    "data": page.items,
                    "pagination": {
                        "total": page.total,
                        "limit": page.limit,
                        "next_cursor": page.next_cursor,
                    },
                }
            )
        elif args.command == "graph":
            output(
                {
                    "data": service.graph(
                        company=args.company,
                        relation_types={RelationType(item) for item in args.type}
                        if args.type
                        else None,
                        directions={RelationDirection(item) for item in args.direction}
                        if args.direction
                        else None,
                        statuses={FactStatus(item) for item in args.status}
                        if args.status
                        else None,
                        commercial_directness={
                            CommercialDirectness(item)
                            for item in args.commercial_directness
                        }
                        if args.commercial_directness
                        else None,
                        min_confidence=args.min_confidence,
                        min_relevance=args.min_relevance,
                        product=args.product,
                        as_of=args.as_of,
                        include_unknown=args.include_unknown,
                        limit=args.limit,
                        cursor=args.cursor,
                    )
                }
            )
        return 0
    except (NotFoundError, InvalidCursorError, ValueError, FileNotFoundError) as exc:
        error_codes = {
            NotFoundError: "not_found",
            InvalidCursorError: "invalid_cursor",
            FileNotFoundError: "file_not_found",
            ValueError: "invalid_input",
        }
        output(
            {
                "error": {
                    "code": error_codes.get(type(exc), "invalid_input"),
                    "message": str(exc),
                }
            }
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
