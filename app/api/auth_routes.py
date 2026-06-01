"""Auth API routes — expose twscrape account management over HTTP."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from twscrape import API, AccountsPool

from app.config.settings import settings

DB_FILE = "accounts.db"
REQUIRED_COOKIES = {"auth_token", "ct0"}


def verify_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    if not settings.REQUIRE_API_KEY:
        return
    if not settings.API_KEY or x_api_key != settings.API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")


router = APIRouter(prefix="/api/auth", tags=["auth"], dependencies=[Depends(verify_api_key)])


# ---------- Schemas ----------

class AddCookieRequest(BaseModel):
    username: str
    cookies: str
    replace: bool = False


class VerifyRequest(BaseModel):
    query: str = "from:TwitterDev"
    limit: int = 1


class DeleteAccountRequest(BaseModel):
    username: str


class AccountInfo(BaseModel):
    username: str
    active: bool
    logged_in: bool
    total_req: int
    last_used: Optional[str] = None
    error_msg: Optional[str] = None


class AuthStatusResponse(BaseModel):
    accounts: list[AccountInfo]
    total: int
    active: int


class AddCookieResponse(BaseModel):
    username: str
    active: bool
    message: str


class VerifyResponse(BaseModel):
    success: bool
    tweets_fetched: int
    sample: Optional[str] = None
    error: Optional[str] = None


class DeleteAccountResponse(BaseModel):
    username: str
    message: str


# ---------- Helpers ----------

def _parse_cookies(cookie_string: str) -> str:
    cookie_string = cookie_string.strip()
    if not cookie_string:
        raise ValueError("Cookie string is empty")

    cookies: dict[str, str] = {}
    for part in cookie_string.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        cookies[name.strip()] = value.strip()

    missing = sorted(REQUIRED_COOKIES - set(cookies))
    if missing:
        raise ValueError(f"Missing required cookies: {', '.join(missing)}. Need auth_token and ct0.")
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


# ---------- Endpoints ----------

@router.get("/status", response_model=AuthStatusResponse)
async def auth_status():
    pool = AccountsPool(DB_FILE)
    items = [dict(x) for x in await pool.accounts_info()]

    accounts = []
    for item in items:
        accounts.append(AccountInfo(
            username=str(item.get("username", "")),
            active=bool(item.get("active")),
            logged_in=bool(item.get("logged_in")),
            total_req=int(item.get("total_req", 0)),
            last_used=str(item["last_used"]) if item.get("last_used") else None,
            error_msg=str(item["error_msg"]) if item.get("error_msg") else None,
        ))

    active_count = sum(1 for a in accounts if a.active)
    return AuthStatusResponse(accounts=accounts, total=len(accounts), active=active_count)


@router.post("/add-cookie", response_model=AddCookieResponse)
async def add_cookie(req: AddCookieRequest):
    try:
        cookie_str = _parse_cookies(req.cookies)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    pool = AccountsPool(DB_FILE)
    existing = await pool.get_account(req.username)

    if existing is not None and not req.replace:
        raise HTTPException(
            status_code=409,
            detail=f"Account '{req.username}' already exists. Set replace=true to overwrite.",
        )
    if existing is not None:
        await pool.delete_accounts([req.username])

    await pool.add_account_cookies(req.username, cookie_str)
    account = await pool.get_account(req.username)
    active = bool(account and account.active)

    return AddCookieResponse(
        username=req.username,
        active=active,
        message=f"Account '{req.username}' added (active={active})",
    )


@router.post("/verify", response_model=VerifyResponse)
async def verify_auth(req: VerifyRequest):
    pool = AccountsPool(DB_FILE, raise_when_no_account=True)
    api = API(pool)

    try:
        count = 0
        sample_text = None
        async for tweet in api.search(req.query, limit=req.limit):
            count += 1
            text = getattr(tweet, "rawContent", None) or getattr(tweet, "text", "") or ""
            if sample_text is None:
                sample_text = text[:200]
            if count >= req.limit:
                break
    except Exception as exc:
        return VerifyResponse(success=False, tweets_fetched=0, error=str(exc))

    return VerifyResponse(
        success=count > 0,
        tweets_fetched=count,
        sample=sample_text,
        error=None if count > 0 else "Query returned 0 tweets",
    )


@router.delete("/accounts/{username}", response_model=DeleteAccountResponse)
async def delete_account(username: str):
    pool = AccountsPool(DB_FILE)
    existing = await pool.get_account(username)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Account '{username}' not found")

    await pool.delete_accounts([username])
    return DeleteAccountResponse(username=username, message=f"Account '{username}' deleted")
