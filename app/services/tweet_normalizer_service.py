from datetime import datetime
import re
from typing import Any


CSV_COLUMNS = [
    "category",
    "conversation_id_str",
    "created_at",
    "favorite_count",
    "full_text",
    "id_str",
    "in_reply_to_screen_name",
    "lang",
    "quote_count",
    "reply_count",
    "retweet_count",
    "user_id_str",
    "username",
    "user_followers_count",
    "user_verified",
    "user_bio",
    "mentions",
    "hashtags",
    "retweeted_from_user",
]


class TweetNormalizerService:
    def normalize_many(self, raw_by_category: dict[str, list[Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for category, tweets in raw_by_category.items():
            for tweet in tweets:
                rows.append(self.normalize(tweet, category))
        return rows

    def normalize(self, tweet: Any, category: str) -> dict[str, Any]:
        user = self._get(tweet, "user")
        reply_user = self._get(tweet, "inReplyToUser", "in_reply_to_user")
        retweeted_tweet = self._get(tweet, "retweetedTweet", "retweeted_tweet", "retweetedStatus")
        retweeted_user = self._get(retweeted_tweet, "user") if retweeted_tweet else None

        return {
            "category": category,
            "conversation_id_str": self._to_str(self._get(tweet, "conversationId", "conversation_id", default="")),
            "created_at": self._format_datetime(self._get(tweet, "date", "created_at", default="")),
            "favorite_count": self._get(tweet, "likeCount", "favoriteCount", "favorite_count", default=0),
            "full_text": self._clean_full_text(self._get(tweet, "rawContent", "text", "content", default="")),
            "id_str": self._to_str(self._get(tweet, "id", "id_str", default="")),
            "in_reply_to_screen_name": self._get(reply_user, "username", "screen_name", default="") if reply_user else "",
            "lang": self._get(tweet, "lang", default=""),
            "quote_count": self._get(tweet, "quoteCount", "quote_count", default=0),
            "reply_count": self._get(tweet, "replyCount", "reply_count", default=0),
            "retweet_count": self._get(tweet, "retweetCount", "retweet_count", default=0),
            "user_id_str": self._to_str(self._get(user, "id", "id_str", default="")) if user else "",
            "username": self._get(user, "username", "screen_name", default="") if user else "",
            "user_followers_count": self._get(
                user,
                "followersCount",
                "followers_count",
                "followers",
                default=0,
            ) if user else 0,
            "user_verified": self._to_bool_str(
                self._get(
                    user,
                    "verified",
                    "isVerified",
                    "is_verified",
                    "blue",
                    "isBlueVerified",
                    "is_blue_verified",
                    default=False,
                )
            ) if user else "False",
            "user_bio": self._get(
                user,
                "rawDescription",
                "description",
                "bio",
                "profileDescription",
                default="",
            ) if user else "",
            "mentions": self._extract_mentions(tweet),
            "hashtags": self._extract_hashtags(tweet),
            "retweeted_from_user": self._get(retweeted_user, "username", "screen_name", default="") if retweeted_user else "",
        }

    def _get(self, obj: Any, *names: str, default: Any = None) -> Any:
        if obj is None:
            return default
        for name in names:
            try:
                if isinstance(obj, dict) and name in obj:
                    value = obj[name]
                else:
                    value = getattr(obj, name)
                if value is not None:
                    return value
            except (AttributeError, KeyError, TypeError):
                continue
        return default

    def _format_datetime(self, value: Any) -> str:
        if isinstance(value, datetime):
            return value.isoformat()
        return self._to_str(value)

    def _to_str(self, value: Any) -> str:
        return "" if value is None else str(value)

    def _clean_full_text(self, value: Any) -> str:
        text = self._to_str(value)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" *\n+ *", " ", text)
        return text.strip()

    def _to_bool_str(self, value: Any) -> str:
        if isinstance(value, bool):
            return str(value)
        if value is None:
            return "False"
        if isinstance(value, (int, float)):
            return str(bool(value))
        text = str(value).strip().lower()
        return str(text in {"true", "1", "yes", "y"})

    def _extract_mentions(self, tweet: Any) -> str:
        mentioned = self._get(tweet, "mentionedUsers", "mentioned_users")
        usernames: list[str] = []
        if mentioned:
            for user in mentioned:
                username = self._get(user, "username", "screen_name", default="")
                if username:
                    usernames.append(str(username))
        if not usernames:
            entities = self._get(tweet, "entities", default={})
            mentions = self._get(entities, "user_mentions", "mentions", default=[])
            for item in mentions or []:
                username = self._get(item, "screen_name", "username", default="")
                if username:
                    usernames.append(str(username))
        return ",".join(dict.fromkeys(usernames))

    def _extract_hashtags(self, tweet: Any) -> str:
        tags = self._get(tweet, "hashtags", default=None)
        values: list[str] = []
        if tags:
            for tag in tags:
                if isinstance(tag, str):
                    values.append(self._format_hashtag(tag))
                else:
                    text = self._get(tag, "text", "tag", default="")
                    if text:
                        values.append(self._format_hashtag(text))
        if not values:
            entities = self._get(tweet, "entities", default={})
            hashtags = self._get(entities, "hashtags", default=[])
            for item in hashtags or []:
                text = self._get(item, "text", "tag", default="")
                if text:
                    values.append(self._format_hashtag(text))
        return ",".join(dict.fromkeys(values))

    def _format_hashtag(self, value: Any) -> str:
        tag = self._to_str(value).strip().lstrip("#").strip()
        return f"#{tag}" if tag else ""
