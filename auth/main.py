"""Registration and login only. Manuscripts never reach this process."""

import os
import sqlite3
import uuid
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from auth.security import hash_password, issue_token, read_token, verify_password

DATA = Path(os.environ.get("NOVEL_AUTH_DATA", "auth_data"))
DATA.mkdir(parents=True, exist_ok=True)
SECRET_PATH = DATA / "secret"
if not SECRET_PATH.exists():
    SECRET_PATH.write_text(os.environ.get("NOVEL_AUTH_SECRET") or uuid.uuid4().hex, encoding="utf-8")
SECRET = os.environ.get("NOVEL_AUTH_SECRET") or SECRET_PATH.read_text(encoding="utf-8").strip()

db = sqlite3.connect(DATA / "accounts.sqlite", check_same_thread=False)
db.row_factory = sqlite3.Row
db.execute(
    """
    CREATE TABLE IF NOT EXISTS account (
        id TEXT PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        salt TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """
)
db.commit()

app = FastAPI(title="Novel accounts", version="0.1.0")


class RegisterBody(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=200)


class LoginBody(BaseModel):
    email: str
    password: str


def _user(row: sqlite3.Row) -> dict[str, str]:
    return {"id": row["id"], "email": row["email"], "name": row["name"]}


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="登录后才能使用")
    user_id = read_token(authorization.removeprefix("Bearer ").strip(), SECRET)
    if not user_id:
        raise HTTPException(status_code=401, detail="登录已失效")
    row = db.execute("SELECT * FROM account WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="登录已失效")
    return user_id


@app.get("/health")
def health() -> dict[str, str]:
    return {"ok": "true"}


@app.post("/register")
def register(body: RegisterBody) -> dict[str, object]:
    email = body.email.strip().lower()
    if db.execute("SELECT 1 FROM account WHERE email = ?", (email,)).fetchone():
        raise HTTPException(status_code=409, detail="这个邮箱已经注册过")
    salt, digest = hash_password(body.password)
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO account (id, email, name, salt, password_hash, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
        (user_id, email, body.name.strip(), salt, digest),
    )
    db.commit()
    row = db.execute("SELECT * FROM account WHERE id = ?", (user_id,)).fetchone()
    return {"token": issue_token(user_id, SECRET), "user": _user(row)}


@app.post("/login")
def login(body: LoginBody) -> dict[str, object]:
    row = db.execute(
        "SELECT * FROM account WHERE email = ?", (body.email.strip().lower(),)
    ).fetchone()
    if row is None or not verify_password(body.password, row["salt"], row["password_hash"]):
        raise HTTPException(status_code=401, detail="邮箱或密码不对")
    return {"token": issue_token(row["id"], SECRET), "user": _user(row)}


@app.get("/me")
def me(authorization: str | None = Header(default=None)) -> dict[str, object]:
    user_id = _bearer(authorization)
    row = db.execute("SELECT * FROM account WHERE id = ?", (user_id,)).fetchone()
    return {"user": _user(row)}


def main() -> None:
    import uvicorn

    uvicorn.run("auth.main:app", host="127.0.0.1", port=8787, reload=False)


if __name__ == "__main__":
    main()
