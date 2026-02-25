let waves = {};

async function startJob() {
    const url = document.getElementById('url').value;
    if (!url) return alert("Please enter a URL");

    const btn = document.getElementById('btn');
    btn.classList.add('is-loading');
    
    try {
        const res = await fetch('/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        const { job_id } = await res.json();
        
        document.getElementById('status-container').classList.remove('is-hidden');
        pollStatus(job_id);
    } catch (e) {
        alert("Server Error");
        btn.classList.remove('is-loading');
    }
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
    document.getElementById('final-video').src = data.video;
    document.getElementById('dl').href = data.video;

    initWave('inst', data.instrumental, '#waveform-inst', '#3273dc');
    initWave('vocal', data.vocals, '#waveform-vocal', '#ff3860');
}

function initWave(key, url, container, color) {
    if (waves[key]) waves[key].destroy();
    waves[key] = WaveSurfer.create({
        container: container,
        waveColor: color,
        progressColor: '#000',
        url: url,
        height: 80
    });
}