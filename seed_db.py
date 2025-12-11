from pymongo import MongoClient

# 1. Connect to MongoDB
client = MongoClient("mongodb://localhost:27017")
db = client["mosip_ocr_db"]
collection = db["documents"]

# 2. The Data
sample_data = {
  "_id": "64f1a2b3c9e77b0012345678",
  "status": "pending_verification",
  "image_url": "uploads/scan_ananya_sharma.jpg",
  "extracted_data": {
    "full_name": { "value": "Ananya Sharma", "confidence": 0.98 },
    "age": { "value": "29", "confidence": 0.99 },
    "gender": { "value": "Female", "confidence": 0.96 },
    "address": { "value": "123, MG Road, Bengaluru, Karnataka - 560001", "confidence": 0.85 },
    "email": { "value": "ananya.sharma@example.com", "confidence": 0.92 },
    "phone": { "value": "+91-9876543210", "confidence": 0.97 }
  },
  "metadata": {
    "scan_timestamp": "2025-10-25T10:30:00Z",
    "model_used": "DeepSeek-Janus-Pro-7B",
    "processing_time_ms": 1205
  }
}

# 3. Insert into DB
try:
    collection.replace_one({"_id": sample_data["_id"]}, sample_data, upsert=True)
    print("✅ Seed data inserted successfully! Doc ID: 64f1a2b3c9e77b0012345678")
except Exception as e:
    print(f"❌ Error inserting data: {e}")