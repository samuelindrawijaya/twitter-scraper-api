# Twitter Scraper API

FastAPI REST API for collecting public X/Twitter search results with `twscrape` for academic/research purposes.

This project does not use Selenium, does not use the paid X API, and must not be used to bypass captcha, login protections, deleted tweets, private accounts, or protected accounts. Collect only public posts and respect X/Twitter rate limits and terms.

## Installation

Linux/macOS:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Windows:

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Environment

Copy `.env.example` to `.env` if you want to customize settings:

```bash
cp .env.example .env
```

Available settings:

```env
APP_NAME=twitter-scraper-api
OUTPUT_DIR=output
REQUIRE_API_KEY=false
API_KEY=change_me
DEFAULT_LIMIT_PER_CATEGORY=1000
SAFE_DELAY_SECONDS=1.0
```

If `REQUIRE_API_KEY=true`, send `X-API-Key: your_key` for start, status, and download endpoints.

## Setup twscrape account

`twscrape` requires a configured account/cookie before searches can run. Depending on your installed twscrape version, use the supported account setup command. Common cookie setup:

```bash
twscrape add_cookie your_username
```

Follow the prompt/instructions shown by your installed `twscrape` version. Do not automate captcha solving or bypass login protections.

Check accounts:

```bash
twscrape accounts
```

Ensure at least one account is available/active before starting a scrape job.

## Run API

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

## Preview query example

```bash
curl -X POST "http://localhost:8000/api/scrape/preview-query" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2026-01-01",
    "end_date": "2026-03-30",
    "keywords": ["UU TPKS", "Undang-Undang TPKS", "kekerasan seksual"],
    "contexts": ["lapor", "implementasi", "kasus", "korban"],
    "hashtags": ["#UUTPKS", "#KekerasanSeksual", "#StopKekerasanSeksual"],
    "actors": ["@komnasperempuan", "@DivHumas_Polri", "Komnas Perempuan", "Polri", "KemenPPPA"],
    "lang": "id",
    "limit_per_category": 1000,
    "include_retweets": false,
    "output_name": "twitter_tpks_dataset.csv"
  }'
```

## Start scrape example

```bash
curl -X POST "http://localhost:8000/api/scrape/start" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2026-01-01",
    "end_date": "2026-03-30",
    "keywords": ["UU TPKS", "Undang-Undang TPKS", "kekerasan seksual"],
    "contexts": ["lapor", "implementasi", "kasus", "korban"],
    "hashtags": ["#UUTPKS", "#KekerasanSeksual", "#StopKekerasanSeksual"],
    "actors": ["@komnasperempuan", "@DivHumas_Polri", "Komnas Perempuan", "Polri", "KemenPPPA"],
    "lang": "id",
    "limit_per_category": 1000,
    "include_retweets": false,
    "output_name": "twitter_tpks_dataset.csv"
  }'
```

Response:

```json
{
  "job_id": "uuid-string",
  "status": "queued",
  "message": "Scraping job started"
}
```

## Check status

```bash
curl "http://localhost:8000/api/scrape/jobs/{job_id}"
```

## Download result

```bash
curl -L "http://localhost:8000/api/scrape/jobs/{job_id}/download" -o twitter_tpks_dataset.csv
```

## Raw query mode

When `raw_query` is provided, the API creates only one category named `custom`, ignores keywords/contexts/hashtags/actors, and applies `limit_per_category`. If `include_retweets=false`, `-filter:retweets` is appended only when no retweet exclusion is already present.

Example:

```bash
curl -X POST "http://localhost:8000/api/scrape/preview-query" \
  -H "Content-Type: application/json" \
  -d '{
    "raw_query": "("UU TPKS" OR #UUTPKS) lang:id since:2026-01-01 until:2026-03-31",
    "include_retweets": false,
    "limit_per_category": 100
  }'
```

## Notes

- Jobs are stored in memory for this MVP. Restarting the server clears job status.
- Output CSV files are written to `output/` by default using UTF-8 BOM for spreadsheet compatibility.
- The CSV columns are fixed by design for downstream research workflows.
