// Theme management
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    const themeIcon = document.querySelector('.theme-icon');
    themeIcon.textContent = newTheme === 'light' ? '🌙' : '☀️';
}

function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    const themeIcon = document.querySelector('.theme-icon');
    if (themeIcon) {
        themeIcon.textContent = savedTheme === 'light' ? '🌙' : '☀️';
    }
}

loadTheme();

// Camera-specific functionality
let metadataVisible = true;

async function controlTracking(action) {
    try {
        const response = await fetch(`/api/tracking/control/${action}`, {
            method: 'POST'
        });
        const result = await response.json();
        
        showNotification(result.message, result.success ? 'success' : 'error');
        
        if (result.success) {
            updateTrackingStatus();
        }
    } catch (error) {
        console.error('Tracking control error:', error);
        showNotification('Error controlling tracking: ' + error.message, 'error');
    }
}

async function updateTrackingStatus() {
    try {
        const response = await fetch('/api/tracking/status');
        const data = await response.json();
        
        const statusEl = document.getElementById('tracking-status');
        if (data.running) {
            statusEl.className = 'status status-running';
            statusEl.textContent = 'Running';
        } else {
            statusEl.className = 'status status-stopped';
            statusEl.textContent = 'Stopped';
        }
    } catch (error) {
        console.error('Status check failed:', error);
    }
}

function updateCameraStatus() {
    fetch('/api/camera/status')
        .then(response => response.json())
        .then(data => {
            const statusEl = document.getElementById('camera-status');
            
            if (data.available) {
                statusEl.className = 'status status-running';
                statusEl.textContent = 'Online';
                
                if (metadataVisible && data.metadata) {
                    updateMetadataDisplay(data.metadata);
                }
            } else {
                statusEl.className = 'status status-stopped';
                statusEl.textContent = 'Offline';
            }
        })
        .catch(error => {
            console.error('Status check failed:', error);
            const statusEl = document.getElementById('camera-status');
            statusEl.className = 'status status-stopped';
            statusEl.textContent = 'Error';
        });
}

function updateMetadataDisplay(metadata) {
    // Face detection
    const faceEl = document.getElementById('meta-face');
    if (faceEl) {
        faceEl.textContent = metadata.face_detected ? '✓ Yes' : '✗ No';
        faceEl.style.color = metadata.face_detected ? '#10b981' : '#ef4444';
    }
    
    // Wave detection - NEW
    const waveEl = document.getElementById('meta-wave');
    if (waveEl) {
        waveEl.textContent = metadata.wave_detected ? '👋 Waving!' : 'No Wave';
        waveEl.style.color = metadata.wave_detected ? '#10b981' : '#ef4444';
        waveEl.style.fontWeight = metadata.wave_detected ? 'bold' : 'normal';
    }
    
    // Tracking state
    const trackingEl = document.getElementById('meta-tracking-state');
    if (trackingEl) {
        trackingEl.textContent = metadata.tracking_state || '-';
    }
    
    // Head position
    if (metadata.head_position) {
        const head = metadata.head_position;
        
        const panEl = document.getElementById('meta-pan');
        if (panEl) {
            panEl.textContent = `${head.pan.toFixed(1)}°`;
        }
        
        const rollEl = document.getElementById('meta-roll');
        if (rollEl) {
            rollEl.textContent = `${head.roll.toFixed(1)}°`;
        }
        
        const pitchEl = document.getElementById('meta-pitch');
        if (pitchEl) {
            pitchEl.textContent = `${head.pitch.toFixed(1)}°`;
        }
    }
    
    // Antenna mode
    const antennaEl = document.getElementById('meta-antenna');
    if (antennaEl) {
        antennaEl.textContent = metadata.antenna_mode || '-';
    }
}

function refreshCamera() {
    const img = document.getElementById('camera-feed');
    const currentSrc = img.src.split('?')[0];
    img.src = currentSrc + '?' + new Date().getTime();
}

function handleCameraError() {
    console.error('Camera feed error');
    const statusEl = document.getElementById('camera-status');
    if (statusEl) {
        statusEl.className = 'status status-stopped';
        statusEl.textContent = 'Feed Error';
    }
}

function toggleMetadata() {
    metadataVisible = !metadataVisible;
    const panel = document.getElementById('metadata-panel');
    
    if (panel) {
        if (metadataVisible) {
            panel.classList.add('visible');
            updateCameraStatus();
        } else {
            panel.classList.remove('visible');
        }
    }
}

function showNotification(message, type) {
    const toast = document.createElement('div');
    toast.style.position = 'fixed';
    toast.style.top = '80px';
    toast.style.right = '20px';
    toast.style.padding = '1rem 1.5rem';
    toast.style.borderRadius = '8px';
    toast.style.zIndex = '10000';
    toast.style.fontWeight = '600';
    toast.style.animation = 'slideIn 0.3s ease';
    
    if (type === 'success') {
        toast.style.background = 'rgba(16, 185, 129, 0.9)';
        toast.style.color = 'white';
    } else {
        toast.style.background = 'rgba(239, 68, 68, 0.9)';
        toast.style.color = 'white';
    }
    
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    updateTrackingStatus();
    updateCameraStatus();
    
    // Update status every 500ms
    setInterval(() => {
        updateTrackingStatus();
        updateCameraStatus();
    }, 500);
});