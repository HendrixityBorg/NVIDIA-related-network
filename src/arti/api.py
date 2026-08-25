from __future__ import annotations

import os
from datetime import date
from typing import Annotated

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .models import CommercialDirectness, FactStatus, RelationDirection, RelationType
from .repository import SnapshotRepository
from .service import InvalidCursorError, NotFoundError, ResearchService


def _response(page) -> dict:
    return {
        "data": page.items,
        "pagination": {
            "total": page.total,
            "limit": page.limit,
            "next_cursor": page.next_cursor,
        },
    }


def create_app(data_path: str | None = None) -> FastAPI:
    app = FastAPI(
        title="ARTI NVIDIA Relationship Research API",
        version="0.2.0",
        description="Point-in-time, evidence-linked listed-company relationships. Not investment advice.",
    )
    service = ResearchService(SnapshotRepository(data_path))
    app.state.service = service

    @app.exception_handler(NotFoundError)
    async def not_found_handler(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": str(exc)}},
        )

    @app.exception_handler(InvalidCursorError)
    async def cursor_handler(_: Request, exc: InvalidCursorError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "invalid_cursor", "message": str(exc)}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "request parameters are invalid",
                    "details": exc.errors(),
                }
            },
        )

    @app.get("/health")
    def health() -> dict:
        snapshot = service.repo.snapshot
        return {
            "status": "ok",
            "snapshot_version": snapshot.meta.snapshot_version,
            "cutoff_at": snapshot.meta.cutoff_at,
            "entity_count": len(snapshot.entities),
            "source_count": len(snapshot.sources),
            "evidence_count": len(snapshot.evidence),
            "relationship_count": len(snapshot.relationships),
        }

    @app.get("/v1/meta")
    def metadata() -> dict:
        return {"data": service.repo.snapshot.meta}

    @app.get("/v1/companies")
    def companies(
        q: str | None = None,
        listed_only: bool = True,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        cursor: str | None = None,
    ) -> dict:
        return _response(
            service.list_entities(
                q=q, listed_only=listed_only, limit=limit, cursor=cursor
            )
        )

    @app.get("/v1/companies/{company}")
    def company(company: str) -> dict:
        return {"data": service.resolve_entity(company)}

    @app.get("/v1/relationships")
    def relationships(
        company: str | None = None,
        relation_type: Annotated[list[RelationType] | None, Query()] = None,
        direction: Annotated[list[RelationDirection] | None, Query()] = None,
        status: Annotated[list[FactStatus] | None, Query()] = None,
        commercial_directness: Annotated[
            list[CommercialDirectness] | None, Query()
        ] = None,
        min_confidence: Annotated[int, Query(ge=0, le=100)] = 0,
        min_relevance: Annotated[int, Query(ge=0, le=100)] = 0,
        product: str | None = None,
        as_of: date | None = None,
        include_unknown: bool = True,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        cursor: str | None = None,
    ) -> dict:
        return _response(
            service.list_relationships(
                company=company,
                relation_types=set(relation_type) if relation_type else None,
                directions=set(direction) if direction else None,
                statuses=set(status) if status else None,
                commercial_directness=(
                    set(commercial_directness) if commercial_directness else None
                ),
                min_confidence=min_confidence,
                min_relevance=min_relevance,
                product=product,
                as_of=as_of,
                include_unknown=include_unknown,
                limit=limit,
                cursor=cursor,
            )
        )

    @app.get("/v1/relationships/{relationship_id}")
    def relationship(relationship_id: str) -> dict:
        return {"data": service.relationship_detail(relationship_id)}

    @app.get("/v1/evidence")
    def evidence_list(
        relationship_id: str | None = None,
        publisher: str | None = None,
        source_family: str | None = None,
        published_from: date | None = None,
        published_to: date | None = None,
        human_verified: bool | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        cursor: str | None = None,
    ) -> dict:
        return _response(
            service.list_evidence(
                relationship_id=relationship_id,
                publisher=publisher,
                source_family=source_family,
                published_from=published_from,
                published_to=published_to,
                human_verified=human_verified,
                limit=limit,
                cursor=cursor,
            )
        )

    @app.get("/v1/evidence/{evidence_id}")
    def evidence(evidence_id: str) -> dict:
        return {"data": service.get_evidence(evidence_id)}

    @app.get("/v1/graph")
    def graph(
        company: str,
        relation_type: Annotated[list[RelationType] | None, Query()] = None,
        direction: Annotated[list[RelationDirection] | None, Query()] = None,
        status: Annotated[list[FactStatus] | None, Query()] = None,
        commercial_directness: Annotated[
            list[CommercialDirectness] | None, Query()
        ] = None,
        min_confidence: Annotated[int, Query(ge=0, le=100)] = 0,
        min_relevance: Annotated[int, Query(ge=0, le=100)] = 0,
        product: str | None = None,
        as_of: date | None = None,
        include_unknown: bool = True,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
    ) -> dict:
        return {
            "data": service.graph(
                company=company,
                relation_types=set(relation_type) if relation_type else None,
                directions=set(direction) if direction else None,
                statuses=set(status) if status else None,
                commercial_directness=(
                    set(commercial_directness) if commercial_directness else None
                ),
                min_confidence=min_confidence,
                min_relevance=min_relevance,
                product=product,
                as_of=as_of,
                include_unknown=include_unknown,
                limit=limit,
            )
        }

    return app


app = create_app()


def main() -> None:
    uvicorn.run(
        "arti.api:app",
        host=os.getenv("ARTI_HOST", "127.0.0.1"),
        port=int(os.getenv("ARTI_PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    main()
