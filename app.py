import os
import subprocess
import signal
import threading
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from contextlib import asynccontextmanager
from a2wsgi import ASGIMiddleware
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from crypto_tracker import run_bot

load_dotenv()

# Initialize Firebase
try:
    if not firebase_admin._apps:
        # Load credentials from the service_account.json file
        cred = credentials.Certificate('service_account.json')
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase (Firestore) initialized with service account key.")
except Exception as e:
    print(f"Firebase initialization failed: {e}")
    db = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic: Auto-start crypto bot in cloud environment
    if os.getenv("AUTO_START_CRYPTO", "true").lower() == "true":
        print("Starting Crypto Tracker (Auto-start enabled)...")
        interval = os.getenv("CRYPTO_INTERVAL", "1h")
        coins = os.getenv("CRYPTO_COINS", "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,DOGEUSDT").split(",")
        try:
            thread = threading.Thread(target=run_bot, args=(interval, coins), daemon=True)
            thread.start()
            threads["crypto"] = thread
        except Exception as e:
            print(f"Failed to auto-start crypto tracker: {e}")
    
    yield
    
    # Shutdown logic
    print("Shutting down... (Threads will terminate as they are daemons)")

app = FastAPI(title="AI Bot Interface", lifespan=lifespan)

# Required for PythonAnywhere WSGI hosting
application = ASGIMiddleware(app)

# Store running threads and processes
processes = {
    "nepse": None
}
threads = {
    "crypto": None
}
logs_buffer = {
    "nepse": [],
    "crypto": []
}

def capture_logs(bot_type, proc):
    """Background task to read process output and sync to Firestore."""
    for line in iter(proc.stdout.readline, ""):
        if line:
            clean_line = line.strip()
            logs_buffer[bot_type].append(clean_line)
            
            # Sync to Firestore if available
            if db:
                try:
                    # Append log to a collection 'logs' with document as bot_type
                    # We store logs as an array for simplicity in this example
                    doc_ref = db.collection("bot_logs").document(bot_type)
                    doc_ref.set({
                        "entries": firestore.ArrayUnion([clean_line]),
                        "last_updated": firestore.SERVER_TIMESTAMP
                    }, merge=True)
                except Exception as e:
                    print(f"Error syncing log to Firestore: {e}")

            # Keep only last 100 lines in memory
            if len(logs_buffer[bot_type]) > 100:
                logs_buffer[bot_type].pop(0)
    proc.stdout.close()

class NepseConfig(BaseModel):
    stock_name: str
    target_qty: str
    target_price: str
    total_orders: int

class CryptoConfig(BaseModel):
    interval: str
    coins: List[str]

# Serve static files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.post("/run/nepse")
async def run_nepse(config: NepseConfig, background_tasks: BackgroundTasks):
    if processes["nepse"] and processes["nepse"].poll() is None:
        raise HTTPException(status_code=400, detail="NEPSE bot is already running")
    
    env = os.environ.copy()
    env["NEPSE_STOCK_NAME"] = config.stock_name
    env["NEPSE_TARGET_QTY"] = config.target_qty
    env["NEPSE_TARGET_PRICE"] = config.target_price
    env["NEPSE_TOTAL_ORDERS"] = str(config.total_orders)
    
    try:
        # Note: bot.py opens a visible browser window
        proc = subprocess.Popen(["python3", "bot.py"], env=env)
        processes["nepse"] = proc
        return {"message": "NEPSE bot started. Verify the manual browser window."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run/crypto")
async def run_crypto(config: CryptoConfig, background_tasks: BackgroundTasks):
    if threads["crypto"] and threads["crypto"].is_alive():
        raise HTTPException(status_code=400, detail="Crypto bot is already running")
    
    try:
        thread = threading.Thread(target=run_bot, args=(config.interval, config.coins), daemon=True)
        thread.start()
        threads["crypto"] = thread
        return {"message": f"Crypto bot started with interval {config.interval}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stop/{bot_type}")
async def stop_bot(bot_type: str):
    if bot_type not in processes:
        raise HTTPException(status_code=404, detail="Bot type not found")
    
    proc = processes[bot_type]
    if proc and proc.poll() is None:
        os.kill(proc.pid, signal.SIGTERM)
        processes[bot_type] = None
        return {"message": f"{bot_type.upper()} bot stopped"}
    
    return {"message": f"{bot_type.upper()} bot is not running"}

@app.get("/status")
async def get_status():
    return {
        "nepse": processes["nepse"].poll() is None if processes["nepse"] else False,
        "crypto": threads["crypto"].is_alive() if threads["crypto"] else False
    }

@app.get("/logs/{bot_type}")
async def get_logs(bot_type: str):
    if bot_type not in logs_buffer:
        raise HTTPException(status_code=404, detail="Bot type not found")
    
    # Check memory first
    logs = list(logs_buffer[bot_type])
    logs_buffer[bot_type] = []
    
    # If memory is empty and we have Firestore, try to fetch the most recent entries
    if not logs and db:
        try:
            doc = db.collection("bot_logs").document(bot_type).get()
            if doc.exists:
                # For simplicity, returning the last 50 stored entries
                data = doc.to_dict()
                logs = data.get("entries", [])[-50:]
        except Exception as e:
            print(f"Error fetching from Firestore: {e}")
            
    return {"logs": logs}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
