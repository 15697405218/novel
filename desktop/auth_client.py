import httpx


class AuthError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return "账号服务没有响应"
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, str):
        return detail
    return "账号服务没有响应"


def register(base: str, email: str, name: str, password: str) -> dict:
    response = httpx.post(
        f"{base.rstrip('/')}/register",
        json={"email": email, "name": name, "password": password},
        timeout=20,
    )
    if response.status_code >= 400:
        raise AuthError(_detail(response))
    return response.json()


def login(base: str, email: str, password: str) -> dict:
    response = httpx.post(
        f"{base.rstrip('/')}/login",
        json={"email": email, "password": password},
        timeout=20,
    )
    if response.status_code >= 400:
        raise AuthError(_detail(response))
    return response.json()


def me(base: str, token: str) -> dict | None:
    response = httpx.get(
        f"{base.rstrip('/')}/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if response.status_code == 401:
        return None
    if response.status_code >= 400:
        raise AuthError(_detail(response))
    return response.json()
