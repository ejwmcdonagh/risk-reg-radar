"""
Pipeline run status endpoints.

Run endpoints (POST /api/cards/run, POST /api/clusters/run) fire jobs in the
background and return a job_id immediately. Use these endpoints to check status
rather than waiting for the trigger call to complete.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.db.client import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.get("/runs")
async def list_runs(
    type: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """List recent pipeline runs, newest first."""
    db = get_db()
    query = (
        db.table("pipeline_runs")
        .select("*")
        .order("started_at", desc=True)
        .limit(limit)
    )
    if type:
        query = query.eq("type", type)
    result = query.execute()
    return {"runs": result.data}


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get the status and result of a single pipeline run."""
    db = get_db()
    result = db.table("pipeline_runs").select("*").eq("id", run_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Run not found")
    return result.data
