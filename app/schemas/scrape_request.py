from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class ScrapeRequest(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    keywords: list[str] = Field(default_factory=list)
    contexts: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    actors: list[str] = Field(default_factory=list)
    lang: str = "id"
    limit_per_category: int = Field(default=1000, ge=1, le=10000)
    include_retweets: bool = False
    debug_raw_sample: bool = False
    raw_query: Optional[str] = None
    output_name: Optional[str] = "twitter_dataset.csv"

    @field_validator("keywords", "contexts", "hashtags", "actors", mode="before")
    @classmethod
    def normalize_lists(cls, value):
        if value is None:
            return []
        return value

    @field_validator("output_name")
    @classmethod
    def default_output_name(cls, value: Optional[str]) -> str:
        return value or "twitter_dataset.csv"

    @model_validator(mode="after")
    def validate_dates_when_no_raw_query(self):
        if not self.raw_query:
            if self.start_date is None or self.end_date is None:
                raise ValueError("start_date and end_date are required when raw_query is null")
            if self.end_date < self.start_date:
                raise ValueError("end_date must be greater than or equal to start_date")
        return self
