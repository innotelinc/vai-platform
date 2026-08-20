"""Interview grading results surfaced from Grist.

The n8n grader writes interview results to the Grist ``Interviews`` table
(see deploy/interview-stack/README.md). This router reads that table
server-side — using the API-key credentials from the environment — and
exposes the results to the UI, so reviewers never need Grist credentials
or the Grist UI itself.

The endpoint is intentionally NOT org-scoped: the Grist document is a single
deployment-wide store shared by the whole interview stack, so any
authenticated user may review it.
"""

import json
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel

from api.constants import GRIST_API_KEY, GRIST_BASE_URL, GRIST_DOC_ID
from api.db.models import UserModel
from api.services.auth.depends import get_user

router = APIRouter(prefix="/interviews")

GRIST_TABLE = "Interviews"
HTTP_TIMEOUT = httpx.Timeout(15.0)


class InterviewResult(BaseModel):
    """One graded interview row from the Grist Interviews table."""

    id: int
    student: Optional[str]
    phone: Optional[str]
    run_id: Optional[str]
    score: Optional[float]
    verdict: Optional[str]
    dimensions: Optional[Dict[str, Any]]
    strengths: Optional[List[str]]
    improvements: Optional[List[str]]
    transcript: Optional[str]


class InterviewsSummary(BaseModel):
    total: int
    pass_count: int
    review_count: int
    fail_count: int
    average_score: Optional[float]


class InterviewsResponse(BaseModel):
    configured: bool
    summary: InterviewsSummary
    interviews: List[InterviewResult]


def _parse_json_field(raw: Any) -> Any:
    """Parse a Grist Text column that stores JSON; None when unset/invalid."""
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


async def _fetch_interviews() -> List[Dict[str, Any]]:
    """Fetch all rows of the Grist Interviews table."""
    url = f"{GRIST_BASE_URL}/api/docs/{GRIST_DOC_ID}/tables/{GRIST_TABLE}/records"
    headers = {"Authorization": f"Bearer {GRIST_API_KEY}"}
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    records = data.get("records", [])
    # Grist row ids increase with insertion order, so sort newest first.
    records.sort(key=lambda r: r.get("id", 0), reverse=True)
    return records


@router.get("", response_model=InterviewsResponse)
async def list_interviews(
    user: UserModel = Depends(get_user),
) -> InterviewsResponse:
    """List graded interviews newest-first with a verdict summary.

    Returns ``configured=false`` with empty data when the Grist credentials
    are not set up (e.g. a fresh install without the interview stack), so the
    UI can show a friendly setup hint instead of an error.
    """
    if not GRIST_DOC_ID or not GRIST_API_KEY:
        return InterviewsResponse(
            configured=False,
            summary=InterviewsSummary(
                total=0, pass_count=0, review_count=0, fail_count=0, average_score=None
            ),
            interviews=[],
        )

    try:
        records = await _fetch_interviews()
    except httpx.HTTPStatusError as e:
        logger.error(f"Grist interviews fetch failed: HTTP {e.response.status_code}")
        raise
    except httpx.RequestError as e:
        logger.error(f"Grist interviews fetch failed: {e}")
        raise

    interviews: List[InterviewResult] = []
    verdict_counts = {"pass": 0, "review": 0, "fail": 0}
    scores: List[float] = []

    for rec in records:
        fields = rec.get("fields", {})
        score = fields.get("Score")
        verdict = fields.get("Verdict")
        if score is not None:
            try:
                score = float(score)
                scores.append(score)
            except (TypeError, ValueError):
                score = None
        if verdict and verdict.lower() in verdict_counts:
            verdict_counts[verdict.lower()] += 1

        interviews.append(
            InterviewResult(
                id=rec.get("id", 0),
                student=fields.get("Student"),
                phone=fields.get("Phone"),
                run_id=str(fields.get("RunID")) if fields.get("RunID") is not None else None,
                score=score,
                verdict=verdict,
                dimensions=_parse_json_field(fields.get("Dimensions")),
                strengths=_parse_json_field(fields.get("Strengths")),
                improvements=_parse_json_field(fields.get("Improvements")),
                transcript=fields.get("Transcript"),
            )
        )

    return InterviewsResponse(
        configured=True,
        summary=InterviewsSummary(
            total=len(interviews),
            pass_count=verdict_counts["pass"],
            review_count=verdict_counts["review"],
            fail_count=verdict_counts["fail"],
            average_score=round(sum(scores) / len(scores), 2) if scores else None,
        ),
        interviews=interviews,
    )
