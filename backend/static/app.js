let currentDevice = null;

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

        btn.onclick = () => selectDevice(device.esp_chip_id);

        list.appendChild(btn);
    });
}

function selectDevice(deviceId) {

    currentDevice = deviceId;

    document.getElementById('device-title').textContent = deviceId;

    document.getElementById('status').textContent = 'Live';

    updateChart();
}

async function updateChart() {

    if (!currentDevice) return;

    const res = await fetch(
        `/api/download?esp_chip_id=${currentDevice}&limit=500`
    );

    if (!res.ok) {
        document.getElementById('status').textContent = 'Error fetching data';
        return;
    }

    const data = await res.json();

    chart.data.labels = data.map((_, i) => i);
    chart.data.datasets[0].data = data.map(x => x.value);

    chart.update();
}

loadDevices();
setInterval(updateChart, 1000);