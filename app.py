import os
import subprocess
import uuid
import threading
import queue
import shutil
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix # <--- New Import
from audio_separator.separator import Separator

app = Flask(__name__, template_folder='./')

# --- FIX FOR REVERSE PROXY ---
# x_proto=1 tells Flask to trust the X-Forwarded-Proto header
# x_host=1 tells Flask to trust the X-Forwarded-Host header
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
# -----------------------------

# Configuration
STORAGE_PATH = "songs"
TMP_DIR = "tmp"
os.makedirs(TMP_DIR, exist_ok=True)
os.makedirs(STORAGE_PATH, exist_ok=True)

# Job Management
job_queue = queue.Queue()
active_job_id = None
jobs = {} # Stores status and results

print("Loading AI Model...")
separator = Separator()
separator.load_model('UVR-MDX-NET-Inst_HQ_3.onnx')

def update_job(job_id, status, data=None):
    jobs[job_id] = {"status": status, "data": data or {}, "queued_at": jobs.get(job_id, {}).get('queued_at')}

def worker():
    """Background worker that pulls jobs from the queue."""
    global active_job_id
    while True:
        job_id, youtube_url, base_url = job_queue.get()
        active_job_id = job_id
        
        try:
            process_karaoke_task(job_id, youtube_url, base_url)
        except Exception as e:
            update_job(job_id, f"Error: {str(e)}")
        finally:
            active_job_id = None
            job_queue.task_done()

def process_karaoke_task(job_id, youtube_url, base_url):
    # Stage 1: Metadata
    update_job(job_id, "Fetching video info...")
    video_id = subprocess.check_output(['yt-dlp', '--no-playlist', '--get-id', youtube_url]).decode().strip()
    
    input_wav = os.path.join(TMP_DIR, f"{job_id}_in.wav")
    video_only = os.path.join(TMP_DIR, f"{job_id}_v.mp4")
    
    # Stage 2: Downloading
    update_job(job_id, "Downloading audio from YouTube...")
    result = subprocess.run(['yt-dlp', '--no-playlist', '-x', '--audio-format', 'wav', '-o', input_wav, youtube_url])
    if result.returncode != 0:
        raise ValueError("Failed to download audio")
    
    update_job(job_id, "Downloading video from YouTube...")
    result = subprocess.run(['yt-dlp', '--no-playlist', '-f', 'bestvideo', '-o', video_only, youtube_url])
    if result.returncode != 0:
        raise ValueError("Failed to download video")

    # Stage 3: AI Separation
    update_job(job_id, "AI Separation (UVR MDX-Net)...")
    output_files = separator.separate(input_wav)
    
    inst_file = ""
    vocal_file = ""
    
    for f in output_files:
        new_name = f"{job_id}_{f}"
        shutil.move(f, os.path.join(STORAGE_PATH, new_name))
        if "instrumental" in f.lower(): inst_file = new_name
        if "vocals" in f.lower(): vocal_file = new_name

    # Stage 4: FFmpeg Merging
    update_job(job_id, "Merging audio channels...")
    final_mp4 = f"{job_id}_karaoke.mp4"
    final_path = os.path.join(STORAGE_PATH, final_mp4)
    
    inst_path = os.path.join(STORAGE_PATH, inst_file)
    
    ffmpeg_cmd = [
        'ffmpeg', '-y',
        '-hwaccel', 'cuda',
        '-i', inst_path, '-i', input_wav, '-i', video_only,
        '-filter_complex', "[0:a]pan=mono|c0=c0[left];[1:a]pan=mono|c0=c0[right];[left][right]join=inputs=2:channel_layout=stereo[a]",
        '-map', '2:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', final_path
    ]
    subprocess.run(ffmpeg_cmd)

    # Cleanup
    if os.path.exists(input_wav): os.remove(input_wav)
    if os.path.exists(video_only): os.remove(video_only)

    update_job(job_id, "Complete", {
        "video": f"{base_url}/songs/{final_mp4}",
        "instrumental": f"{base_url}/songs/{inst_file}",
        "vocals": f"{base_url}/songs/{vocal_file}"
    })

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/songs/<path:filename>')
def serve_songs(filename):
    return send_from_directory(STORAGE_PATH, filename)

@app.route('/process', methods=['POST'])
def handle_request():
    url = request.json.get('url')
    if not url: return jsonify({"error": "No URL"}), 400
    
    job_id = str(uuid.uuid4())[:8]
    base_url = request.host_url.rstrip('/')
    
    jobs[job_id] = {"status": "Waiting in queue", "data": {}}
    print(f'Enquing job with base_url: {base_url}')
    job_queue.put((job_id, url, base_url))
    
    return jsonify({"job_id": job_id})

@app.route('/status/<job_id>')
def get_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"status": "Not Found"})
    
    # Calculate position in line
    queue_list = list(job_queue.queue)
    position = -1
    for i, (qid, _, _) in enumerate(queue_list):
        if qid == job_id:
            position = i + 1
            break
            
    # If it's not in the queue but not finished, it's currently processing
    if position == -1 and job['status'] == "Waiting in queue":
        status_text = "Processing now..."
    elif position != -1:
        status_text = f"Waiting in queue (Position: {position})"
    else:
        status_text = job['status']

    return jsonify({"status": status_text, "data": job.get('data')})

if __name__ == '__main__':
    # Start the background worker thread
    threading.Thread(target=worker, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=False) # Debug false to prevent double thread start
