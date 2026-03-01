let waves = {};
let isPlaying = false;
const videoElem = () => document.getElementById('final-video');

async function startJob() {
    const url = document.getElementById('url').value;
    if (!url) return alert(i18n.errors.no_url);

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

        // Translate the status code, inject queue position if needed
        let statusText = i18n.status[job.status] || job.status;
        if (job.status === 'waiting' && job.position > 0) {
            statusText = statusText.replace('{pos}', job.position);
        }

        document.getElementById('status-text').innerText = statusText;

        if (job.status === "complete") {
            clearInterval(timer);
            document.getElementById('status-container').classList.add('is-hidden');
            document.getElementById('btn').classList.remove('is-loading');
            showResults(job.data);
        } else if (job.status === "error") {
            clearInterval(timer);
            document.getElementById('btn').classList.remove('is-loading');
            alert(`${i18n.status.error}: ${job.data.message}`);
        }
    }, 1000);
}

function showResults(data) {
    document.getElementById('results').style.display = 'block';
    const video = videoElem();
    video.src = data.video;
    video.load();
    document.getElementById('dl').href = data.video;

    initWave('inst', data.instrumental, '#waveform-inst', '#3273dc');
    initWave('vocal', data.vocals, '#waveform-vocal', '#ff3860');

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
        btn.innerText = i18n.pause_all;
        btn.classList.replace('is-success', 'is-warning');
    } else {
        waves['inst'].pause();
        waves['vocal'].pause();
        videoElem().pause();
        btn.innerText = i18n.play_all;
        btn.classList.replace('is-warning', 'is-success');
    }
}

function syncAllTo(masterKey) {
    const time = waves[masterKey].getCurrentTime();
    const otherKey = masterKey === 'inst' ? 'vocal' : 'inst';
    waves[otherKey].setTime(time);
    videoElem().currentTime = time;
}

function toggleMute(key) {
    const isMuted = waves[key].getMuted();
    waves[key].setMuted(!isMuted);

    const btn = document.getElementById(`mute-${key}`);
    const textMute = key === 'inst' ? i18n.mute_inst : i18n.mute_vocals;

    // Note: isMuted contains the OLD state before we just toggled it.
    btn.innerText = isMuted ? textMute : i18n.unmute;
    btn.classList.toggle('is-outlined');
}

document.getElementById("url").addEventListener("keypress", function (event) {
    if (event.key === "Enter") {
        event.preventDefault();
        document.getElementById("btn").click();
    }
});

setInterval(() => {
    if (isPlaying && waves['inst'] && waves['vocal']) {
        const diff = Math.abs(waves['inst'].getCurrentTime() - waves['vocal'].getCurrentTime());
        const vidDiff = Math.abs(waves['inst'].getCurrentTime() - videoElem().currentTime);
        if (diff > 0.1) {
            waves['vocal'].setTime(waves['inst'].getCurrentTime());
            videoElem().currentTime = waves['inst'].getCurrentTime();
        }
        if (vidDiff > 0.1) {
            videoElem().currentTime = waves['inst'].getCurrentTime();
        }
    }
}, 500);