import os
import sqlite3
import time
from pathlib import Path
from typing import Any

import jwt
from quart import Blueprint, current_app, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


local_auth_bp = Blueprint("local_auth", __name__)


def _get_db_path() -> Path:
    data_dir = Path(__file__).resolve().parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "users.db"


def _ensure_db():
    db_path = _get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.commit()


@local_auth_bp.post("/auth/register")
async def register():
    payload = await request.get_json()
    if not payload or "email" not in payload or "password" not in payload:
        return jsonify({"error": "email and password are required"}), 400

    email = str(payload["email"]).strip().lower()
    password = str(payload["password"]).strip()
    if len(email) == 0 or len(password) < 6:
        return jsonify({"error": "invalid email or password too short"}), 400

    _ensure_db()
    db_path = _get_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (email, generate_password_hash(password), int(time.time())),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "email already registered"}), 409

    return jsonify({"message": "registered"}), 201


@local_auth_bp.post("/auth/login")
async def login():
    payload = await request.get_json()
    if not payload or "email" not in payload or "password" not in payload:
        return jsonify({"error": "email and password are required"}), 400

    email = str(payload["email"]).strip().lower()
    password = str(payload["password"]).strip()

    _ensure_db()
    db_path = _get_db_path()
    user: dict[str, Any] | None = None
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            user = dict(row)

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401

    secret = os.getenv("LOCAL_JWT_SECRET", "dev-insecure-change-me")
    token = jwt.encode({"sub": user["email"], "iat": int(time.time())}, secret, algorithm="HS256")
    return jsonify({"token": token, "email": user["email"]}), 200


