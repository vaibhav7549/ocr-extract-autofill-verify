from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import Levenshtein
from datetime import datetime
from typing import Dict, Any, Optional
import os

# --- Configuration ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "mosip_ocr_db"
COLLECTION_NAME = "documents"

app = FastAPI(title="OCR Verification Service", version="1.0")

# --- CORS Middleware ---
# Allows the frontend to communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database Connection ---
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    client.server_info()
    print("✅ Connected to MongoDB successfully.")
except Exception as e:
    print(f"❌ Failed to connect to MongoDB: {e}")

# --- Data Models ---
class VerificationRequest(BaseModel):
    doc_id: str
    user_submitted_data: Dict[str, Any] = Field(
        ..., 
        json_schema_extra={
            "example": {"full_name": "Ananya Sharma", "age": "29", "gender": "Female"}
        }
    )

# --- Helper Logic ---
def calculate_match_status(original_val: str, new_val: str) -> dict:
    s1 = str(original_val).strip().lower()
    s2 = str(new_val).strip().lower()

    if s1 == s2:
        return {"status": "VERIFIED", "confidence": 1.0, "message": "Exact match."}

    similarity = Levenshtein.ratio(s1, s2)
    if similarity >= 0.8:
        return {"status": "CORRECTED", "confidence": round(similarity, 2), "message": "Typo corrected."}

    return {"status": "OVERRIDDEN", "confidence": round(similarity, 2), "message": "Manual override."}

# --- SERVE FRONTEND ---
# This serves index.html at http://127.0.0.1:8001/
@app.get("/")
async def read_index():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"error": "index.html not found. Make sure it is in the same folder as verification_service.py"}

# --- API Endpoints ---
@app.post("/api/v1/verify-document")
async def verify_and_save_document(request: VerificationRequest):
    doc_id = request.doc_id
    user_data = request.user_submitted_data
    
    try:
        document = collection.find_one({"_id": doc_id})
        
        # Fallback if seed_db.py wasn't run
        if not document:
            print(f"⚠️ Document {doc_id} not found in DB. Creating new entry.")
            ocr_data = {} 
        else:
            ocr_data = document.get("extracted_data", {})

        verification_report = {}
        
        # Comparison Logic
        for key, user_value in user_data.items():
            raw_field = ocr_data.get(key, {})
            # Handle nested value/confidence structure if present
            if isinstance(raw_field, dict) and "value" in raw_field:
                ocr_value = raw_field["value"]
            else:
                ocr_value = str(raw_field) 

            match_result = calculate_match_status(ocr_value, user_value)
            
            verification_report[key] = {
                "original_value": ocr_value,
                "final_value": user_value,
                "status": match_result["status"],
                "similarity_score": match_result["confidence"],
                "notes": match_result["message"]
            }

        update_payload = {
            "status": "completed",
            "final_verified_data": user_data,
            "verification_logs": {
                "timestamp": datetime.now().isoformat(),
                "report": verification_report,
                "summary": "User manual verification completed"
            },
            "last_updated_at": datetime.now()
        }

        # Save to DB (Upsert=True handles missing documents)
        collection.update_one({"_id": doc_id}, {"$set": update_payload}, upsert=True)

        return {
            "status": "success",
            "message": "Verification Saved",
            "doc_id": doc_id,
            "verification_summary": verification_report
        }

    except Exception as e:
        print(f"Server Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Host 0.0.0.0 allows external access, Port 8001 (Changed to avoid conflict)
    uvicorn.run(app, host="0.0.0.0", port=8001)