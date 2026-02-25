let waves = {};

async function startJob() {
    const url = document.getElementById('url').value;
    const res = await fetch('/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
    });
    const { job_id } = await res.json();
    pollStatus(job_id);
}

function pollStatus(id) {
    const timer = setInterval(async () => {
        const res = await fetch(`/status/${id}`);
        const job = await res.json();
        document.getElementById('status-box').innerText = "Status: " + job.status;

        if (job.status === "Complete") {
            clearInterval(timer);
            showResults(job.data);
        } else if (job.status.startsWith("Error")) {
            clearInterval(timer);
            alert(job.status);
        }
    }, 2000);
}

function showResults(data) {
    document.getElementById('results').style.display = 'block';
    document.getElementById('final-video').src = data.video;
    document.getElementById('dl').href = data.video;

    // Initialize Waves
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