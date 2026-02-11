"""FastAPI entrypoint for sentence chat product."""

from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, HTTPException

from sentence_chat_product.api.schemas import (
    CalculateSentenceRequest,
    CalculateSentenceResponse,
    ChatTurnRequest,
    ChatTurnResponse,
    GuidelineChunkOut,
    SearchGuidelinesRequest,
    SearchGuidelinesResponse,
    SentencingRangeOut,
)
from sentence_chat_product.config import get_settings
from sentence_chat_product.core.calculator import calculate_sentence
from sentence_chat_product.core.retrieval import RetrievalService
from sentence_chat_product.core.types import SentenceCalculationInput
from sentence_chat_product.db.repository import Repository

app = FastAPI(title="Sentence Chat Product API", version="0.1.0")


@lru_cache
def get_repository() -> Repository:
    settings = get_settings()
    return Repository(settings.database_url)


@lru_cache
def get_retrieval_service() -> RetrievalService:
    settings = get_settings()
    repo = get_repository()
    return RetrievalService(repository=repo, settings=settings)


def resolve_offence(
    repo: Repository,
    offence_id: str | None,
    offence_query: str | None,
) -> tuple[Any, list[str]]:
    trace: list[str] = []

    if offence_id:
        offence = repo.fetch_offence_by_id(offence_id)
        if not offence:
            raise HTTPException(status_code=404, detail=f"Offence not found: {offence_id}")
        return offence, trace

    if not offence_query:
        raise HTTPException(status_code=400, detail="Provide offence_id or offence_query")

    matches = repo.search_offences(offence_query, limit=5)
    if not matches:
        raise HTTPException(status_code=404, detail=f"No offence found for query: {offence_query}")

    chosen = matches[0]
    trace.append(
        f"Resolved offence query '{offence_query}' to '{chosen.canonical_name}' ({chosen.offence_id})."
    )
    if len(matches) > 1:
        trace.append("Multiple matches found; top similarity match selected automatically.")

    return chosen, trace


def to_response_payload(result: Any) -> CalculateSentenceResponse:
    matched_range = None
    if result.matched_range:
        matched_range = SentencingRangeOut(**asdict(result.matched_range))

    return CalculateSentenceResponse(
        offence_id=result.offence_id,
        offence_name=result.offence_name,
        sentence_type=result.sentence_type,
        pre_plea_term_months=result.pre_plea_term_months,
        post_plea_term_months=result.post_plea_term_months,
        minimum_sentence_triggered=result.minimum_sentence_triggered,
        minimum_floor_pre_plea_months=result.minimum_floor_pre_plea_months,
        minimum_floor_post_plea_months=result.minimum_floor_post_plea_months,
        release_fraction=result.release_fraction,
        estimated_time_in_custody_months=result.estimated_time_in_custody_months,
        victim_surcharge_gbp=result.victim_surcharge_gbp,
        matched_range=matched_range,
        warnings=result.warnings,
        trace=result.trace,
    )


def calculate_from_request(req: CalculateSentenceRequest) -> CalculateSentenceResponse:
    repo = get_repository()

    offence, resolution_trace = resolve_offence(repo, req.offence_id, req.offence_query)
    matrix_rows = repo.fetch_sentencing_matrix(offence.offence_id)

    model = SentenceCalculationInput(
        offence=offence,
        offence_date=req.offence_date,
        conviction_date=req.conviction_date,
        sentence_date=req.sentence_date,
        age_at_offence=req.age_at_offence,
        age_at_conviction=req.age_at_conviction,
        age_at_sentence=req.age_at_sentence,
        plea_stage=req.plea_stage,
        sentence_type=req.sentence_type,
        culpability=req.culpability,
        harm=req.harm,
        pre_plea_term_months=req.pre_plea_term_months,
        extension_months=req.extension_months,
        fine_amount=req.fine_amount,
        dangerousness_assessed=req.dangerousness_assessed,
        prior_listed_offence_with_custody=req.prior_listed_offence_with_custody,
        prior_domestic_burglary_count=req.prior_domestic_burglary_count,
        prior_class_a_trafficking_count=req.prior_class_a_trafficking_count,
        prior_relevant_weapon_conviction=req.prior_relevant_weapon_conviction,
        terrorism_flag=req.terrorism_flag,
        minimum_sentence_unjust_or_exceptional=req.minimum_sentence_unjust_or_exceptional,
        replicate_ace_release_bug=req.replicate_ace_release_bug,
    )

    try:
        result = calculate_sentence(model, matrix_rows)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result.trace = resolution_trace + result.trace
    payload = to_response_payload(result)

    try:
        repo.store_calculation_audit(
            offence_id=result.offence_id,
            request_payload=req.model_dump(mode="json"),
            result_payload=payload.model_dump(mode="json"),
        )
    except Exception:
        # Audit logging should not break user flow.
        pass

    return payload


def convert_chunks(rows: list[dict[str, Any]]) -> list[GuidelineChunkOut]:
    return [
        GuidelineChunkOut(
            chunk_id=row.get("chunk_id", ""),
            guideline_id=row.get("guideline_id", ""),
            offence_id=row.get("offence_id"),
            section_type=row.get("section_type"),
            section_heading=row.get("section_heading"),
            chunk_text=row.get("chunk_text", ""),
            source_url=row.get("source_url"),
            score=row.get("score"),
        )
        for row in rows
    ]


@app.get("/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/calculate_sentence", response_model=CalculateSentenceResponse)
def calculate_sentence_endpoint(req: CalculateSentenceRequest) -> CalculateSentenceResponse:
    return calculate_from_request(req)


@app.post("/v1/search_guidelines", response_model=SearchGuidelinesResponse)
def search_guidelines_endpoint(req: SearchGuidelinesRequest) -> SearchGuidelinesResponse:
    retrieval = get_retrieval_service()
    rows = retrieval.search(req.query, offence_id=req.offence_id, top_k=req.top_k)
    return SearchGuidelinesResponse(results=convert_chunks(rows))


@app.post("/v1/chat_turn", response_model=ChatTurnResponse)
def chat_turn_endpoint(req: ChatTurnRequest) -> ChatTurnResponse:
    follow_up: list[str] = []

    calc_response: CalculateSentenceResponse | None = None
    offence_id = req.offence_id

    if req.calculation is not None:
        calc_request = req.calculation
        if not calc_request.offence_id and offence_id:
            calc_request = calc_request.model_copy(update={"offence_id": offence_id})
        if not calc_request.offence_id and not calc_request.offence_query and req.offence_query:
            calc_request = calc_request.model_copy(update={"offence_query": req.offence_query})
        calc_response = calculate_from_request(calc_request)
        offence_id = calc_response.offence_id
    else:
        if not offence_id and not req.offence_query:
            follow_up.append("Which offence is this for? Provide offence_id or offence name.")

    retrieval = get_retrieval_service()
    rows = retrieval.search(req.message, offence_id=offence_id, top_k=req.top_k)
    citations = convert_chunks(rows)

    if follow_up:
        return ChatTurnResponse(
            reply="I need one more detail before I can calculate a sentence.",
            calculation=calc_response,
            citations=citations,
            follow_up_questions=follow_up,
        )

    reply_parts: list[str] = []
    if calc_response:
        reply_parts.append(
            (
                f"Calculated sentence for {calc_response.offence_name}: "
                f"post-plea term {calc_response.post_plea_term_months} months, "
                f"estimated custody served {calc_response.estimated_time_in_custody_months} months, "
                f"victim surcharge £{calc_response.victim_surcharge_gbp}."
            )
        )
        if calc_response.warnings:
            reply_parts.append("Warnings: " + " ".join(calc_response.warnings))

    if citations:
        top = citations[0]
        reply_parts.append(
            "Top supporting guideline section: "
            f"{top.section_heading or top.section_type or 'section'} ({top.source_url or 'no-url'})."
        )
    else:
        reply_parts.append("No guideline citation found for this query.")

    return ChatTurnResponse(
        reply="\n\n".join(reply_parts),
        calculation=calc_response,
        citations=citations,
        follow_up_questions=[],
    )
