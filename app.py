"""
Audio Downloader API for Render
Uses yt-dlp with proxy
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import uuid
import hashlib
import time
import threading

app = Flask(__name__)
CORS(app)

# Proxy configuration
PROXY = "http://144.125.164.158:8080"

# Temp storage for downloads
DOWNLOADS = {}
DOWNLOAD_DIR = tempfile.gettempdir()

def cleanup_old_files():
    """Remove files older than 10 minutes"""
    while True:
        time.sleep(300)
        now = time.time()
        to_delete = []
        for token, info in DOWNLOADS.items():
            if now - info['created'] > 600:
                try:
                    if info.get('path') and os.path.exists(info['path']):
                        os.remove(info['path'])
                    to_delete.append(token)
                except:
                    pass
        for token in to_delete:
            DOWNLOADS.pop(token, None)

cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

def get_ydl_opts(format_type='mp3'):
    """Get yt-dlp options with proxy"""
    # Set proxy environment variables
    os.environ['HTTP_PROXY'] = PROXY
    os.environ['HTTPS_PROXY'] = PROXY
    os.environ['http_proxy'] = PROXY
    os.environ['https_proxy'] = PROXY
    
    opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'socket_timeout': 60,
        'retries': 5,
        'postprocessors': [],
        'proxy': PROXY,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        },
    }
    
    return opts

@app.route('/')
def index():
    return jsonify({
        'status': 'ok',
        'message': 'Audio Downloader API',
        'proxy': PROXY,
        'endpoints': {
            '/api/info': 'POST - Get video info',
            '/download': 'POST - Prepare download',
            '/api/stream': 'GET - Stream/download audio',
            '/test': 'GET - Test connectivity'
        }
    })

@app.route('/test')
def test_connection():
    """Test YouTube connectivity"""
    results = {'proxy': PROXY, 'youtube_test': 'not tested'}
    
    # Test YouTube access directly
    try:
        ydl_opts = get_ydl_opts()
        ydl_opts['skip_download'] = True
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info('https://www.youtube.com/watch?v=dQw4w9WgXcQ', download=False)
            results['youtube_test'] = 'success'
            results['test_video'] = info.get('title', 'Unknown')
    except Exception as e:
        results['youtube_test'] = f'failed: {str(e)}'
    
    return jsonify(results)

@app.route('/api/info', methods=['POST'])
def get_info():
    """Get video title and info"""
    try:
        data = request.get_json()
        url = data.get('url', '')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        if not url.startswith('http'):
            url = f'https://www.youtube.com/watch?v={url}'
        
        ydl_opts = get_ydl_opts()
        ydl_opts['skip_download'] = True
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'channel': info.get('channel', info.get('uploader', 'Unknown'))
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def prepare_download():
    """Prepare download and return stream URL"""
    try:
        data = request.get_json()
        video_id = data.get('videoId', '')
        format_type = data.get('format', 'mp3')
        
        if not video_id:
            return jsonify({'success': False, 'error': 'videoId is required'}), 400
        
        token = hashlib.md5(f"{video_id}:{format_type}:{time.time()}".encode()).hexdigest()
        
        DOWNLOADS[token] = {
            'video_id': video_id,
            'format': format_type,
            'created': time.time(),
            'status': 'pending'
        }
        
        download_url = f"/api/stream?token={token}&videoId={video_id}&format={format_type}"
        
        return jsonify({
            'success': True,
            'downloadUrl': download_url,
            'filename': f'audio.{format_type}'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stream', methods=['GET'])
def stream_audio():
    """Stream the audio file"""
    try:
        video_id = request.args.get('videoId', '')
        format_type = request.args.get('format', 'mp3')
        
        if not video_id:
            return jsonify({'error': 'videoId is required'}), 400
        
        url = f'https://www.youtube.com/watch?v={video_id}'
        temp_path = os.path.join(DOWNLOAD_DIR, f"{video_id}_{uuid.uuid4().hex[:8]}")
        
        ydl_opts = get_ydl_opts(format_type)
        ydl_opts['outtmpl'] = temp_path + '.%(ext)s'
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            actual_ext = info.get('ext', 'm4a')
        
        final_path = None
        for ext in [actual_ext, 'm4a', 'webm', 'opus', 'mp3', 'wav']:
            check_path = f"{temp_path}.{ext}"
            if os.path.exists(check_path):
                final_path = check_path
                actual_ext = ext
                break
        
        if not final_path or not os.path.exists(final_path):
            import glob
            files = glob.glob(f"{temp_path}*")
            return jsonify({'error': f'Download failed. Files: {files}'}), 500
        
        file_size = os.path.getsize(final_path)
        content_types = {
            'mp3': 'audio/mpeg', 'm4a': 'audio/mp4',
            'webm': 'audio/webm', 'opus': 'audio/opus'
        }
        content_type = content_types.get(actual_ext, 'audio/mp4')
        
        def generate():
            try:
                with open(final_path, 'rb') as f:
                    while chunk := f.read(8192):
                        yield chunk
            finally:
                try:
                    os.remove(final_path)
                except:
                    pass
        
        response = Response(generate(), mimetype=content_type)
        response.headers['Content-Disposition'] = f'attachment; filename="audio.{actual_ext}"'
        response.headers['Content-Length'] = file_size
        return response
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'detail': traceback.format_exc()}), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    return jsonify([])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
