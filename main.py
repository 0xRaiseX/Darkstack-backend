from datetime import datetime, timedelta
import random
import os
import time
from fastapi import FastAPI, Request, Form, Depends, Response, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import httpx
from passlib.hash import bcrypt
from pymongo import MongoClient
from itsdangerous import BadSignature, URLSafeSerializer
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
SALT = os.getenv("SALT")
DB_NAME = os.getenv("DB_NAME")
SECRET_KEY = os.getenv("SECRET_KEY")
COOKIE_NAME = os.getenv("COOKIE_NAME", "session")

app = FastAPI()

origins = [
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = MongoClient(MONGO_URL)
db = client[DB_NAME]
users_collection = db["users"]
codes_collection = db["codes"]
deployments_collection = db["deployments"]


serializer = URLSafeSerializer(SECRET_KEY)

def get_current_user(request: Request):
    session_cookie = request.cookies.get(COOKIE_NAME)
    if not session_cookie:
        return None
    try:
        user_email = serializer.loads(session_cookie)
        return users_collection.find_one({"email": user_email})
    except Exception:
        return None

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=FileResponse)
async def get_main_page():
    return "static/index.html"

@app.get("/login", response_class=FileResponse)
async def get_login_page(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url='/dashboard', status_code=302)
    return "static/login.html"

@app.get("/reset", response_class=FileResponse)
async def get_reset_page(request: Request):
    return "static/reset.html"

@app.get("/verify", response_class=FileResponse)
async def get_verify_page(request: Request):
    return "static/verify.html"

@app.get("/data_policy", response_class=FileResponse)
async def get_data_policy_page(request: Request):
    return "static/data_policy.html"

@app.get("/user_agreement", response_class=FileResponse)
async def get_user_agreement_page(request: Request):
    return "static/user_agreement.html"

@app.get("/reset-password", response_class=FileResponse)
async def get_reset_password_page(request: Request):
    return "static/new_password.html"

@app.get("/register", response_class=FileResponse)
async def get_register_page(request: Request):
    return "static/register.html"

@app.get("/dashboard", response_class=FileResponse)
async def get_dashboard_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url='/login', status_code=302)
    return "static/dashboard.html"

@app.get("/dashboard_newservice", response_class=FileResponse)
async def get_dashboard_newservice_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url='/login', status_code=302)
    return "static/dashboard_newservice.html"


# === API ===

class RegisterData(BaseModel):
    email: str
    password: str

@app.post("/api/register")
def register(data: RegisterData, response: Response):
    if users_collection.find_one({"email": data.email}):
        raise HTTPException(status_code=400, detail="Пользователь уже существует")
    hashed_password = bcrypt.hash(data.password)
    subdomain = generate_subdomain(data.email, str(time.time() * 1000), SALT)
    users_collection.insert_one({"email": data.email, "password": hashed_password, "subdomain": subdomain})

    # Сразу логиним
    session_token = serializer.dumps(data.email)
    response = JSONResponse(content={"status": "ok"}, status_code=200)
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="strict",  # или "lax" если нужно для разных портов
    )
    return response

class LoginData(BaseModel):
    email: str
    password: str

@app.post("/api/login")
def login(data: LoginData):
    user = users_collection.find_one({"email": data.email})
    if not user or not bcrypt.verify(data.password, user["password"]):
        return JSONResponse(content={"status": "error", "message": "Неверные данные"}, status_code=401)

    session_token = serializer.dumps(data.email)

    response = JSONResponse(content={"status": "ok"}, status_code=200)
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="strict",  # или "lax" если нужно для разных портов
    )
    return response

@app.get("/logout")
def logout(response: Response):
    response = RedirectResponse(url='/', status_code=302)
    response.delete_cookie(COOKIE_NAME)

    return response

@app.get("/api/me")
def me_api(request: Request):
    user = get_current_user(request)
    if not user:
        return JSONResponse(content={"status": "unauthorized"}, status_code=401)
    return JSONResponse(content={"status": "ok", "email": user["email"]}, status_code=200)

@app.post("/api/request-reset")
async def request_reset(email: str = Form(...)):
    user = users_collection.find_one({"email": email})
    if not user:
        return JSONResponse(content={"status": "error", "message": "Такой email не зарегистрирован"}, status_code=401)
    
    code = str(random.randint(100000, 999999))
    codes_collection.insert_one({
        "email": email,
        "code": code,
        "created_at": datetime.utcnow(),
        "used": False
    })
    print(f"[DEBUG] Код {code} отправлен на {email}")
    # return RedirectResponse(url=f'/verify?email={email}', status_code=302)
    return JSONResponse(content={"status": "ok"}, status_code=200)

@app.post("/api/verify-code")
async def verify_code(email: str = Form(...), code: str = Form(...)):
    record = codes_collection.find_one({"email": email, "code": code, "used": False})
    print(email, code, record)
    if not record:
        return JSONResponse(content={"status": "invalid_code"}, status_code=400)
    if datetime.utcnow() - record["created_at"] > timedelta(minutes=10):
        return JSONResponse(content={"status": "expired"}, status_code=400)
    return JSONResponse(content={"status": "ok"}, status_code=200)

@app.post("/api/reset-password")
async def reset_password(email: str = Form(...), code: str = Form(...), new_password: str = Form(...)):
    print(email, code, new_password)
    record = codes_collection.find_one({"email": email, "code": code, "used": False})
    if not record:
        return JSONResponse(content={"status": "invalid_code"}, status_code=400)

    codes_collection.update_one({"_id": record["_id"]}, {"$set": {"used": True}})
    hashed_password = bcrypt.hash(new_password)
    users_collection.update_one({"email": email}, {"$set": {"password": hashed_password}})
    return JSONResponse(content={"status": "ok"}, status_code=200)


class PushServiceRequest(BaseModel):
    image: str

def get_current_user_email(request: Request) -> str:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        email = serializer.loads(token)
    except BadSignature:
        raise HTTPException(status_code=401, detail="Invalid session token")

    return email

@app.post("/api/push_service")
async def push_service(payload: PushServiceRequest, user_email: str = Depends(get_current_user_email)):
    k8s_manager_url = "http://k8s-manager-service.default.svc.cluster.local:80/manage-resources"
    count = deployments_collection.count_documents({"user_email": user_email})

    user = users_collection.find_one({"email": user_email})
    subdomain = user["subdomain"]

    data = {
        "user": subdomain,
        "image": payload.image,
        "action": "create",
        "order": count
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(k8s_manager_url, json=data)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"K8s manager error: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to contact k8s-manager: {str(e)}")

    deployments_collection.insert_one({
        "user_email": user_email,
        "namespace": subdomain,
        "image": payload.image,
        "deployment_name": payload.image.split(":")[0] + "-deployment",
        "created_at": datetime.utcnow(),
        "status": "requested"
    })

    return {"message": "Service deployment requested", "k8s_response": response.json()}

@app.post("/api/delete_service")
async def delete_service(payload: PushServiceRequest, user_email: str = Depends(get_current_user_email)):
    user_namespace = user_email.replace("@", "-").replace(".", "-")
    k8s_manager_url = "http://k8s-manager-service.default.svc.cluster.local:80/manage-resources"

    data = {
        "user": user_namespace, 
        "image": "",
        "action": "delete"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(k8s_manager_url, json=data)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"K8s manager error: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to contact k8s-manager: {str(e)}")

    return {"message": "All resources has been deleted", "k8s_response": response.json()}

class DeploymentInfo(BaseModel):
    user_email: str
    namespace: str
    image: str
    deployment_name: str
    created_at: datetime
    status: str

@app.get("/api/deployments/by-user", response_model=List[DeploymentInfo])
def get_deployments_by_user(user_email: str = Query(..., description="Email пользователя")):
    try:
        deployments_cursor = deployments_collection.find(
            {"user_email": user_email},
            {"_id": 0} 
        )
        deployments = list(deployments_cursor)
        return deployments
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve deployments: {str(e)}")

import hashlib

def generate_subdomain(email: str, timestamp: str, salt: str, rounds: int = 1) -> str:
    data = f"{email}:{timestamp}:{salt}".encode()
    for _ in range(rounds):
        data = hashlib.sha256(data).digest()  # или .hexdigest().encode() — в зависимости от длины
    return f"u-{data.hex()[:8]}"


"""
{
  "user_email": "example@example.com",
  "namespace": "example-example-com",
  "image": "nginx:latest",
  "deployment_name": "nginx-deployment",
  "created_at": "2025-06-13T12:00:00Z",
  "status": "running"  // или "pending", "failed"
}
"""