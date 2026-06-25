let currentDevice = null;
let currentDeviceInfo = null;

const ctx = document
    .getElementById('signalChart')
    .getContext('2d');

const chart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'Signal',
            data: [],
            borderColor: '#22c55e',
            tension: 0.2
        }]
    },
    options: {
        responsive: true,
        animation: false
    }
});

async function loadDevices() {

    const res = await fetch('/api/devices');
    const devices = await res.json();

    const list = document.getElementById('device-list');
    list.innerHTML = '';

    devices.forEach(device => {

        const btn = document.createElement('button');

        btn.className =
            'w-full text-left p-4 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700 mb-2';

        btn.innerHTML = `
            <div class="font-bold text-green-400">
                ${device.esp_chip_id}
            </div>
            <div class="text-xs text-gray-400">
                ID: ${device.device_id}
            </div>
            <div class="text-xs text-gray-500">
                ${new Date(device.created_at).toLocaleString()}
            </div>
        `;

        if (device.active_session_id) {
            btn.className += ' ring-1 ring-green-500';
        }

        btn.onclick = () => selectDevice(device);

        list.appendChild(btn);
    });
}

function selectDevice(device) {

    currentDeviceInfo = device;
    currentDevice = device.esp_chip_id;

    document.getElementById('device-title').textContent = device.esp_chip_id;

    document.getElementById('status').textContent = 'Live';
    document.getElementById('prediction-label').textContent = '-';
    document.getElementById('prediction-confidence').textContent = '-';
    document.getElementById('prediction-window').textContent = '-';
    updateRecordingStatus(device.active_session_id);

    updateChart();
    updatePrediction();
}

function updateRecordingStatus(sessionId) {

    document.getElementById('recording-status').textContent =
        sessionId
            ? `Recording session ${sessionId}`
            : 'No active recording';
}

async function startSession() {

    if (!currentDeviceInfo) {
        document.getElementById('recording-status').textContent = 'Select a device first';
        return;
    }

    const label = document.getElementById('session-label').value.trim();

    if (!label) {
        document.getElementById('recording-status').textContent = 'Enter a label';
        return;
    }

    const res = await fetch('/api/session/start', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            device_id: currentDeviceInfo.device_id,
            label
        })
    });

    if (!res.ok) {
        document.getElementById('recording-status').textContent = 'Could not start recording';
        return;
    }

    const session = await res.json();
    currentDeviceInfo.active_session_id = session.session_id;
    updateRecordingStatus(session.session_id);
    loadDevices();
}

async function stopSession() {

    if (!currentDeviceInfo) {
        document.getElementById('recording-status').textContent = 'Select a device first';
        return;
    }

    const res = await fetch('/api/session/stop', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            device_id: currentDeviceInfo.device_id
        })
    });

    if (!res.ok) {
        document.getElementById('recording-status').textContent = 'Could not stop recording';
        return;
    }

    currentDeviceInfo.active_session_id = null;
    updateRecordingStatus(null);
    loadDevices();
}

async function updateChart() {

    if (!currentDevice) return;

    const res = await fetch(
        `/api/download?esp_chip_id=${encodeURIComponent(currentDevice)}&limit=500`
    );

    if (!res.ok) {
        document.getElementById('status').textContent = 'Error fetching data';
        return;
    }

    const data = await res.json();

    data.reverse();

    chart.data.labels = data.map((_, i) => i);
    chart.data.datasets[0].data = data.map(x => x.value);

    chart.update();
}

async function updatePrediction() {

    if (!currentDevice) return;

    const res = await fetch(
        `/api/predict?esp_chip_id=${encodeURIComponent(currentDevice)}`
    );

    if (!res.ok) {
        document.getElementById('prediction-label').textContent = 'Error';
        document.getElementById('prediction-confidence').textContent = '-';
        document.getElementById('prediction-window').textContent = '-';
        return;
    }

    const prediction = await res.json();

    document.getElementById('prediction-label').textContent = prediction.label;

    document.getElementById('prediction-confidence').textContent =
        prediction.confidence === null
            ? '-'
            : `${Math.round(prediction.confidence * 100)}%`;

    document.getElementById('prediction-window').textContent =
        `${prediction.sample_count}/${prediction.window_size}`;
}

loadDevices();
document.getElementById('label-control').onclick = () => {
    document.getElementById('session-label').value = 'control';
};
document.getElementById('label-stimulus').onclick = () => {
    document.getElementById('session-label').value = 'stimulus';
};
document.getElementById('start-session').onclick = startSession;
document.getElementById('stop-session').onclick = stopSession;
setInterval(updateChart, 1000);
setInterval(updatePrediction, 1000);
