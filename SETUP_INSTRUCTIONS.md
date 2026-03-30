# Frontend Setup Instructions

## 1. Install Dependencies

```bash
cd frontend
npm install
```

## 2. Configure Environment

Create `.env` file in the frontend folder:
```env
REACT_APP_API_URL=http://localhost:3001
```

## 3. Start the React Development Server

```bash
npm start
```

The app will open at: http://localhost:3000

---

# Backend Setup Instructions

## 1. Install Python Dependencies

```bash
pip install flask flask-cors requests python-dotenv
```

Or install from requirements_packages.txt:
```bash
pip install -r requirements_packages.txt
```

## 2. Run the Flask API Server

```bash
cd src
python flaskSearchAPI.py
```

The API will run at: http://localhost:3001

## API Endpoints

### POST /api/search
Search documents in Azure Search index

**Request:**
```json
{
  "query": "API 617",
  "top": 20
}
```

**Response:**
```json
{
  "results": [
    {
      "id": "html_page_3_table_1",
      "content": "<html><table>...</table></html>",
      "filename": "page_3_tables.html",
      "page_number": 3,
      "indexed_date": "2026-03-13T14:00:00Z",
      "text_length": 1200
    }
  ],
  "count": 1,
  "total": 1
}
```

### GET /api/health
Check API health and Azure Search connection

**Response:**
```json
{
  "status": "healthy",
  "index": "search-index-4",
  "endpoint": "https://search-ais-1.search.windows.net"
}
```

---

# Running Both Servers

**Terminal 1 - Frontend:**
```bash
cd frontend
npm start
```

**Terminal 2 - Backend:**
```bash
cd src
python flaskSearchAPI.py
```

Then access the application at: http://localhost:3000

---

# Docker Deployment (Optional)

To deploy in production, use Docker:

**Frontend Dockerfile:**
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend/src ./src
COPY frontend/public ./public
EXPOSE 3000
CMD ["npm", "start"]
```

**Backend Dockerfile:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements_packages.txt ./
RUN pip install -r requirements_packages.txt
COPY src/ ./
EXPOSE 3001
CMD ["python", "flaskSearchAPI.py"]
```

---

# Features

✅ Real-time search across PDF documents
✅ Text and HTML table support
✅ Responsive UI design
✅ Azure AI Search integration
✅ RESTful API backend
✅ CORS enabled for development

Ready to search! 🚀
