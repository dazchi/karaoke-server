let waves = {};
let isPlaying = false;
const videoElem = () => document.getElementById('final-video');

async function startJob() {
    const url = document.getElementById('url').value;
    if (!url) return alert("Please enter a URL");

    const btn = document.getElementById('btn');
    btn.classList.add('is-loading');
    
    const res = await fetch('/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
    });
    const { job_id } = await res.json();
    
    document.getElementById('status-container').classList.remove('is-hidden');
    pollStatus(job_id);
}

function pollStatus(id) {
    const timer = setInterval(async () => {
        const res = await fetch(`/status/${id}`);
        const job = await res.json();
        document.getElementById('status-text').innerText = job.status;

        if (job.status === "Complete") {
            clearInterval(timer);
            document.getElementById('status-container').classList.add('is-hidden');
            document.getElementById('btn').classList.remove('is-loading');
            showResults(job.data);
        } else if (job.status.startsWith("Error")) {
            clearInterval(timer);
            document.getElementById('btn').classList.remove('is-loading');
            alert(job.status);
        }
    }, 2500);
}

function showResults(data) {
    document.getElementById('results').style.display = 'block';
    const video = videoElem();
    video.src = data.video;
    video.load();
    document.getElementById('dl').href = data.video;

    // Initialize both waves
    initWave('inst', data.instrumental, '#waveform-inst', '#3273dc');
    initWave('vocal', data.vocals, '#waveform-vocal', '#ff3860');

    // Sync Logic: When user seeks on one waveform, sync all others
    waves['inst'].on('interaction', () => syncAllTo('inst'));
    waves['vocal'].on('interaction', () => syncAllTo('vocal'));
}

function initWave(key, url, container, color) {
    if (waves[key]) waves[key].destroy();
    waves[key] = WaveSurfer.create({
        container: container,
        waveColor: color,
        progressColor: '#000',
        url: url,
        height: 80,
        interact: true
    });
}

function togglePlayback() {
    isPlaying = !isPlaying;
    const btn = document.getElementById('master-play');
    
    if (isPlaying) {
        waves['inst'].play();
        waves['vocal'].play();
        videoElem().play();
        btn.innerText = "Pause All";
        btn.classList.replace('is-success', 'is-warning');
    } else {
        waves['inst'].pause();
        waves['vocal'].pause();
        videoElem().pause();
        btn.innerText = "Play All";
        btn.classList.replace('is-warning', 'is-success');
    }
}

function syncAllTo(masterKey) {
    const time = waves[masterKey].getCurrentTime();
    
    // Sync other audio
    const otherKey = masterKey === 'inst' ? 'vocal' : 'inst';
    waves[otherKey].setTime(time);
    
    // Sync video
    videoElem().currentTime = time;
}

function toggleMute(key) {
    const isMuted = waves[key].getMuted();
    waves[key].setMuted(!isMuted);
    
    const btn = document.getElementById(`mute-${key}`);
    btn.innerText = isMuted ? `Mute ${key === 'inst' ? 'Inst' : 'Vocals'}` : "Unmute";
    btn.classList.toggle('is-outlined');
}

// Periodic drift correction (runs every 1s while playing)
setInterval(() => {
    if (isPlaying && waves['inst'] && waves['vocal']) {
        const diff = Math.abs(waves['inst'].getCurrentTime() - waves['vocal'].getCurrentTime());
        if (diff > 0.1) { // If drift > 100ms
            waves['vocal'].setTime(waves['inst'].getCurrentTime());
            videoElem().currentTime = waves['inst'].getCurrentTime();
        }
    }
}, 1000);