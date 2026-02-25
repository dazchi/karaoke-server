import os
import subprocess
import uuid
from flask import Flask, request, jsonify, render_template
from audio_separator.separator import Separator

app = Flask(__name__, template_folder='./')

# Configuration
STORAGE_PATH = "songs"
TMP_DIR = "tmp"
os.makedirs(TMP_DIR, exist_ok=True)
os.makedirs(STORAGE_PATH, exist_ok=True)

# Global Job Tracker
jobs = {}

print("Loading AI Model...")
separator = Separator()
separator.load_model('UVR-MDX-NET-Inst_HQ_3.onnx')

def update_job(job_id, status, data=None):
    jobs[job_id] = {"status": status, "data": data or {}}

def process_karaoke_task(job_id, youtube_url, base_url):
    try:
        # Stage 1: Metadata
        update_job(job_id, "Fetching video info...")
        video_id = subprocess.check_output(['yt-dlp', '--get-id', youtube_url]).decode().strip()
        
        input_wav = os.path.join(TMP_DIR, f"{job_id}_in.wav")
        video_only = os.path.join(TMP_DIR, f"{job_id}_v.mp4")
        
        # Stage 2: Downloading
        update_job(job_id, "Downloading from YouTube...")
        subprocess.run(['yt-dlp', '-x', '--audio-format', 'wav', '-o', input_wav, youtube_url])
        subprocess.run(['yt-dlp', '-f', 'bestvideo', '-o', video_only, youtube_url])

        # Stage 3: AI Separation
        update_job(job_id, "AI Separation (UVR MDX-Net)...")
        output_files = separator.separate(input_wav)
        
        inst_file = ""
        vocal_file = ""
        
        # Move stems to storage for preview
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
            '-i', inst_path, '-i', input_wav, '-i', video_only,
            '-filter_complex', "[0:a]pan=mono|c0=c0[left];[1:a]pan=mono|c0=c0[right];[left][right]join=inputs=2:channel_layout=stereo[a]",
            '-map', '2:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', final_path
        ]
        subprocess.run(ffmpeg_cmd)

        # Cleanup
        if os.path.exists(input_wav): os.remove(input_wav)
        if os.path.exists(video_only): os.remove(video_only)

        # Final Result
        update_job(job_id, "Complete", {
            "video": f"{base_url}/songs/{final_mp4}",
            "instrumental": f"{base_url}/songs/{inst_file}",
            "vocals": f"{base_url}/songs/{vocal_file}"
        })
    except Exception as e:
        update_job(job_id, f"Error: {str(e)}")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def handle_request():
    url = request.json.get('url')
    job_id = str(uuid.uuid4())[:8]
    base_url = request.host_url.rstrip('/')
    
    # In a production app, use a Background Thread/Celery. 
    # For now, we'll process synchronously but return the ID first for polling.
    jobs[job_id] = {"status": "Queued", "data": {}}
    
    # Note: To make this non-blocking, you'd use threading.Thread
    import threading
    threading.Thread(target=process_karaoke_task, args=(job_id, url, base_url)).start()
    
    return jsonify({"job_id": job_id})

@app.route('/status/<job_id>')
def get_status(job_id):
    return jsonify(jobs.get(job_id, {"status": "Not Found"}))

if __name__ == '__main__':
    import shutil
    app.run(host='0.0.0.0', port=5000)