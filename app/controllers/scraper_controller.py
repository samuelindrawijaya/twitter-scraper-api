import json
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from app.schemas.scrape_request import ScrapeRequest
from app.schemas.scrape_response import JobStatusResponse, PreviewQueryResponse, StartScrapeResponse
from app.services.csv_export_service import CsvExportService
from app.services.job_service import JobService, job_service
from app.services.query_builder_service import QueryBuilderService
from app.services.twitter_scraper_service import TwitterScraperService
from app.services.tweet_normalizer_service import TweetNormalizerService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ScraperController:
    def __init__(self, jobs: JobService = job_service) -> None:
        self.jobs = jobs
        self.query_builder = QueryBuilderService()
        self.normalizer = TweetNormalizerService()
        self.csv_exporter = CsvExportService()

    async def start_scraping(self, request: ScrapeRequest, background_tasks: BackgroundTasks) -> StartScrapeResponse:
        job = self.jobs.create_job()
        background_tasks.add_task(self.run_scraping_job, job["job_id"], request)
        return StartScrapeResponse(job_id=job["job_id"], status="queued", message="Scraping job started")

    async def preview_query(self, request: ScrapeRequest) -> PreviewQueryResponse:
        return PreviewQueryResponse(queries=self.query_builder.build_queries(request))

    async def get_job(self, job_id: str) -> JobStatusResponse:
        job = self.jobs.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return self._job_response(job)

    async def download_job_result(self, job_id: str) -> FileResponse:
        job = self.jobs.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job["status"] != "completed" or not job.get("output_file"):
            raise HTTPException(status_code=409, detail="Job result is not ready")

        path = Path(job["output_file"])
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="Output file not found")

        return FileResponse(path=path, filename=path.name, media_type="text/csv")

    async def run_scraping_job(self, job_id: str, request: ScrapeRequest) -> None:
        try:
            self.jobs.set_running(job_id)
            queries = self.query_builder.build_queries(request)
            if not queries:
                raise ValueError("No valid query categories were generated from the request")

            scraper = TwitterScraperService()

            def progress(category: str, collected_rows: int, total_rows: int) -> None:
                self.jobs.update_progress(
                    job_id,
                    current_category=category,
                    collected_rows=collected_rows,
                    total_rows=total_rows,
                )

            raw_results = await scraper.collect(queries, request.limit_per_category, progress)
            if request.debug_raw_sample:
                self._save_debug_raw_sample(job_id, raw_results)
            rows = self.normalizer.normalize_many(raw_results)
            if not rows:
                raise ValueError("No tweets were collected for the generated queries")
            output_file = self.csv_exporter.save(rows, request.output_name)
            self.jobs.set_completed(job_id, output_file=output_file, total_rows=len(rows))
        except Exception as exc:
            logger.exception("Scraping job failed: %s", job_id)
            self.jobs.set_failed(job_id, str(exc))

    def _save_debug_raw_sample(self, job_id: str, raw_results: dict[str, list[Any]]) -> None:
        for category, tweets in raw_results.items():
            if not tweets:
                continue
            debug_dir = Path(self.csv_exporter.output_dir)
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_path = debug_dir / f"{job_id}_{category}_raw_sample.json"
            sample = tweets[0]
            try:
                payload = sample.dict() if hasattr(sample, "dict") else vars(sample)
            except TypeError:
                payload = repr(sample)
            debug_path.write_text(json.dumps(payload, default=str, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("Saved debug raw sample to %s", debug_path)
            return

    def _job_response(self, job: dict[str, Any]) -> JobStatusResponse:
        download_url = None
        if job["status"] == "completed" and job.get("output_file"):
            download_url = f"/api/scrape/jobs/{job['job_id']}/download"
        return JobStatusResponse(**job, download_url=download_url)


scraper_controller = ScraperController()
