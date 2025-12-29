# Audio Downloader API for PythonAnywhere

## Setup on PythonAnywhere

### 1. Create a new Web App
- Go to PythonAnywhere Dashboard
- Click "Web" tab → "Add a new web app"
- Choose "Flask" and Python 3.10+

### 2. Upload Files
Upload these files to your PythonAnywhere account:
- `app.py` → `/home/yourusername/mysite/app.py`
- `requirements.txt` → `/home/yourusername/mysite/requirements.txt`

### 3. Install Dependencies
Open a Bash console and run:
```bash
cd ~/mysite
pip install -r requirements.txt
```

### 4. Configure WSGI
Edit the WSGI configuration file (link in Web tab):
```python
import sys
path = '/home/yourusername/mysite'
if path not in sys.path:
    sys.path.append(path)

from app import app as application
```

### 5. Reload Web App
Click "Reload" button in the Web tab.

## API Endpoints

### POST /api/info
Get video information.
```json
{ "url": "https://youtube.com/watch?v=VIDEO_ID" }
```

### POST /download
Prepare download and get stream URL.
```json
{ "videoId": "VIDEO_ID", "format": "mp3" }
```
Returns:
```json
{
  "success": true,
  "downloadUrl": "/api/stream?token=...&videoId=...&format=mp3",
  "filename": "audio.mp3"
}
```

### GET /api/stream
Stream/download the audio file.
Query params: `token`, `videoId`, `format`

## Notes
- Uses HTTP proxy to bypass YouTube restrictions
- Files are auto-cleaned after 10 minutes
- Supports mp3, m4a, wav formats
