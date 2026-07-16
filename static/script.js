// --- NOTIFICATION API ---
function requestNotificationPermission() {
    if ("Notification" in window) {
        Notification.requestPermission();
    }
}

function sendLocalNotification(title, body) {
    if ("Notification" in window && Notification.permission === "granted") {
        new Notification(title, { body, icon: "/static/favicon.ico" });
    }
}

// --- LOGGING ---
const logsContainer = document.getElementById('logs');
function addLog(msg, type = 'info') {
    const placeholder = logsContainer.querySelector('.placeholder');
    if (placeholder) placeholder.remove();

    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;

    const time = new Date().toLocaleTimeString();
    entry.innerHTML = `
        <span class="log-time">[${time}]</span>
        <span class="log-msg">${msg}</span>
    `;

    logsContainer.prepend(entry);
    sendLocalNotification("AI Bot Alert", msg);
}

// --- API ACTIONS ---
async function runNepse() {
    const config = {
        stock_name: document.getElementById('stock-name').value,
        target_qty: document.getElementById('target-qty').value,
        target_price: document.getElementById('target-price').value,
        total_orders: parseInt(document.getElementById('total-orders').value)
    };

    try {
        const response = await fetch('/run/nepse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        const data = await response.json();

        if (response.ok) {
            document.getElementById('nepse-status').className = 'status-badge online';
            document.getElementById('nepse-status').textContent = 'Online';
            addLog(`NEPSE Bot: ${data.message}`);
        } else {
            addLog(`Error: ${data.detail}`, 'error');
        }
    } catch (err) {
        addLog(`Connection Failed: ${err.message}`, 'error');
    }
}

async function runCrypto() {
    const config = {
        interval: document.getElementById('interval').value,
        coins: document.getElementById('coins').value.trim().split(/\s+/)
    };

    try {
        const response = await fetch('/run/crypto', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        const data = await response.json();

        if (response.ok) {
            document.getElementById('crypto-status').className = 'status-badge online';
            document.getElementById('crypto-status').textContent = 'Online';
            addLog(`Crypto Bot: ${data.message}`);

            // Poll for updates if we had a websocket, but for now just simulate
            // In a real app, the backend would push updates.
        } else {
            addLog(`Error: ${data.detail}`, 'error');
        }
    } catch (err) {
        addLog(`Connection Failed: ${err.message}`, 'error');
    }
}

async function pollLogs(botType) {
    try {
        const response = await fetch(`/logs/${botType}`);
        const data = await response.json();
        if (data.logs && data.logs.length > 0) {
            data.logs.forEach(msg => addLog(`${botType.toUpperCase()}: ${msg}`));
        }
    } catch (err) {
        console.error(`Log polling failed for ${botType}`, err);
    }
}

async function checkStatus() {
    try {
        const response = await fetch('/status');
        const data = await response.json();

        const nStatus = document.getElementById('nepse-status');
        nStatus.className = data.nepse ? 'status-badge online' : 'status-badge offline';
        nStatus.textContent = data.nepse ? 'Online' : 'Offline';
        if (data.nepse) pollLogs('nepse');

        const cStatus = document.getElementById('crypto-status');
        cStatus.className = data.crypto ? 'status-badge online' : 'status-badge offline';
        cStatus.textContent = data.crypto ? 'Online' : 'Offline';
        if (data.crypto) pollLogs('crypto');
    } catch (err) {
        console.error("Status check failed", err);
    }
}

async function stopBot(botType) {
    try {
        const response = await fetch(`/stop/${botType}`, { method: 'POST' });
        const data = await response.json();
        addLog(`${botType.toUpperCase()} Bot: ${data.message}`);
        checkStatus();
    } catch (err) {
        addLog(`Stop Failed: ${err.message}`, 'error');
    }
}

// --- EVENT LISTENERS ---
document.getElementById('run-nepse').addEventListener('click', runNepse);
document.getElementById('stop-nepse').addEventListener('click', () => stopBot('nepse'));
document.getElementById('run-crypto').addEventListener('click', runCrypto);
document.getElementById('stop-crypto').addEventListener('click', () => stopBot('crypto'));
document.getElementById('clear-logs').addEventListener('click', () => {
    logsContainer.innerHTML = '<p class="placeholder">Awaiting bot activity...</p>';
});

// Initialize
requestNotificationPermission();
setInterval(checkStatus, 5000);
addLog("Dashboard loaded. Ready to start bots.");
