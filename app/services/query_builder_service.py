from datetime import timedelta

from app.schemas.scrape_request import ScrapeRequest


class QueryBuilderService:
    RETWEET_EXCLUSION = "-filter:retweets"

    def build_queries(self, request: ScrapeRequest) -> dict[str, str]:
        if request.raw_query:
            query = request.raw_query.strip()
            if not request.include_retweets and not self._has_retweet_exclusion(query):
                query = f"{query} {self.RETWEET_EXCLUSION}"
            return {"custom": query}

        date_filter = self._date_filter(request)
        retweet_filter = "" if request.include_retweets else f" {self.RETWEET_EXCLUSION}"
        queries: dict[str, str] = {}

        if request.keywords or request.contexts:
            parts = []
            if request.keywords:
                parts.append(self._or_group(request.keywords))
            if request.contexts:
                parts.append(self._or_group(request.contexts))
            queries["umum"] = f"{' '.join(parts)} lang:{self._normalize_lang(request.lang)} {date_filter}{retweet_filter}".strip()

        if request.hashtags:
            queries["hashtag"] = f"{self._or_group(request.hashtags)} lang:{self._normalize_lang(request.lang)} {date_filter}{retweet_filter}".strip()

        if request.actors:
            related_terms = [*request.keywords, *request.contexts]
            parts = [self._or_group(request.actors)]
            if related_terms:
                parts.append(self._or_group(related_terms))
            queries["aktor"] = f"{' '.join(parts)} lang:{self._normalize_lang(request.lang)} {date_filter}{retweet_filter}".strip()

        return queries

    def _date_filter(self, request: ScrapeRequest) -> str:
        assert request.start_date is not None
        assert request.end_date is not None
        until_date = request.end_date + timedelta(days=1)
        return f"since:{request.start_date.isoformat()} until:{until_date.isoformat()}"

    def _or_group(self, terms: list[str]) -> str:
        clean_terms = [self._format_term(term.strip()) for term in terms if term and term.strip()]
        return f"({' OR '.join(clean_terms)})"

    def _format_term(self, term: str) -> str:
        if term.startswith('"') and term.endswith('"'):
            return term
        if " " in term:
            return f'"{term}"'
        return term

    def _has_retweet_exclusion(self, query: str) -> bool:
        lowered = query.lower()
        return "-filter:retweets" in lowered or "exclude:retweets" in lowered
    
    def _normalize_lang(self, lang: str) -> str:
        if lang == "id":
            return "in"
        return lang
