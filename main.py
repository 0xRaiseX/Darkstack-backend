from datetime import datetime, timedelta
import random
import os
import time
from fastapi import FastAPI, Query, Request, Form, Depends, Response, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import httpx
from passlib.hash import bcrypt as bcrypt_v
from itsdangerous import BadSignature, URLSafeSerializer
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List
from datetime import datetime, timezone
import hashlib
import secrets
from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt
import re

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
SALT = os.getenv("SALT")
DB_NAME = os.getenv("DB_NAME")
SECRET_KEY = os.getenv("SECRET_KEY")
COOKIE_NAME = os.getenv("COOKIE_NAME", "session")
BILLING_INTERVAL = timedelta(minutes=60)
BILLING_COST = 10.0

if DB_NAME is None:
    raise ValueError("DB_NAME environment variable is not set.")

if SECRET_KEY is None:
    raise ValueError("SECRET_KEY environment variable is not set.")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
users_collection = db["users"]
codes_collection = db["codes"]
deployments_collection = db["deployments"]

serializer = URLSafeSerializer(SECRET_KEY)

# === Tarifs ===
tarifs = {
    "mini": {
        "hourPrice": 0.104,
        "monthPrice": 75,
        "CPU": 0.2,
        "RAM": 256,
    },
    "standart": {
        "hourPrice": 0.15,
        "monthPrice": 105,
        "CPU": 0.5,
        "RAM": 512,
    },
    "hard": {
        "hourPrice": 0.21,
        "monthPrice": 150,
        "CPU": 1,
        "RAM": 1024
    },
    "premium": {
        "hourPrice": 0.42,
        "monthPrice": 300,
        "CPU": 2,
        "RAM": 2048
    }
}

tarifs_db = {
    "mini": {
        "hourPrice": 0.25,
        "monthPrice": 180,
        "CPU": 1,
        "RAM": 1024,
    },
    "standart": {
        "hourPrice": 0.42,
        "monthPrice": 300,
        "CPU": 2,
        "RAM": 2048,
    },
    "hard": {
        "hourPrice": 0.81,
        "monthPrice": 580,
        "CPU": 4,
        "RAM": 4096
    },
    "premium": {
        "hourPrice": 1.25,
        "monthPrice": 900,
        "CPU": 6,
        "RAM": 6144
    }
}


# === START ===

app = FastAPI()

### СДЖЕЛАТЬ ОТПРАВВКУ УВЕДОМЛЕНИЙ НА ПОЧТУ

# ИСПРАВИТЬ БАГ ПРИ ОБНОВЛЕНИИ МАРШРУТА НЕ ВЫДАЕТСЯ ИНФО БЕЗ ОБНОВЛЕНИЯ СТРАНЦИЫ
# ПРИ ОБНОВЛЕНИИ ПОЛЬЗВОАТЕЛСЬКОГ ОМАРШРУТА ОСТАЕТСЯ ПЕРВИЧНЫЙ МРАШЩРУТ ДЯЛ БАЗЫ ДАННЫХ
# Добавить autoscalling
# Добавить правильное обновление сервисов

# === GET ===  

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=FileResponse)
async def get_main_page():
    return "static/index.html"

@app.get("/login", response_class=FileResponse)
async def get_login_page(request: Request):
    user = await get_current_user(request)
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
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url='/login', status_code=302)
    return "static/dashboard.html"

@app.get("/dashboard/newservice", response_class=FileResponse)
async def get_dashboard_newservice_page(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url='/login', status_code=302)
    return "static/dashboard_newservice.html"

@app.get("/dashboard/settings", response_class=FileResponse)
async def get_dashboard_settings(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url='/login', status_code=302)
    return "static/dashboard_settings.html"

@app.get("/dashboard/finance", response_class=FileResponse)
async def get_dashboard_finance(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url='/login', status_code=302)
    return "static/dashboard_finance.html"

@app.get("/dashboard/logs", response_class=FileResponse)
async def get_dashboard_logs(request: Request):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse(url='/login', status_code=302)
    return "static/dashboard_logs.html"


# === Helper Functions ===

async def get_current_user(request: Request):
    session_cookie = request.cookies.get(COOKIE_NAME)
    if not session_cookie:
        return None
    try:
        user_email = serializer.loads(session_cookie)
        return await users_collection.find_one({"email": user_email})
    except Exception:
        return None

def get_current_user_email(request: Request) -> str:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        email = serializer.loads(token)
    except BadSignature:
        raise HTTPException(status_code=401, detail="Invalid session token")

    return email

async def find_missing_order(user_email):
    count = await deployments_collection.count_documents({
        "user_email": {
            "$exists": True,
            "$ne": None,
            "$ne": ""
        }
    })

    if count == 0:
        return 1
    
    orders = deployments_collection.find({"user_email": user_email}, {"order": 1, "_id": 0}).sort("order", 1)
    orders_list = [doc["order"] async for doc in orders]

    expected = 1
    for order in orders_list:
        if order != expected:
            return expected
        expected += 1
    
    return expected


async def check_user_deployment_name(user_email: str, deployment_name: str):
    exists = await deployments_collection.find_one({
        "user_email": user_email,
        "user_deployment_name": deployment_name
    })

    if exists:
        raise HTTPException(status_code=403, detail="Deployment name already exists")

async def check_domain(user_email, domain: str):
    user_deployments = deployments_collection.find({"user_email": user_email})

    async for deployment in user_deployments:
        if deployment.get("user_domain") == domain:
            return True

    return False

def generate_subdomain(email: str, timestamp: str, rounds: int = 1) -> str:
    salt = secrets.token_hex(32)
    data = f"{email}:{timestamp}:{salt}".encode()
    for _ in range(rounds):
        data = hashlib.sha256(data).digest()
    return f"u-{data.hex()[:8]}"

def delete_ingress_suffix(ingress_name: str) -> str:
    suffix = "-ingress"
    if ingress_name.endswith(suffix):
        return ingress_name[:-len(suffix)]
    return ingress_name

def build_domain(subdomain: str, order: int) -> str:
    return f"{subdomain}.darkstack.local/service{order}" if order > 1 else f"{subdomain}.darkstack.local"

def build_deployment_name(subdomain: str, order: int) -> str:
    return subdomain+f"-{order}"+"-app" if order > 1 else subdomain+"-app"

def build_db_name(db_type: str, order: int) -> str:
    return db_type+f"-{order}"+"-app"

async def deposit_balance(email: str, amount: int):
    if amount <= 0:
        raise ValueError("Сумма пополнения должна быть положительной")

    result = await users_collection.update_one(
        {"email": email},
        {
            "$inc": {"balance": amount},
            "$push": {
                "transactions": {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "type": "deposit",
                    "amount": amount
                }
            }
        }
    )

    if result.matched_count == 0:
        raise ValueError("Пользователь не найден")

    await continue_deployment_if_possible(email)

    return f"Баланс пополнен на {amount} ₽"


async def withdraw_balance(email: str, amount: int):
    if amount <= 0:
        raise ValueError("Сумма списания должна быть положительной")

    user = await users_collection.find_one({"email": email})
    if not user:
        raise ValueError("Пользователь не найден")

    if user["balance"] < amount:
        raise ValueError("Недостаточно средств для списания")

    await users_collection.update_one(
        {"email": email},
        {
            "$inc": {"balance": -amount},
            "$push": {
                "transactions": {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "type": "withdrawal",
                    "amount": amount
                }
            }
        }
    )

    return f"Списано {amount} ₽ с баланса"

def validate_k8s_name(name: str):
    """Проверка имени для Kubernetes (DNS-1035)."""
    if not (1 <= len(name) <= 63):
        raise HTTPException(status_code=422, detail="Имя должно быть от 1 до 63 символов.")
    
    pattern = r'^[a-z]([-a-z0-9]*[a-z0-9])?$'
    if not re.fullmatch(pattern, name):
        raise HTTPException(
            status_code=422,
            detail="Имя должно соответствовать формату DNS-1035: маленькие буквы, цифры или '-', начинаться с буквы и заканчиваться буквой или цифрой."
        )

def validate_domain(domain: str):
    """Простая проверка домена по структуре вида 'example.com'."""
    if not domain or len(domain) > 253:
        raise HTTPException(status_code=422, detail="Недопустимая длина домена.")

    domain_pattern = r'^(?=.{1,253}$)((?!-)[A-Za-z0-9-]{1,63}(?<!-)\.)+[A-Za-z]{2,}$'
    if not re.fullmatch(domain_pattern, domain):
        raise HTTPException(status_code=422, detail="Недопустимый домен. Убедитесь, что он записан корректно (например: example.com).")

# === Callbacks ===

async def on_rechange_balance():
    """
    Колбэк при обновлении баланса.
    Проверяет все сервисы для конкретного user_email или namespace 
    и запускает их работу
    """

# === Datas ===

class RegisterData(BaseModel):
    email: str
    password: str

class LoginData(BaseModel):
    email: str
    password: str

class PushServiceRequest(BaseModel):
    image: str
    port: int
    tarif: str

class CreateDatabaseRequest(BaseModel):
    db_type: str
    storage_size: str
    tarif: str

class DeleteServiceRequest(BaseModel):
    deployment_name: str

class DeploymentInfo(BaseModel):
    user_email: str
    subdomain: str
    image: str
    deployment_name: str
    user_deployment_name: str
    user_service_name: str
    domain: str
    user_domain: str
    tarif: str
    type: str
    lastTimePay: datetime
    created_at: datetime
    uptime_start: datetime
    status: str
    order: int

class ChangeDomain(BaseModel):
    deployment_name: str
    new_domain: str

class ChangeDeploymentName(BaseModel):
    deployment_name: str
    new_deployment_name: str

class DeleteDomainUser(BaseModel):
    deployment_name: str

class UserInfo(BaseModel):
    email: str
    subdomain: str
    update_password_time: datetime
    created_at: datetime
    name: str
    balance: int
    transactions: List

class NewDeploymentName(BaseModel):
    deployment_name_new: str

class ChangeUserName(BaseModel):
    new_name: str

class DepositRequest(BaseModel):
    amount: int

class RestartRequest(BaseModel):
    deployment_name: str

class LogsInfo(BaseModel):
    pod: str
    logs: list


# === API ===

@app.get("/logout")
async def logout():
    response = RedirectResponse(url='/', status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response

@app.get("/api/me")
async def me_api(request: Request):
    user = await get_current_user(request)
    if not user:
        return JSONResponse(content={"status": "unauthorized"}, status_code=401)
    return JSONResponse(content={"status": "ok", "email": user["email"]}, status_code=200)

@app.get("/api/deployments/by-user", response_model=List[DeploymentInfo])
async def get_deployments_by_user(user_email: str = Depends(get_current_user_email)):
    try:
        deployments_cursor = deployments_collection.find(
            {"user_email": user_email},
            {"_id": 0} 
        )
        deployments = await deployments_cursor.to_list(length=None)
        return deployments
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve deployments: {str(e)}")

@app.get("/api/get/user_data", response_model=UserInfo)
async def get_user_data(user_email: str = Depends(get_current_user_email)):
    try:
        user_data = await users_collection.find_one(
            {"email": user_email},
            {"_id": 0} 
        )
        if not user_data:
            raise HTTPException(status_code=404, detail="User data not found")
        return user_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve deployments: {str(e)}")

@app.get("/api/get/logs", response_model=LogsInfo)
async def get_logs(deployment_name: str = Query(...), user_email: str = Depends(get_current_user_email)):
    try:
        deployment = await deployments_collection.find_one(
            {
                "user_email": user_email,
                "deployment_name": deployment_name
            }
        )
        if not deployment:
            raise HTTPException(status_code=404, detail="Deployment not found for this user")

        k8s_manager_url = "http://k8s-manager-service.default.svc.cluster.local:80/get/logs"

        data = {
            "deployment_name": deployment['deployment_name'],
            "namespace": deployment['subdomain'],
            "tail_lines": 100,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(k8s_manager_url, json=data)
                response.raise_for_status()
                data_response = response.json()
        except httpx.HTTPStatusError as e:
            # Выводим json-ошибку, если доступна
            try:
                error_data = e.response.json()
            except Exception:
                error_data = {"error": e.response.text}
            print(error_data)

            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"K8s manager error: {error_data}"
            )

        return data_response
    
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")


@app.get("/api/get/new_deployment_name", response_model=NewDeploymentName)
async def get_new_deployment_name(user_email: str = Depends(get_current_user_email)):
    try:
        user_data = await users_collection.find_one(
            {"email": user_email},
            {"_id": 0} 
        )

        if not user_data:
            raise HTTPException(status_code=404, detail="User data not found")
        subdomain = user_data.get("subdomain")
        order = await find_missing_order(user_email)
        response_data = {
            "deployment_name_new": subdomain+"-"+str(order)
        }
        return response_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve deployments: {str(e)}")

@app.post("/api/register")
async def register(data: RegisterData, response: Response):
    existing_user = await users_collection.find_one({"email": data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    hashed_password = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()

    subdomain = generate_subdomain(data.email, str(int(time.time() * 1000)))
    time_create_account = datetime.now(timezone.utc).isoformat()

    existing_subdomain = await users_collection.find_one({"subdomain": subdomain})
    if existing_subdomain:
        raise HTTPException(status_code=400, detail="Поддомен уже существует")
    
    await users_collection.insert_one({
        "subdomain": subdomain,
        "email": data.email,
        "balance": 0,
        "totalHourPay": 0,
        "password": hashed_password,
        "update_password_time": time_create_account,
        "created_at": time_create_account,
        "name": "",
        "transactions": []
    })

    session_token = serializer.dumps(data.email)

    response = JSONResponse(content={"status": "ok"}, status_code=200)
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="strict",
    )
    return response 

@app.post("/api/login")
async def login(data: LoginData):
    user = await users_collection.find_one({"email": data.email})
    if not user or not bcrypt_v.verify(data.password, user["password"]):
        return JSONResponse(content={"status": "error", "message": "Неверные данные"}, status_code=401)

    session_token = serializer.dumps(data.email)

    response = JSONResponse(content={"status": "ok"}, status_code=200)
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="strict",
    )
    return response

@app.post("/api/request-reset")
async def request_reset(email: str = Form(...)):
    user = await users_collection.find_one({"email": email})
    if not user:
        return JSONResponse(content={"status": "error", "message": "Такой email не зарегистрирован"}, status_code=401)
    
    code = str(random.randint(100000, 999999))
    await codes_collection.insert_one({
        "email": email,
        "code": code,
        "created_at": datetime.utcnow(),
        "used": False
    })
    print(f"[DEBUG] Код {code} отправлен на {email}")
    return JSONResponse(content={"status": "ok"}, status_code=200)

@app.post("/api/verify-code")
async def verify_code(email: str = Form(...), code: str = Form(...)):
    record = await codes_collection.find_one({"email": email, "code": code, "used": False})
    print(email, code, record)
    if not record:
        return JSONResponse(content={"status": "invalid_code"}, status_code=400)
    if datetime.utcnow() - record["created_at"] > timedelta(minutes=10):
        return JSONResponse(content={"status": "expired"}, status_code=400)
    return JSONResponse(content={"status": "ok"}, status_code=200)

@app.post("/api/reset-password")
async def reset_password(email: str = Form(...), code: str = Form(...), new_password: str = Form(...)):
    print(email, code, new_password)
    record = await codes_collection.find_one({"email": email, "code": code, "used": False})
    if not record:
        return JSONResponse(content={"status": "invalid_code"}, status_code=400)

    await codes_collection.update_one({"_id": record["_id"]}, {"$set": {"used": True}})
    hashed_password = bcrypt_v.hash(new_password)
    time_update_password = datetime.now(timezone.utc).isoformat()
    await users_collection.update_one({"email": email}, {"$set": {"password": hashed_password, "update_password_time": time_update_password}})

    return JSONResponse(content={"status": "ok"}, status_code=200)

@app.post("/api/push_service")
async def push_service_request(payload: PushServiceRequest, user_email: str = Depends(get_current_user_email)):
    k8s_manager_url = "http://k8s-manager-service.default.svc.cluster.local:80/manage-resources"
    order = await find_missing_order(user_email)

    user = await users_collection.find_one({"email": user_email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    subdomain = user.get("subdomain")
    balance = user.get("balance", 0)

    domain = build_domain(subdomain, order)
    now = datetime.now(timezone.utc)

    if payload.tarif not in tarifs:
        raise HTTPException(status_code=403, detail=f"Invalid tarif: {payload.tarif}")

    if payload.port < 1 or payload.port > 65535:
        raise HTTPException(status_code=403, detail=f"Invalid port: {payload.port}")
    
    ########## ДОБАВИТЬ ПОДДЕРЖКУ STORAGE

    base_deployment_data = {
        "user_email": user_email,
        "subdomain": subdomain,
        "image": payload.image,
        "user_deployment_name": "",
        "user_domain": "",
        "tarif": payload.tarif,
        "port": payload.port,
        "type": "microservice",
        "user_service_name": "",
        "created_at": now,
        "lastTimePay": 0,
        "uptime_start": 0,
        "domain": domain,
        "order": order,
        "error": "",
    }

    hourRequired = user.get("hourPricePay", 0) + tarifs[payload.tarif]['hourPrice']

    if balance == 0 or balance < hourRequired:
        await deployments_collection.insert_one({
            **base_deployment_data,
            "deployment_name": build_deployment_name(subdomain, order),
            "service_name": "",
            "user_service_name": "",
            "ingress_name": "",
            "status": "waitToPay"
        })
        return {"message": "Service waiting for payment"}

    data = {
        "user": subdomain,
        "image": payload.image,
        "tarif": payload.tarif,
        "port": payload.port,
        "action": "create",
        "order": order,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(k8s_manager_url, json=data)
            response.raise_for_status()
            data_response = response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"K8s manager error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to contact k8s-manager: {str(e)}")

    await deployments_collection.insert_one({
        **base_deployment_data,
        "uptime_start": now,
        "lastTimePay": now,
        "deployment_name": data_response['deployment']['name'],
        "service_name": data_response['service']['name'],
        "ingress_name": data_response['ingress']['name'],
        "status": "requested"
    })

    await users_collection.update_one(
        {"email": user_email},
        {"$inc": {"totalHourPay": tarifs[payload.tarif]['hourPrice']}}
    )

    data_request = {
        "subdomain": subdomain,
        "message": f"Сервис {data_response['deployment']['name']} успешно создан."
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post("http://aiogram-service:80/send", json=data_request)
            response.raise_for_status()
            data_response = response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Aiogram manager error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to contact aiogram: {str(e)}")

    return {"message": "Service deployment requested", "k8s_response": data_response}

async def continue_deployment_if_possible(user_email: str):
    user = await users_collection.find_one({"email": user_email})
    if not user:
        return

    balance = user.get("balance", 0)
    if balance <= 0:
        return

    pending = await deployments_collection.find_one({
        "user_email": user_email,
        "status": "waitToPay"
    })

    if not pending:
        return

    tarif = pending['tarif']
    if tarif not in tarifs:
        return

    now = datetime.now(timezone.utc)

    if pending['deployment_name']:
        k8s_manager_url = "http://k8s-manager-service.default.svc.cluster.local:80/set/scale"
                    
        data = {
            "namespace": pending['subdomain'],
            "deployment_name": pending['deployment_name'],
            "replicas": 1,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(k8s_manager_url, json=data)
            response.raise_for_status()
            data_response = response.json()

            if response.status_code != 200:
                print(f"WARN! K8s manager error response: {data_response}")

        await deployments_collection.update_one(
            {"_id": pending['_id']},
            {"$set": {
                "lastTimePay": now,
                "uptime_start": now
            }}
        )
    else:
        data = {
            "user": pending['subdomain'],
            "image": pending['image'],
            "tarif": tarif,
            "port": pending['port'],
            "action": "create",
            "order": pending['order'],
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post("http://k8s-manager-service.default.svc.cluster.local:80/manage-resources", json=data)
                response.raise_for_status()
                data_response = response.json()

            await deployments_collection.update_one(
                {"_id": pending['_id']},
                {"$set": {
                    "deployment_name": data_response['deployment']['name'],
                    "service_name": data_response['service']['name'],
                    "ingress_name": data_response['ingress']['name'],
                    "status": "requested",
                    "lastTimePay": now,
                    "uptime_start": now
                }}
            )

            await users_collection.update_one(
                {"email": user_email},
                {"$inc": {"totalHourPay": tarifs[tarif]['hourPrice']}}
            )

        except Exception as e:
            print(f"Deployment failed after payment: {e}")


@app.post("/api/delete_service")
async def delete_service(payload: DeleteServiceRequest, user_email: str = Depends(get_current_user_email)):
    k8s_manager_url = "http://k8s-manager-service.default.svc.cluster.local:80/delete-resources"

    if not payload.deployment_name.endswith("-app"):
        raise HTTPException(status_code=400, detail="Invalid deployment name format")

    user_from_name = payload.deployment_name.removesuffix("-app")
        
    deployment_record = await deployments_collection.find_one({
        "user_email": user_email,
        "deployment_name": payload.deployment_name
    })

    if not deployment_record:
        raise HTTPException(status_code=404, detail="Deployment not found")

    subdomain = deployment_record.get("subdomain")
    if not subdomain:
        raise HTTPException(status_code=500, detail="Subdomain not found in deployment record")

    data = {
        "user": user_from_name,
        "namespace": subdomain,
        "action": "delete",
        "user_service_name": deployment_record.get("user_service_name", ""),
        "user_ingress_name": deployment_record.get("user_ingress_name", ""),
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(k8s_manager_url, json=data)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"K8s manager error: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to contact k8s-manager: {str(e)}")

     # Удаляем запись из базы после успешного удаления в Kubernetes
    result = await deployments_collection.delete_one({
        "user_email": user_email,
        "deployment_name": payload.deployment_name
    })

    if result.deleted_count == 0:
        raise HTTPException(status_code=500, detail="Failed to delete deployment record from database")

    return {
        "message": "All resources have been deleted and record removed from database",
        "k8s_response": response.json()
    }

@app.post("/api/change/deployment_name")
async def change_deployment_name_user(data: ChangeDeploymentName, user_email: str = Depends(get_current_user_email)):
    k8s_manager_url = "http://k8s-manager-service.default.svc.cluster.local:80/set/custom/service"
    try: 
        deployment = await deployments_collection.find_one(
            {
                "user_email": user_email,
                "deployment_name": data.deployment_name
            }
        )

        if not deployment:
            raise HTTPException(status_code=404, detail=f"Deployment name not found")

        if deployment.get("status") != "running":
            raise HTTPException(status_code=403, detail=f"Service not started")

        await check_user_deployment_name(user_email, data.new_deployment_name)
        validate_k8s_name(data.new_deployment_name)

        if deployment.get("user_service_name") == "":
            new_flag = True
        else:
            new_flag = False
        
        request_data = {
            "namespace": deployment.get("subdomain"),
            "service_name": data.new_deployment_name,
            "port": deployment.get("port"),
            "deployment_name": deployment.get("deployment_name"),
            "new": new_flag,
            "old_name":  deployment.get("user_service_name"),
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(k8s_manager_url, json=request_data)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise HTTPException(status_code=e.response.status_code, detail=f"K8s manager error: {e.response.text}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to contact k8s-manager: {str(e)}")


        result = await deployments_collection.update_one(
            {
                "user_email": user_email,
                "deployment_name": data.deployment_name
            },
            {
                "$set": {
                    "user_deployment_name": data.new_deployment_name,
                    "user_service_name": data.new_deployment_name
                }
            }
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Deployment not found for this user")
        
        return {"message": "Deployment name updated successfully"}
    
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update deployment name: {str(e)}")



@app.post("/api/change/domain")
async def change_domain_user(data: ChangeDomain, user_email: str = Depends(get_current_user_email)):
    k8s_manager_url = "http://k8s-manager-service.default.svc.cluster.local:80/manage-ingress"
    try:
        deployment_db = await deployments_collection.find_one(
            {
                "user_email": user_email,
                "deployment_name": data.deployment_name
            },
            {"_id": 0} 
        )

        if deployment_db and deployment_db.get('user_domain') == "":
            if await check_domain(user_email, data.new_domain):
                raise HTTPException(status_code=403, detail=f"Domain already exists")
        
            validate_domain(data.new_domain)

            request_data = {
                "user": delete_ingress_suffix(deployment_db.get("ingress_name")),
                "namespace": deployment_db.get("subdomain"),
                "host": data.new_domain,
                "action": "create",
                "order": deployment_db.get("order")
            }
                
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(k8s_manager_url, json=request_data)
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    raise HTTPException(status_code=e.response.status_code, detail=f"K8s manager error: {e.response.text}")
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to contact k8s-manager: {str(e)}")
                
        elif deployment_db and deployment_db.get('user_domain') != "":
            if await check_domain(user_email, data.new_domain):
                raise HTTPException(status_code=403, detail=f"Domain already exists")
        
            validate_domain(data.new_domain)

            request_data = {
                "user": delete_ingress_suffix(deployment_db.get("ingress_name")),
                "namespace": deployment_db.get("subdomain"),
                "host": data.new_domain,
                "action": "update",
                "order": 0
            }
                
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(k8s_manager_url, json=request_data)
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    raise HTTPException(status_code=e.response.status_code, detail=f"K8s manager error: {e.response.text}")
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to contact k8s-manager: {str(e)}")
        else:
            raise HTTPException(status_code=404, detail=f"User not found")
        
        await deployments_collection.update_one(
            {
                "user_email": user_email,
                "deployment_name": data.deployment_name
            },
            {
                "$set": {
                    "user_domain": data.new_domain
                }
            }
        )
            
        return {"message": "User domain updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user domain: {str(e)}")



@app.post("/api/delete/domain")
async def delete_domain_user(data: DeleteDomainUser, user_email: str = Depends(get_current_user_email)):
    k8s_manager_url = "http://k8s-manager-service.default.svc.cluster.local:80/manage-ingress"
    try:
        deployment_db = await deployments_collection.find_one(
            {
                "user_email": user_email,
                "deployment_name": data.deployment_name
            },
            {"_id": 0} 
        )

        if deployment_db and deployment_db.get('user_domain') == "":
           raise HTTPException(status_code=404, detail=f"User domain not found.")
        elif deployment_db:
            request_data = {
                "user": delete_ingress_suffix(deployment_db.get("ingress_name")),
                "namespace": deployment_db.get("namespace"),
                "host": "",
                "action": "delete",
                "order": 0
            }
                
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(k8s_manager_url, json=request_data)
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    raise HTTPException(status_code=e.response.status_code, detail=f"K8s manager error: {e.response.text}")
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to contact k8s-manager: {str(e)}")
        else:
            raise HTTPException(status_code=404, detail=f"User not found")
        
        await deployments_collection.update_one(
            {
                "user_email": user_email,
                "deployment_name": data.deployment_name
            },
            {
                "$set": {
                    "user_domain": ""
                }
            }
        )
            
        return {"message": "User domain deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user domain: {str(e)}")



@app.post("/api/change/user_name")
async def change_user_name(data: ChangeUserName, user_email: str = Depends(get_current_user_email)):
    try:
        result = await users_collection.update_one(
            {
                "email": user_email,
            },
            {
                "$set": {
                    "name": data.new_name
                }
            }
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User data not found for this user")
        return {"message": "User name updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user domain: {str(e)}")


@app.post("/api/create/database")
async def create_database_request(payload: CreateDatabaseRequest, user_email: str = Depends(get_current_user_email)):
    k8s_manager_url = "http://k8s-manager-service.default.svc.cluster.local:80/create/database"
    order = await find_missing_order(user_email)

    user = await users_collection.find_one({"email": user_email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    subdomain = user.get("subdomain")
    balance = user.get("balance", 0)

    domain = build_domain(subdomain, order)
    now = datetime.now(timezone.utc)

    if payload.tarif not in tarifs_db:
        raise HTTPException(status_code=403, detail=f"Invalid tarif: {payload.tarif}")

    base_deployment_data = {
        "user_email": user_email,
        "subdomain": subdomain,
        "image": "", # -
        "user_deployment_name": "",
        "user_domain": "", # -
        "tarif": payload.tarif,
        "port": 0, # -
        "type": "database",
        "user_service_name": "",
        "created_at": now,
        "lastTimePay": 0,
        "uptime_start": 0,
        "domain": domain, # только для тестов с другим протоклом доступа (сделать возможность отключить)
        "order": order, 
        "error": "",
    }

    hourRequired = user.get("hourPricePay", 0) + tarifs_db[payload.tarif]['hourPrice']

    if balance == 0 or balance < hourRequired:
        await deployments_collection.insert_one({
            **base_deployment_data,
            "deployment_name": build_db_name(payload.db_type, order),
            "service_name": "", 
            "user_service_name": "",
            "ingress_name": "", 
            "status": "waitToPay"
        })
        return {"message": "Service waiting for payment"}

    data = {
        "namespace": subdomain,
        "db_type": payload.db_type,
        "storage_size": payload.storage_size,
        "order": order,
        "action": "create",
        "tarif": payload.tarif,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(k8s_manager_url, json=data)
            response.raise_for_status()
            data_response = response.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"K8s manager error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to contact k8s-manager: {str(e)}")

    await deployments_collection.insert_one({
        **base_deployment_data,
        "uptime_start": now,
        "lastTimePay": now,
        "deployment_name": build_db_name(payload.db_type, order),
        "service_name": data_response['service'],
        "ingress_name": data_response['pvc'],
        "status": "requested"
    })

    await users_collection.update_one(
        {"email": user_email},
        {"$inc": {"totalHourPay": tarifs_db[payload.tarif]['hourPrice']}}
    )

    return {"message": "Database deployment requested", "k8s_response": data_response}

@app.post("/api/deployment/restart")
async def restart_request(data: RestartRequest, user_email: str = Depends(get_current_user_email)):
    k8s_manager_url = "http://k8s-manager-service.default.svc.cluster.local:80/restart"
    try:
        deployment = await deployments_collection.find_one(
            {
                "user_email": user_email,
                "deployment_name": data.deployment_name,
            },
        )

        if not deployment:
            raise HTTPException(status_code=404, detail="Service not found")

        data_request = {
            "namespace": deployment.get("subdomain"),
            "deployment_name": deployment.get("deployment_name"),
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(k8s_manager_url, json=data_request)
                response.raise_for_status()
                data_response = response.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"K8s manager error: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to contact k8s-manager: {str(e)}")

        now = datetime.now(timezone.utc)

        await deployments_collection.update_one(
            {
                "user_email": user_email,
                "deployment_name": data.deployment_name,
            },
            {
                "$set": {
                    "uptime_start": now,
                }
            }
        )
        
        return data_response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user domain: {str(e)}")


@app.post("/api/deposit")
async def deposit_request(request: DepositRequest, user_email: str = Depends(get_current_user_email)):
    await deposit_balance(user_email, request.amount)
    return JSONResponse(content={"status": "ok"}, status_code=200)

@app.post("/api/withdrawal")
async def withdrawal_request(request: DepositRequest, user_email: str = Depends(get_current_user_email)):
    await withdraw_balance(user_email, request.amount)
    return JSONResponse(content={"status": "ok"}, status_code=200)


""" Routes
GET
/logout
/api/me
/api/deployments/by-user
/api/get/user_data

POST
/api/register
/api/login

/api/request-reset
/api/verify-code
/api/reset-password

/api/push_service

/api/change/deployment_name
/api/change/domain
/api/change/user_name

/api/delete/domain
/api/delete_service
"""

""" Deployments Colletion
{
  "user_email": "example@example.com",              - почта пользователя (уникальная)
  "subdomain": "u-xxxxxxxx",                        - поддомен пользователя (уникальный)
  "image": "nginx:latest",                          - образ контейнера
  "deployment_name": "u-xxxxxxxx-n-app",            - имя Deployment манифеста
  "user_deployment_name": "",                       - имя D..t для отображения в таблице (не имеет отношения к кластеру)
  "service_name": "u-xxxxxxxx-n",                   - имя Service манифеста
  "user_service_name": user_deployment_name,        - кастомное имя Service манифеста (второй внутренний маршрут, удобный для пользователя) 
  "ingress_name": "u-xxxxxxxx-n-ingress",           - имя Ingress манифеста
  "user_ingress_name": "u-xxxxxxxx-n-ingress-user", - имя Ingress манифеста с маршрутом пользователя (кастомный внешний доступ)
  "domain": "u-xxxxxxxx.darkstack.local",           - поддомен на основной маршрут (внешний доступ)
  "user_domain": "my.supersite.com",                - привязанный домен пользователя (yaml файл - user_ingress_name)
  "tarif": "normal",                                - тариф сервиса (mini, standard, hard, premium)
  "port": 1-65535,                                  - порт, на котором работает контейнер
  "type": "microservice"/"database"
  "lastTimePay": "",                                - время последнего списания оплаты
  "created_at": "2025-06-13T12:00:00Z",             - время создания сервиса
  "uptime_start": 0,                                - время старта сервиса (сбрасывается при рестарте)
  "status": "running"  // или "pending", "failed",  - статус сервиса
  "order": 1,                                       - количество в рамках одного пользователя
}
"""

""" Users Collection
{
  "subdomain": "u-xxxxxxxx",
  "email": "easada@emasi.pt",
  "balance": 0,
  "totalHourPay": 0,
  "typeMessage": "tg"/"email",
  "password": "sdgsdgsdgsdgsdg",
  "update_password_time": "2025-06-13T12:00:00Z",
  "created_at": "2025-06-13T12:00:00Z",
  "name": "",
  "transactions": [
        {
        "date": "2025-06-12",
        "type: "deposit"/"withdrawal"
        "amount: "100"
        }
    ]
}
"""