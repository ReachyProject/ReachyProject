// Theme management
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    
    // Update theme icon
    const themeIcon = document.querySelector('.theme-icon');
    themeIcon.textContent = newTheme === 'light' ? '🌙' : '☀️';
}

// Load saved theme on page load
function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    const themeIcon = document.querySelector('.theme-icon');
    if (themeIcon) {
        themeIcon.textContent = savedTheme === 'light' ? '🌙' : '☀️';
    }
}

// Load theme immediately
loadTheme();

// Update age ranges based on persona
document.getElementById('persona').addEventListener('change', function() {
    const ageSelect = document.getElementById('age_range');
    const persona = this.value;
    
    ageSelect.innerHTML = '<option value="">Select Age Range</option>';
    
    if (persona && ageRanges[persona]) {
        ageSelect.disabled = false;
        ageRanges[persona].forEach(range => {
            const option = document.createElement('option');
            option.value = range;
            option.textContent = range;
            ageSelect.appendChild(option);
        });
    } else {
        ageSelect.disabled = true;
    }

    // Automatically update voice ID when persona changes
    if (persona && voiceMappings[persona]) {
        const voiceId = voiceMappings[persona];
        console.log(`Selected persona: ${persona}, Voice ID: ${voiceId}`);

        // Send the new voice ID to backend
        fetch('/update_voice', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ VOICE_ID: voiceId })
        })
        .then(res => res.json())
        .then(result => {
            console.log(result.message);
            showMessage(result.message, result.success ? 'success' : 'error');
        })
        .catch(err => {
            console.error('Error updating voice:', err);
        });
    }
});


// Update models based on provider
document.getElementById('llm_provider').addEventListener('change', function() {
    const modelSelect = document.getElementById('llm_model');
    const provider = this.value;
    
    modelSelect.innerHTML = '<option value="">Select Model</option>';
    
    if (provider && llmModels[provider]) {
        modelSelect.disabled = false;
        llmModels[provider].forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            modelSelect.appendChild(option);
        });
    } else {
        modelSelect.disabled = true;
    }
});

// Handle form submission
document.getElementById('configForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const formData = {
        persona: document.getElementById('persona').value,
        age_range: document.getElementById('age_range').value,
        mood: document.getElementById('mood').value,
        llm_provider: document.getElementById('llm_provider').value,
        llm_model: document.getElementById('llm_model').value
    };

    try {
        const response = await fetch('/save_config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });

        const result = await response.json();
        showMessage(result.message, result.success ? 'success' : 'error');
    } catch (error) {
        showMessage('Error saving configuration: ' + error.message, 'error');
    }
});

// Service control
async function controlService(action) {
    try {
        const response = await fetch(`/service/${action}`, {
            method: 'POST'
        });

        const result = await response.json();
        showMessage(result.message, result.success ? 'success' : 'error');
        
        if (result.success) {
            updateStatus();
        }
    } catch (error) {
        showMessage('Error controlling service: ' + error.message, 'error');
    }
}

// Update service status
async function updateStatus() {
    try {
        const response = await fetch('/service/status');
        const result = await response.json();
        
        const statusElement = document.getElementById('status');
        if (result.running) {
            statusElement.textContent = 'Running';
            statusElement.className = 'status status-running';
        } else {
            statusElement.textContent = 'Stopped';
            statusElement.className = 'status status-stopped';
        }
    } catch (error) {
        console.error('Error checking status:', error);
    }
}

// Show message
function showMessage(text, type) {
    const messageEl = document.getElementById('message');
    messageEl.textContent = text;
    messageEl.className = `message ${type} show`;
    
    setTimeout(() => {
        messageEl.classList.remove('show');
    }, 5000);
}

// Check status on load and periodically
updateStatus();
setInterval(updateStatus, 3000);