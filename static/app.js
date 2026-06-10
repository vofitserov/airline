// Global App State
let appState = {
    isPlaying: false,
    currentStreamId: null,
    wifiConnected: false,
    wifiMode: 'Disconnected',
    wifiSsid: '',
    wifiIp: '127.0.0.1',
    streams: []
};

// Polling interval reference
let statusInterval = null;
let wifiScanInterval = null;

// DOM Elements
const navItems = document.querySelectorAll('.nav-item');
const tabPanes = document.querySelectorAll('.tab-pane');
const sidebarStatusDot = document.getElementById('sidebar-status-dot');
const sidebarStatusText = document.getElementById('sidebar-status-text');

// Playback Elements
const playbackBadge = document.getElementById('playback-badge');
const currentTitle = document.getElementById('current-title');
const currentUrl = document.getElementById('current-url');
const btnStop = document.getElementById('btn-stop');
const btnPlayStatus = document.getElementById('btn-play-status');
const playStatusIcon = document.getElementById('play-status-icon');
const visualizer = document.querySelector('.visualizer-container');
const streamsList = document.getElementById('streams-list');
const addStreamForm = document.getElementById('add-stream-form');

// Wi-Fi Elements
const netStatusText = document.getElementById('net-status-text');
const netModeText = document.getElementById('net-mode-text');
const netSsidText = document.getElementById('net-ssid-text');
const netIpText = document.getElementById('net-ip-text');
const wifiBadge = document.getElementById('wifi-badge');
const wifiMainIcon = document.getElementById('wifi-main-icon');
const wifiDetailsSsid = document.getElementById('wifi-details-ssid');
const wifiDetailsIp = document.getElementById('wifi-details-ip');
const wifiDetailsMode = document.getElementById('wifi-details-mode');
const hotspotBanner = document.getElementById('hotspot-banner');
const btnScanWifi = document.getElementById('btn-scan-wifi');
const scanIcon = document.getElementById('scan-icon');
const wifiNetworksList = document.getElementById('wifi-networks-list');

// Mobile UI
const menuToggle = document.getElementById('menuToggle');
const sidebar = document.querySelector('.sidebar');
const navOverlay = document.getElementById('navOverlay');

// Modals
const wifiModal = document.getElementById('wifi-modal');
const wifiModalClose = document.getElementById('wifi-modal-close');
const wifiModalCancel = document.getElementById('wifi-modal-cancel');
const wifiConnectForm = document.getElementById('wifi-connect-form');
const modalWifiTitle = document.getElementById('modal-wifi-title');
const modalWifiSsid = document.getElementById('modal-wifi-ssid');
const modalWifiPassword = document.getElementById('modal-wifi-password');

const imageLightbox = document.getElementById('image-lightbox');
const lightboxImg = document.getElementById('lightbox-img');
const lightboxCaption = document.getElementById('lightbox-caption');

// ----------------------------------------------------
// Toast Notification Helper
// ----------------------------------------------------
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let iconName = 'check-circle';
    if (type === 'error') iconName = 'alert-octagon';
    if (type === 'warning') iconName = 'alert-triangle';
    
    toast.innerHTML = `
        <i data-lucide="${iconName}"></i>
        <span>${message}</span>
    `;
    
    container.appendChild(toast);
    lucide.createIcons();
    
    // Slide out after 3.7 seconds and remove at 4s
    setTimeout(() => {
        toast.style.transform = 'translateY(20px)';
        toast.style.opacity = '0';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3700);
}

// ----------------------------------------------------
// Tab Navigation
// ----------------------------------------------------
function switchTab(tabId) {
    // Update active nav item
    navItems.forEach(item => {
        if (item.dataset.tab === tabId) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Update visible tab pane
    tabPanes.forEach(pane => {
        if (pane.id === `tab-${tabId}`) {
            pane.classList.add('active');
        } else {
            pane.classList.remove('active');
        }
    });

    // Trigger Wi-Fi scan automatically if switched to Wi-Fi tab
    if (tabId === 'wifi-config') {
        scanWifi();
    }

    // Close mobile menu if open
    closeMobileMenu();
}

// Mobile Menu Event Handlers
function toggleMobileMenu() {
    sidebar.classList.toggle('open');
    navOverlay.classList.toggle('open');
}

function closeMobileMenu() {
    sidebar.classList.remove('open');
    navOverlay.classList.remove('open');
}

// ----------------------------------------------------
// Lightbox Gallery
// ----------------------------------------------------
window.openLightbox = function(imageId) {
    const img = document.getElementById(imageId);
    imageLightbox.style.display = "block";
    lightboxImg.src = img.src;
    lightboxCaption.innerHTML = img.alt;
};

window.closeLightbox = function() {
    imageLightbox.style.display = "none";
};

// ----------------------------------------------------
// API Communication
// ----------------------------------------------------

// Load Stream Stations
async function loadStreams() {
    try {
        const response = await fetch('/api/streams');
        if (!response.ok) throw new Error("Failed to load streams");
        const streams = await response.json();
        appState.streams = streams;
        renderStreams();
    } catch (error) {
        console.error("Error fetching streams:", error);
        showToast("Error loading streams.", "error");
    }
}

// Render Streams Grid
function renderStreams() {
    if (appState.streams.length === 0) {
        streamsList.innerHTML = '<p class="placeholder-text">No stations configured. Add one below!</p>';
        return;
    }

    streamsList.innerHTML = appState.streams.map(stream => {
        const isActive = appState.isPlaying && appState.currentStreamId === stream.id;
        const deleteButton = stream.default 
            ? '' 
            : `<button class="btn-delete-stream" onclick="deleteStream('${stream.id}', event)" title="Delete Station">
                 <i data-lucide="trash-2"></i>
               </button>`;
               
        return `
            <div class="stream-card ${isActive ? 'active' : ''}" onclick="playStream('${stream.id}')">
                <div class="stream-card-meta">
                    <h4>${stream.name}</h4>
                    <p class="truncate">${stream.url}</p>
                </div>
                <div class="stream-card-actions">
                    <span class="badge ${isActive ? 'badge-success' : ''}">
                        ${isActive ? 'Active' : 'Offline'}
                    </span>
                    <div class="right-actions">
                        ${deleteButton}
                        <button class="btn btn-secondary btn-sm">
                            <i data-lucide="${isActive ? 'square' : 'play'}"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    // Initialize icons in generated HTML
    lucide.createIcons();
}

// Play Selected Stream
async function playStream(streamId) {
    // If clicking the active station, we toggle stop
    if (appState.isPlaying && appState.currentStreamId === streamId) {
        stopPlayback();
        return;
    }

    showToast("Starting stream...", "info");
    
    try {
        const response = await fetch('/api/play', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: streamId })
        });
        
        const data = await response.json();
        if (data.success) {
            showToast(`Streaming ${data.stream.name}`, "success");
            pollStatus(); // Immediate status update
        } else {
            showToast(data.message || "Failed to start stream", "error");
        }
    } catch (error) {
        showToast("Network error trying to play stream.", "error");
    }
}

// Stop Playback
async function stopPlayback() {
    try {
        const response = await fetch('/api/stop', { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            showToast("Playback stopped.", "success");
            pollStatus();
        } else {
            showToast("Failed to stop playback.", "error");
        }
    } catch (error) {
        showToast("Network error trying to stop playback.", "error");
    }
}

// Add Custom Stream Form Submit
addStreamForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('stream-name').value;
    const url = document.getElementById('stream-url').value;
    
    try {
        const response = await fetch('/api/streams', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, url })
        });
        
        const data = await response.json();
        if (response.status === 201) {
            showToast(`Added station "${name}"`, "success");
            addStreamForm.reset();
            loadStreams();
        } else {
            showToast(data.message || "Failed to add station", "error");
        }
    } catch (error) {
        showToast("Network error adding station.", "error");
    }
});

// Delete Custom Stream
window.deleteStream = async function(streamId, event) {
    event.stopPropagation(); // Prevent card click trigger
    
    if (!confirm("Are you sure you want to delete this station?")) return;

    try {
        const response = await fetch(`/api/streams/${streamId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        if (data.success) {
            showToast("Station deleted successfully", "success");
            loadStreams();
            // If the deleted stream was playing, sync the UI status
            if (appState.currentStreamId === streamId) {
                pollStatus();
            }
        } else {
            showToast(data.message || "Failed to delete station", "error");
        }
    } catch (error) {
        showToast("Network error deleting station.", "error");
    }
};

// ----------------------------------------------------
// Wi-Fi Connections Logic
// ----------------------------------------------------

// Scan for networks
async function scanWifi() {
    btnScanWifi.disabled = true;
    scanIcon.classList.add('spin');
    wifiNetworksList.innerHTML = `
        <div class="loading-placeholder">
            <div class="spinner"></div>
            <p>Scanning nearby airwaves...</p>
        </div>
    `;

    try {
        const response = await fetch('/api/wifi/scan', { method: 'POST' });
        if (!response.ok) throw new Error("Wifi scan returned error");
        const networks = await response.json();
        renderWifiNetworks(networks);
    } catch (error) {
        showToast("Failed to scan Wi-Fi networks.", "error");
        wifiNetworksList.innerHTML = '<p class="placeholder-text">Scanning failed. Verify device has Wi-Fi enabled.</p>';
    } finally {
        btnScanWifi.disabled = false;
        scanIcon.classList.remove('spin');
    }
}

// Render wifi list
function renderWifiNetworks(networks) {
    if (!networks || networks.length === 0) {
        wifiNetworksList.innerHTML = '<p class="placeholder-text">No Wi-Fi networks found.</p>';
        return;
    }

    wifiNetworksList.innerHTML = networks.map(net => {
        // Determine signal rating
        let signalClass = 'signal-excellent';
        if (net.signal < 45) signalClass = 'signal-poor';
        else if (net.signal < 65) signalClass = 'signal-fair';
        else if (net.signal < 85) signalClass = 'signal-good';
        
        const secureIcon = net.security ? '<i data-lucide="lock" class="lock-icon"></i>' : '';
        const secureBadge = net.security ? `<span class="sec-badge">${net.security}</span>` : '<span class="sec-badge">Open</span>';
        
        return `
            <div class="wifi-network-row" onclick="openConnectModal('${net.ssid}', ${!!net.security})">
                <div class="wifi-net-info">
                    <i data-lucide="wifi"></i>
                    <div>
                        <span class="ssid-name">${net.ssid}</span>
                        ${secureBadge}
                    </div>
                </div>
                <div class="wifi-net-signal ${signalClass}">
                    ${secureIcon}
                    <div class="signal-bar-wrapper" title="Signal strength: ${net.signal}%">
                        <div class="signal-bar"></div>
                        <div class="signal-bar"></div>
                        <div class="signal-bar"></div>
                        <div class="signal-bar"></div>
                    </div>
                    <button class="btn btn-secondary btn-sm">Connect</button>
                </div>
            </div>
        `;
    }).join('');
    
    lucide.createIcons();
}

// Connect Modal
function openConnectModal(ssid, isSecure) {
    if (!isSecure) {
        // Open networks can connect directly
        if (confirm(`Do you want to connect to the open network "${ssid}"?`)) {
            connectToWifi(ssid, '');
        }
        return;
    }

    modalWifiTitle.textContent = `Connect to ${ssid}`;
    modalWifiSsid.value = ssid;
    modalWifiPassword.value = '';
    wifiModal.classList.add('open');
    modalWifiPassword.focus();
}

function closeConnectModal() {
    wifiModal.classList.remove('open');
}

wifiModalClose.addEventListener('click', closeConnectModal);
wifiModalCancel.addEventListener('click', closeConnectModal);

wifiConnectForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const ssid = modalWifiSsid.value;
    const password = modalWifiPassword.value;
    closeConnectModal();
    connectToWifi(ssid, password);
});

// Post Connect Request
async function connectToWifi(ssid, password) {
    showToast(`Attempting connection to "${ssid}"...`, "info");
    
    try {
        const response = await fetch('/api/wifi/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ssid, password })
        });
        
        const data = await response.json();
        if (data.success) {
            // Started connecting task
            pollWifiConnectionTask();
        } else {
            showToast(data.message || "Failed to start connection task", "error");
        }
    } catch (error) {
        showToast("Error connecting to network.", "error");
    }
}

// Poll background wifi connection status
let wifiTaskPollInterval = null;
function pollWifiConnectionTask() {
    if (wifiTaskPollInterval) clearInterval(wifiTaskPollInterval);
    
    // Disable scan button and show loading text
    btnScanWifi.disabled = true;
    wifiNetworksList.innerHTML = `
        <div class="loading-placeholder">
            <div class="spinner"></div>
            <p id="wifi-connect-loading-text">Connecting to Wi-Fi...</p>
        </div>
    `;

    wifiTaskPollInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/wifi/connect/status');
            const data = await response.json();
            
            const loadingText = document.getElementById('wifi-connect-loading-text');
            if (loadingText && data.message) {
                loadingText.textContent = data.message;
            }

            if (data.status === 'success') {
                clearInterval(wifiTaskPollInterval);
                showToast("Wi-Fi connected successfully!", "success");
                btnScanWifi.disabled = false;
                scanWifi(); // reload network list
                pollStatus(); // Refresh general details
            } else if (data.status === 'failed') {
                clearInterval(wifiTaskPollInterval);
                showToast(data.message || "Wi-Fi connection failed.", "error");
                btnScanWifi.disabled = false;
                scanWifi(); // restore scanning
                pollStatus();
            }
        } catch (e) {
            console.error("Error polling wifi task:", e);
        }
    }, 1500);
}

// ----------------------------------------------------
// System Status Polling
// ----------------------------------------------------
async function pollStatus() {
    try {
        const response = await fetch('/api/status');
        if (!response.ok) throw new Error("Offline");
        
        const status = await response.json();
        
        // Update Sidebar Server Status Dot
        sidebarStatusDot.className = 'status-indicator online';
        sidebarStatusText.textContent = 'Server Online';
        
        // Sync Playback State
        appState.isPlaying = status.playing;
        if (status.playing && status.current_stream) {
            appState.currentStreamId = status.current_stream.id;
            currentTitle.textContent = status.current_stream.name;
            currentUrl.textContent = status.current_stream.url;
            playbackBadge.textContent = 'Streaming';
            playbackBadge.className = 'badge badge-success';
            btnStop.disabled = false;
            
            // Large Play Button state changes to STOP
            btnPlayStatus.title = "Stop Playback";
            playStatusIcon.setAttribute('data-lucide', 'square');
            visualizer.classList.add('playing');
        } else {
            appState.currentStreamId = null;
            currentTitle.textContent = 'No Stream Loaded';
            currentUrl.textContent = 'Select a station to begin';
            playbackBadge.textContent = 'Stopped';
            playbackBadge.className = 'badge';
            btnStop.disabled = true;
            
            // Large Play Button state changes to PLAY
            btnPlayStatus.title = "Play";
            playStatusIcon.setAttribute('data-lucide', 'play');
            visualizer.classList.remove('playing');
        }
        
        // Update Wi-Fi stats
        appState.wifiConnected = status.wifi.connected;
        appState.wifiMode = status.wifi.mode;
        appState.wifiSsid = status.wifi.ssid;
        appState.wifiIp = status.wifi.ip;

        // UI updates for Network Status details
        if (appState.wifiConnected) {
            netStatusText.textContent = 'Connected';
            netStatusText.className = 'val badge badge-success';
            netModeText.textContent = appState.wifiMode;
            netSsidText.textContent = appState.wifiSsid;
            netIpText.textContent = appState.wifiIp;
            
            wifiBadge.textContent = 'Connected';
            wifiBadge.className = 'badge badge-success';
            wifiMainIcon.style.color = 'var(--success)';
            wifiDetailsSsid.textContent = appState.wifiSsid;
            wifiDetailsIp.textContent = `IP: ${appState.wifiIp}`;
            wifiDetailsMode.textContent = `Mode: ${appState.wifiMode}`;
            
            // Hotspot mode warning UI
            if (appState.wifiMode === 'Hotspot') {
                hotspotBanner.style.display = 'flex';
                wifiMainIcon.style.color = 'var(--warning)';
            } else {
                hotspotBanner.style.display = 'none';
            }
        } else {
            netStatusText.textContent = 'Disconnected';
            netStatusText.className = 'val badge';
            netModeText.textContent = '-';
            netSsidText.textContent = '-';
            netIpText.textContent = '127.0.0.1';
            
            wifiBadge.textContent = 'Offline';
            wifiBadge.className = 'badge';
            wifiMainIcon.style.color = 'var(--text-muted)';
            wifiDetailsSsid.textContent = 'Not Connected';
            wifiDetailsIp.textContent = 'IP: 127.0.0.1';
            wifiDetailsMode.textContent = 'Mode: Offline';
            hotspotBanner.style.display = 'none';
        }

        // Check if there is an active background connection task that we need to restore UI for on refresh
        if (status.wifi_connect_status && status.wifi_connect_status.status === 'connecting' && !wifiTaskPollInterval) {
            pollWifiConnectionTask();
        }
        
        // Refresh grid active colors
        renderStreams();
    } catch (error) {
        // Handle Server Offline
        sidebarStatusDot.className = 'status-indicator offline';
        sidebarStatusText.textContent = 'Server Offline';
        
        appState.isPlaying = false;
        playbackBadge.textContent = 'Disconnected';
        playbackBadge.className = 'badge';
        btnStop.disabled = true;
        visualizer.classList.remove('playing');
        playStatusIcon.setAttribute('data-lucide', 'play');
    } finally {
        lucide.createIcons();
    }
}

// Play Large Button Action (Toggles current play state)
btnPlayStatus.addEventListener('click', () => {
    if (appState.isPlaying) {
        stopPlayback();
    } else {
        // Play first stream if nothing loaded, otherwise play last active
        const configId = appState.currentStreamId || (appState.streams.length > 0 ? appState.streams[0].id : null);
        if (configId) {
            playStream(configId);
        } else {
            showToast("No stations available. Add one first!", "warning");
        }
    }
});

btnStop.addEventListener('click', stopPlayback);

// ----------------------------------------------------
// Initialization
// ----------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    // Navigation routing
    navItems.forEach(item => {
        item.addEventListener('click', () => switchTab(item.dataset.tab));
    });

    // Mobile Navigation triggers
    menuToggle.addEventListener('click', toggleMobileMenu);
    navOverlay.addEventListener('click', closeMobileMenu);

    // Scan Button Trigger
    btnScanWifi.addEventListener('click', scanWifi);

    // Initial setup
    loadStreams();
    pollStatus();
    
    // Poll status every 2 seconds
    statusInterval = setInterval(pollStatus, 2000);
});
