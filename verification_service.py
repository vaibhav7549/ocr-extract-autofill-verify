from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import Levenshtein
from datetime import datetime
from typing import Dict, Any, Optional
import os
import shutil
import uuid
import json

# --- OCR Imports ---
import easyocr
import cv2
import re
import numpy as np
from difflib import SequenceMatcher

# --- Configuration ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "mosip_ocr_db"
COLLECTION_NAME = "documents"
UPLOAD_DIR = "uploads"

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="OCR Verification Service", version="1.0")

# --- CORS Middleware ---
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
    user_submitted_data: Dict[str, Any] = Field(..., description="The verified data submitted by user")

# --- EASY OCR LOGIC (PROVIDED) ---
class FinalExtractor:
    def __init__(self):
        print(">> Initializing Final Engine (Handwriting + ID + Forms)...")
        self.reader = easyocr.Reader(['en'], gpu=False)

        self.FIELDS = {
            "Name":    {"keys": ["Name", "Student", "Full Name", "Candidate"], "type": "text"},
            "Age":     {"keys": ["Age", "Years", "Yrs"], "type": "number"},
            "Gender":  {"keys": ["Gender", "Sex"], "type": "text"},
            "Address": {"keys": ["Address", "Residing", "City", "State", "Add", "Country"], "type": "address"},
            "Email":   {"keys": ["Email", "E-mail", "Mail"], "type": "email"},
            "Phone":   {"keys": ["Phone", "Mobile", "Cell", "Contact", "Ph", "No."], "type": "phone"},
            "UID":     {"keys": ["UID", "Aadhar", "PRN", "ID", "Reg", "USN", "Number", "No"], "type": "uid"}
        }

        self.IGNORE_HEADERS = [
            "COLLEGE", "UNIVERSITY", "INSTITUTE", "GOVERNMENT", "INDIA", "STATE",
            "IDENTITY", "CARD", "STUDENT", "FORM", "REGISTRATION", "ENGINEERING",
            "TECHNOLOGY", "DEPARTMENT", "PRINCIPAL", "SIGNATURE", "VALID", "UPTO"
        ]

    def preprocess(self, image_path):
        img = cv2.imread(image_path)
        if img is None: return None

        h, w = img.shape[:2]
        img = cv2.resize(img, (w*2, h*2), interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 31, 15)
        return thresh

    def find_value_for_label(self, label_text, label_box, all_blocks, data_type):
        (lx_min, ly_min) = label_box[0]
        (lx_max, ly_max) = label_box[2]
        label_height = ly_max - ly_min
        label_center_y = (ly_min + ly_max) / 2

        candidates = []

        for block in all_blocks:
            bbox = block[0]
            text = block[1]
            conf = block[2]

            if conf < 0.3: continue
            if SequenceMatcher(None, label_text.lower(), text.lower()).ratio() > 0.6: continue

            (bx_min, by_min) = bbox[0]
            (bx_max, by_max) = bbox[2]
            block_center_y = (by_min + by_max) / 2

            if abs(label_center_y - block_center_y) < (label_height * 1.5) and bx_min > lx_min:
                dist = bx_min - lx_max
                if dist < 600:
                    candidates.append({"text": text, "score": 1000 - dist, "type": "right"})

            is_below = by_min > ly_max
            is_close = by_min < (ly_max + label_height * 4.5)

            overlap = max(0, min(lx_max, bx_max) - max(lx_min, bx_min))
            has_overlap = overlap > 0 or (bx_min >= lx_min - 20 and bx_min <= lx_max + 20)

            if is_below and is_close and has_overlap:
                dist = by_min - ly_max
                candidates.append({"text": text, "score": 800 - dist, "type": "below"})

        candidates.sort(key=lambda x: x["score"], reverse=True)

        for cand in candidates:
            val = self.validate(cand["text"], data_type)
            if val: return val
        return None

    def guess_orphan_name(self, all_blocks, existing_data, img_height):
        best_cand = None
        best_score = -100

        for block in all_blocks:
            text = block[1].strip()
            conf = block[2]
            if conf < 0.4: continue

            bbox = block[0]
            y_center = (bbox[0][1] + bbox[2][1]) / 2
            score = 0
            rel_y = y_center / img_height

            if rel_y < 0.15: score -= 50
            if rel_y > 0.18 and rel_y < 0.5: score += 20

            upper = text.upper()
            if any(bad in upper for bad in self.IGNORE_HEADERS): score -= 100
            if any(k in upper for k in ["PHONE", "MOBILE", "EMAIL", "ADD", "PRN", "UID"]): score -= 100
            if re.search(r'\d', text): score -= 50
            if len(text) < 3: score -= 50

            is_dup = False
            for k, v in existing_data.items():
                if v and text in v: is_dup = True
            if is_dup: continue

            if text[0].isupper() and text[1:].islower(): score += 10

            if score > best_score and score > 0:
                best_score = score
                best_cand = text

        return best_cand

    def validate(self, text, dtype):
        text = text.strip()
        if not text: return None

        if dtype == "phone":
            digits = re.sub(r'\D', '', text)
            if 9 < len(digits) < 14: return digits[-10:]
            return None

        if dtype == "email":
            match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
            if match: return match.group(0).lower()
            return None

        if dtype == "age":
            match = re.search(r'\b\d{1,2}\b', text)
            if match and 0 < int(match.group(0)) < 100: return match.group(0)
            return None

        if dtype == "uid":
            address_keywords = ["ROAD", "MARG", "STREET", "DIST", "TAL", "NAGAR", "BENGALURU", "SANGLI", "LANE", "NEAR", "USA", "ELM"]
            if any(k in text.upper() for k in address_keywords): return None
            clean = re.sub(r'[^a-zA-Z0-9]', '', text)
            if len(clean) > 4 and re.search(r'\d', clean): return clean
            return None

        if dtype == "text" or dtype == "address":
            if len(text) < 2: return None
            if text.upper() in ["NAME", "ADDRESS", "GENDER", "UID", "AGE"]: return None
            return text

        return text

    def extract(self, image_path):
        print(f"--- Processing: {image_path} ---")
        processed_img = self.preprocess(image_path)
        if processed_img is None: return json.dumps({"Error": "File not found"})

        blocks = self.reader.readtext(processed_img, detail=1)
        h, w = processed_img.shape[:2]

        extracted_data = {k: None for k in self.FIELDS.keys()}

        for field, config in self.FIELDS.items():
            for block in blocks:
                text = block[1].strip()
                if any(k.upper() in text.upper() for k in config["keys"]):
                    if ":" in text:
                        parts = text.split(":", 1)
                        if len(parts) > 1:
                            inline_val = self.validate(parts[1], config["type"])
                            if inline_val:
                                extracted_data[field] = inline_val
                                break
                    val = self.find_value_for_label(text, block[0], blocks, config["type"])
                    if val:
                        extracted_data[field] = val
                        break

        if not extracted_data["UID"]:
            for block in blocks:
                clean_uid = self.validate(block[1], "uid")
                if clean_uid:
                    phone = extracted_data.get("Phone")
                    if not phone or clean_uid != phone:
                        extracted_data["UID"] = clean_uid
                        break

        if not extracted_data["Phone"]:
            for block in blocks:
                val = self.validate(block[1], "phone")
                if val: extracted_data["Phone"] = val; break

        if not extracted_data["Email"]:
            for block in blocks:
                val = self.validate(block[1], "email")
                if val: extracted_data["Email"] = val; break

        if not extracted_data["Name"]:
            extracted_data["Name"] = self.guess_orphan_name(blocks, extracted_data, h)

        return extracted_data # Changed to return dict directly for API use

# Initialize Extractor Global Instance
extractor = FinalExtractor()

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
@app.get("/")
async def read_index():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"error": "index.html not found."}

# --- API Endpoints ---

@app.post("/api/v1/process-ocr")
async def process_ocr(file: UploadFile = File(...)):
    """
    1. Uploads file
    2. Runs EasyOCR logic
    3. Saves to MongoDB
    4. Returns formatted fields for Frontend
    """
    try:
        # 1. Save File Temporarily
        file_ext = file.filename.split('.')[-1]
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 2. Run Extraction
        extracted_dict = extractor.extract(file_path)
        
        # 3. Format Data for Frontend & Mongo
        # Frontend expects: {id, label, value, confidence}
        formatted_fields = []
        mongo_data = {}
        
        field_mappings = {
            "Name": {"label": "Full Name", "id": "full_name"},
            "Age": {"label": "Age", "id": "age"},
            "Gender": {"label": "Gender", "id": "gender"},
            "Address": {"label": "Address", "id": "address"},
            "Email": {"label": "Email", "id": "email"},
            "Phone": {"label": "Phone Number", "id": "phone"},
            "UID": {"label": "UID / PRN", "id": "uid"}
        }

        for ocr_key, ocr_val in extracted_dict.items():
            if ocr_key in field_mappings:
                meta = field_mappings[ocr_key]
                val = ocr_val if ocr_val else ""
                
                # Mock confidence for now as this specific EasyOCR logic 
                # returns final strings, not confidence tuples in the final dict.
                # If value exists -> High confidence, else 0
                confidence = 0.95 if val else 0.0

                # Prepare for Frontend
                formatted_fields.append({
                    "id": meta["id"],
                    "label": meta["label"],
                    "value": val,
                    "confidence": confidence
                })

                # Prepare for Mongo
                mongo_data[meta["id"]] = {
                    "value": val,
                    "confidence": confidence
                }

        # 4. Save to MongoDB
        doc_id = str(uuid.uuid4())
        db_record = {
            "_id": doc_id,
            "status": "processed",
            "image_path": file_path,
            "extracted_data": mongo_data,
            "created_at": datetime.now()
        }
        collection.insert_one(db_record)

        return {
            "status": "success",
            "doc_id": doc_id,
            "fields": formatted_fields
        }

    except Exception as e:
        print(f"OCR Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/verify-document")
async def verify_and_save_document(request: VerificationRequest):
    doc_id = request.doc_id
    user_data = request.user_submitted_data
    
    try:
        document = collection.find_one({"_id": doc_id})
        
        if not document:
            # Create if missing (fallback)
            ocr_data = {} 
        else:
            ocr_data = document.get("extracted_data", {})

        verification_report = {}
        
        for key, user_value in user_data.items():
            raw_field = ocr_data.get(key, {})
            if isinstance(raw_field, dict) and "value" in raw_field:
                ocr_value = raw_field["value"]
            else:
                ocr_value = str(raw_field) if raw_field else ""

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
    uvicorn.run(app, host="0.0.0.0", port=8001)