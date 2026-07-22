import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os

# Adjust sys path so we can import backend packages
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app
from backend.database.db import Base, get_db
from backend.database import models

# In-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override database dependency
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_signup():
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "password": "password123", "full_name": "Test User"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data
    assert data["role"] == "admin" # First user is admin

def test_login():
    # Sign up
    client.post(
        "/api/v1/auth/signup",
        json={"email": "login@example.com", "password": "password123", "full_name": "Login User"}
    )
    
    # Login
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "password123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["email"] == "login@example.com"
    assert data["full_name"] == "Login User"

def test_get_profile():
    # Sign up
    client.post(
        "/api/v1/auth/signup",
        json={"email": "profile@example.com", "password": "password123", "full_name": "Profile User"}
    )
    
    # Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "profile@example.com", "password": "password123"}
    )
    token = login_resp.json()["access_token"]
    
    # Fetch profile
    response = client.get(
        "/api/v1/auth/profile",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "profile@example.com"
    assert data["full_name"] == "Profile User"
