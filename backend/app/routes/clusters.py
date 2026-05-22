import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.db.client import get_db
from app.models.enums import RiskDomain
from app.services.clustering import run_clustering

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/clusters", tags=["clusters"])


@router.post("/run")
async def trigger_clustering(background_tasks: BackgroundTasks):
    """
    Manually trigger the signal clustering job.

    Returns immediately with a job_id. Poll GET /api/pipeline/runs/{job_id}
    for status and result. This prevents HTTP timeouts on large signal sets.
    """
    db = get_db()
    run = db.table("pipeline_runs").insert({"type": "clustering"}).execute().data[0]
    background_tasks.add_task(_run_clustering_job, run["id"])
    return {"job_id": run["id"], "status": "running"}


async def _run_clustering_job(run_id: str) -> None:
    db = get_db()
    try:
        written = await run_clustering()
        db.table("pipeline_runs").update({
            "status": "completed",
            "completed_at": datetime.now(UTC).isoformat(),
            "result": {"clusters_written": written},
        }).eq("id", run_id).execute()
        logger.info("Clustering job %s complete: %d clusters written", run_id, written)
    except Exception:
        logger.exception("Clustering background job %s failed", run_id)
        db.table("pipeline_runs").update({
            "status": "failed",
            "completed_at": datetime.now(UTC).isoformat(),
            "error": "Job failed - see server logs",
        }).eq("id", run_id).execute()


@router.get("")
async def list_clusters(
    risk_domain: Annotated[RiskDomain | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    min_score: Annotated[float | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """
    List signal clusters, ordered by score descending.

    Filters:
    - risk_domain: narrow to a specific domain
    - status: 'pending' | 'card_generated' | 'dismissed'
    - min_score: only return clusters above this score threshold
    """
    db = get_db()
    query = (
        db.table("signal_clusters")
        .select("*")
        .order("score", desc=True)
        .range(offset, offset + limit - 1)
    )

    if risk_domain:
        query = query.eq("risk_domain", risk_domain.value)
    if status:
        query = query.eq("status", status)
    if min_score is not None:
        query = query.gte("score", min_score)

    result = query.execute()
    return {"clusters": result.data, "offset": offset, "limit": limit}


@router.get("/{cluster_id}")
async def get_cluster(cluster_id: str):
    """Fetch a single cluster by ID, including the full metadata and signal_ids list."""
    db = get_db()
    result = db.table("signal_clusters").select("*").eq("id", cluster_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return result.data
