// Theme management (reused from other pages)
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
let metadataVisible = false;

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
    
    // Tracking state
    const trackingEl = document.getElementById('meta-tracking');
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
    // Add timestamp to force reload without flickering
    const timestamp = new Date().getTime();
    const baseUrl = '/api/camera/feed';
    img.src = `${baseUrl}?t=${timestamp}`;
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

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Update status immediately and then every 2 seconds
    updateCameraStatus();
    setInterval(updateCameraStatus, 2000);
});