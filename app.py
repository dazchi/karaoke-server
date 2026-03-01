import os
import subprocess
import uuid
import threading
import queue
import shutil
import json # <--- New Import
import yt_dlp # <--- New Import for progress tracking
import re
import ffmpeg
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix
from audio_separator.separator import Separator

app = Flask(__name__, template_folder='./')
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configuration
STORAGE_PATH = "songs"
TMP_DIR = "tmp"
os.makedirs(TMP_DIR, exist_ok=True)
os.makedirs(STORAGE_PATH, exist_ok=True)

# --- LOCALIZATION SETUP ---
LOCALES = {}
for lang in ['en', 'zh_TW']:
    with open(f'locales/{lang}.json', 'r', encoding='utf-8') as f:
        LOCALES[lang] = json.load(f)

def get_locale():
    # 1. Manual Override: User clicked the dropdown (?lang=en)
    requested_lang = request.args.get('lang')
    if requested_lang in LOCALES:
        return requested_lang

    # 2. Automatic OS/Browser Detection: Parse the Accept-Language header
    # Browsers send a prioritized list (e.g., "zh-TW,zh;q=0.9,en-US;q=0.8")
    if request.accept_languages:
        print("Browser Accept-Language:", request.accept_languages)
        for browser_lang in request.accept_languages.values():
            lang_code = browser_lang.lower()
            
            # If the OS language starts with 'zh' (covers zh-TW, zh-HK, zh-CN, zh), use Traditional Chinese
            if lang_code.startswith('zh'):
                return 'zh_TW'

    # 3. Final Fallback: If the user's OS is French, German, etc., default to zh_TW
    return 'en'
# --------------------------

job_queue = queue.Queue()
active_job_id = None
jobs = {}

print("Loading AI Model...")
separator = Separator()
separator.load_model('UVR-MDX-NET-Inst_HQ_3.onnx')

def update_job(job_id, status_code, data=None):
    jobs[job_id] = {"status": status_code, "data": data or {}}

def worker():
    global active_job_id
    while True:
        job_id, youtube_url, base_url = job_queue.get()
        active_job_id = job_id
        try:
            process_karaoke_task(job_id, youtube_url, base_url)
        except Exception as e:
            # Store error details in data, use "error" as status code
            update_job(job_id, "error", {"message": str(e)})
        finally:
            active_job_id = None
            job_queue.task_done()

def process_karaoke_task(job_id, youtube_url, base_url):
    update_job(job_id, "fetching_info")
    
    # Progress hook for yt-dlp
    def progress_hook(d):
        if d['status'] == 'downloading':
            ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
            p = text_without_colors = ansi_escape.sub('', d.get('_percent_str', '0%').strip()).replace(' ','')
            current_phase = jobs[job_id].get("status")
            # Avoid overwriting the phase name, just append/update the percentage
            update_job(job_id, current_phase, {"percentage": str(p)})

    # Get video ID
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        video_id = info.get('id', 'video')

    input_wav = os.path.join(TMP_DIR, f"{job_id}_in.wav")
    video_only = os.path.join(TMP_DIR, f"{job_id}_v.mp4")
    
    # Download Audio
    update_job(job_id, "downloading_audio", {"percentage": "0%"})
    ydl_opts_audio = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],
        'outtmpl': input_wav.replace('.wav', ''), # yt-dlp adds extension
        'progress_hooks': [progress_hook],
        'noplaylist': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
        ydl.download([youtube_url])
    
    # Ensure correct extension if yt-dlp changed it (though wav is forced above)
    if not os.path.exists(input_wav) and os.path.exists(input_wav + ".wav"):
        os.rename(input_wav + ".wav", input_wav)

    # Download Video
    update_job(job_id, "downloading_video", {"percentage": "0%"})
    ydl_opts_video = {
        'format': 'bestvideo',
        'outtmpl': video_only,
        'progress_hooks': [progress_hook],
        'noplaylist': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
        ydl.download([youtube_url])

    update_job(job_id, "ai_separation")
    output_files = separator.separate(input_wav)
    
    inst_file, vocal_file = "", ""
    for f in output_files:
        new_name = f"{job_id}_{f}"
        shutil.move(f, os.path.join(STORAGE_PATH, new_name))
        if "instrumental" in f.lower(): inst_file = new_name
        if "vocals" in f.lower(): vocal_file = new_name

    update_job(job_id, "merging")
    final_mp4 = f"{job_id}_karaoke.mp4"
    final_path = os.path.join(STORAGE_PATH, final_mp4)
    inst_path = os.path.join(STORAGE_PATH, inst_file)
    
    ffmpeg_cmd = [
        'ffmpeg', '-y', '-hwaccel', 'cuda',
        '-i', inst_path, '-i', input_wav, '-i', video_only,
        '-filter_complex', "[0:a]pan=mono|c0=c0[left];[1:a]pan=mono|c0=c0[right];[left][right]join=inputs=2:channel_layout=stereo[a]",
        '-map', '2:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', final_path
    ]
    subprocess.run(ffmpeg_cmd)

    if os.path.exists(input_wav): os.remove(input_wav)
    if os.path.exists(video_only): os.remove(video_only)

    update_job(job_id, "complete", {
        "video": f"{base_url}/songs/{final_mp4}",
        "instrumental": f"{base_url}/songs/{inst_file}",
        "vocals": f"{base_url}/songs/{vocal_file}"
    })

@app.route('/')
def home():
    lang = get_locale()
    return render_template('index.html', t=LOCALES[lang], current_lang=lang)

@app.route('/songs/<path:filename>')
def serve_songs(filename):
    return send_from_directory(STORAGE_PATH, filename)

@app.route('/process', methods=['POST'])
def handle_request():
    url = request.json.get('url')
    if not url: return jsonify({"error": "no_url"}), 400
    
    job_id = str(uuid.uuid4())[:8]
    base_url = request.host_url.rstrip('/')
    
    jobs[job_id] = {"status": "waiting", "data": {}}
    job_queue.put((job_id, url, base_url))
    
    return jsonify({"job_id": job_id})

@app.route('/status/<job_id>')
def get_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"status": "not_found"})
    
    queue_list = list(job_queue.queue)
    position = -1
    for i, (qid, _, _) in enumerate(queue_list):
        if qid == job_id:
            position = i + 1
            break
            
    status_code = job['status']
    if position == -1 and status_code == "waiting":
        status_code = "processing"

    return jsonify({
        "status": status_code, 
        "position": position,
        "data": job.get('data')
    })

if __name__ == '__main__':
    threading.Thread(target=worker, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=False)