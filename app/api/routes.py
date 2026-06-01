from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from fastapi.responses import FileResponse

from app.config.settings import settings
from app.controllers.scraper_controller import scraper_controller
from app.schemas.scrape_request import ScrapeRequest
from app.schemas.scrape_response import JobStatusResponse, PreviewQueryResponse, StartScrapeResponse

router = APIRouter(prefix="/api/scrape", tags=["scrape"])


def verify_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    if not settings.REQUIRE_API_KEY:
        return
    if not settings.API_KEY or x_api_key != settings.API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


@router.post("/start", response_model=StartScrapeResponse, dependencies=[Depends(verify_api_key)])
async def start_scraping(request: ScrapeRequest, background_tasks: BackgroundTasks) -> StartScrapeResponse:
    return await scraper_controller.start_scraping(request, background_tasks)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse, dependencies=[Depends(verify_api_key)])
async def get_job(job_id: str) -> JobStatusResponse:
    return await scraper_controller.get_job(job_id)


@router.get("/jobs/{job_id}/download", dependencies=[Depends(verify_api_key)])
async def download_job_result(job_id: str) -> FileResponse:
    return await scraper_controller.download_job_result(job_id)


@router.post("/preview-query", response_model=PreviewQueryResponse)
async def preview_query(request: ScrapeRequest) -> PreviewQueryResponse:
    return await scraper_controller.preview_query(request)
