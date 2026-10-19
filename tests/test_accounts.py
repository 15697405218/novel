import unittest
import uuid

from fastapi.testclient import TestClient

from auth.main import app


class Accounts(unittest.TestCase):
    def test_register_login_and_me(self) -> None:
        client = TestClient(app)
        email = f"{uuid.uuid4().hex[:8]}@example.com"
        created = client.post(
            "/register",
            json={"email": email, "name": "甲", "password": "12345678"},
        )
        self.assertEqual(created.status_code, 200)
        token = created.json()["token"]
        me = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["user"]["email"], email)
        again = client.post("/login", json={"email": email, "password": "wrong-pass"})
        self.assertEqual(again.status_code, 401)
        logged = client.post("/login", json={"email": email, "password": "12345678"})
        self.assertEqual(logged.status_code, 200)
        duplicate = client.post(
            "/register",
            json={"email": email, "name": "甲", "password": "12345678"},
        )
        self.assertEqual(duplicate.status_code, 409)


if __name__ == "__main__":
    unittest.main()
