# OCR Extract, Autofill & Verify Tool

A full-stack web application for extracting text from documents using **EasyOCR**, auto-filling form fields, and verifying data with fuzzy matching before storing in **MongoDB**. Built for seamless document processing in verification workflows like ID cards, forms, and certificates.

[![Status](https://img.shields.io/badge/Status-Active-success)](https://github.com/vaibhav7549/ocr-extract-autofill-verify) [![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/) [![FastAPI](https://img.shields.io/badge/FastAPI-0.95%2B-009688)](https://fastapi.tiangolo.com/) [![MongoDB](https://img.shields.io/badge/Database-MongoDB-47A248)](https://www.mongodb.com/) [![JavaScript](https://img.shields.io/badge/Frontend-Vanilla%20JS-blueviolet)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)

## ✨ Features

- **OCR Text Extraction**: Powered by EasyOCR to detect and extract key fields (Name, Age, Gender, Address, Email, Phone, UID) from uploaded images (JPG/PNG).
- **Smart Autofill**: Automatically populates form fields with extracted data, complete with confidence scores for each field.
- **Manual Verification**: Interactive UI for editing, accepting, or rejecting fields with visual states (pending, accepted, editing, rejected).
- **Fuzzy Matching**: Uses Levenshtein distance to compare OCR results with user edits, flagging typos or overrides.
- **PDF Report Generation**: Exports verified data as a downloadable PDF for records.
- **Secure Storage**: Saves processed documents, extracted data, and verification logs to MongoDB for auditing.

## 🛠️ Tech Stack

- **Backend**: Python 3.8+, FastAPI, Uvicorn, EasyOCR, OpenCV, python-Levenshtein
- **Database**: MongoDB (local or cloud)
- **Frontend**: HTML5, CSS3 (custom styles with glassmorphism), Vanilla JavaScript, html2pdf.js
- **Other**: UUID for doc IDs, CORS for web access

## 📁 Project Structure

```
ocr-extract-autofill-verify/
├── index.html                 # Main frontend UI (HTML + inline CSS + JS)
├── verification_service.py    # Backend API server (FastAPI + OCR + MongoDB)
├── uploads/                   # Auto-created dir for temporary image uploads
├── README.md                  # This file
└── requirements.txt           # Python dependencies (generate with `pip freeze > requirements.txt`)
```

## ⚙️ Quick Start

### 1. Prerequisites
- Python 3.8+ installed
- MongoDB running locally (default: `mongodb://localhost:27017`)

### 2. Clone & Setup
```bash
git clone https://github.com/vaibhav7549/ocr-extract-autofill-verify.git
cd ocr-extract-autofill-verify
```

### 3. Virtual Environment
**Windows**:
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux**:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install fastapi "uvicorn[standard]" python-multipart pymongo python-Levenshtein easyocr opencv-python-headless numpy
```
> 💡 **Note**: EasyOCR downloads models (~500MB) on first run—be patient!

### 5. Run the App
1. Start MongoDB (e.g., `mongod` in a terminal).
2. Launch the server:
   ```bash
   python verification_service.py
   ```
3. Open in browser: [http://127.0.0.1:8001](http://127.0.0.1:8001)

## 📖 How It Works

1. **Upload Image**: Drag/drop or click to upload a document (e.g., ID card).
2. **OCR Processing**: Backend runs EasyOCR to extract fields → Returns autofilled form with confidence badges.
3. **Autofill & Verify**:
   - Fields auto-populate (e.g., "Full Name: John Doe" with 95% confidence).
   - Edit fields via pencil icon; accept/reject with check/X icons.
   - Visual feedback: Green for accepted, red for rejected.
4. **Submit & Export**:
   - Hit "Final Submit" → Verifies changes, saves to MongoDB.
   - Downloads PDF report → Reloads for next doc.

### Sample Workflow
- Upload `sample_id.jpg` → Extracts {full_name: "Vaibhav Chaudhari", uid: "246109002", ...}
- Verify edits → PDF saved as `Verified_abc123.pdf`

## 🔌 API Endpoints

| Method | Endpoint              | Description |
|--------|-----------------------|-------------|
| `GET`  | `/`                   | Serves the web UI. |
| `POST` | `/api/v1/process-ocr`| Upload image → Extract & autofill fields (multipart/form-data). |
| `POST` | `/api/v1/verify-document` | Submit verified data → Save to DB & generate report (JSON). |

### cURL Examples
**Extract Fields**:
```bash
curl -X POST "http://127.0.0.1:8001/api/v1/process-ocr" -F "file=@sample.jpg"
```

**Verify Data**:
```bash
curl -X POST "http://127.0.0.1:8001/api/v1/verify-document" \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "uuid-here", "user_submitted_data": {"full_name": "Updated Name"}}'
```

## 🐛 Troubleshooting

- **MongoDB Errors**: Verify `mongod` is running. Set `MONGO_URI` env var for custom setup.
- **EasyOCR Slow/Errors**: First run downloads models. Use clear, high-res images. GPU: Set `gpu=True` in `FinalExtractor`.
- **CORS Issues**: Allowed for all origins (`*`) in dev—restrict in prod.
- **PDF Not Generating**: Ensure `html2pdf.js` loads (CDN in `index.html`).
- **No Fields Detected**: Check image quality; tweak `preprocess` in `verification_service.py`.

## 🤝 Contributing

1. Fork the repo.
2. Create branch: `git checkout -b feature/your-feature`.
3. Commit: `git commit -m "Add your feature"`.
4. Push: `git push origin feature/your-feature`.
5. Open PR!

Report bugs or suggest features via Issues.



---

⭐ **Star if useful!** Questions? Open an issue or DM on GitHub. Built for hackathons & real-world doc verification.
