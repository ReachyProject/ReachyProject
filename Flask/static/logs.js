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

// Fetch and display logs
let lastLogCount = 0;

async function fetchLogs() {
    try {
        const response = await fetch('/api/logs');
        const result = await response.json();
        
        const logsContent = document.getElementById('logsContent');
        
        // Check if user has text selected
        const selection = window.getSelection();
        const hasSelection = selection && selection.toString().length > 0;
        
        // Check if user is scrolled to bottom (with 50px threshold)
        const isScrolledToBottom = logsContent.scrollHeight - logsContent.clientHeight <= logsContent.scrollTop + 50;
        
        // Only update if logs changed and no text is selected
        if (result.logs && result.logs.length > 0) {
            // Skip update if user is selecting text
            if (hasSelection) {
                return;
            }
            
            // Skip update if content hasn't changed
            if (result.logs.length === lastLogCount) {
                return;
            }
            
            lastLogCount = result.logs.length;
            
            // Clear existing content
            logsContent.innerHTML = '';
            
            // Create and append each log line
            result.logs.forEach(log => {
                const logDiv = document.createElement('div');
                logDiv.className = 'log-line';
                logDiv.innerHTML = richMarkupToHtml(log);
                logsContent.appendChild(logDiv);
            });
            
            // Only auto-scroll if user was already at the bottom
            if (isScrolledToBottom) {
                logsContent.scrollTop = logsContent.scrollHeight;
            }
        } else {
            logsContent.innerHTML = '<div class="logs-empty">No logs available. Start the service to see logs.</div>';
            lastLogCount = 0;
        }
    } catch (error) {
        console.error('Error fetching logs:', error);
    }
}

function richMarkupToHtml(text) {
    // Escape HTML entities first
    let html = text.replace(/&/g, '&amp;')
                   .replace(/</g, '&lt;')
                   .replace(/>/g, '&gt;');
    
    // Rich markup color/style mapping
    const styleMap = {
        // Text styles
        'bold': 'bold',
        'b': 'bold',
        'dim': 'dim',
        'd': 'dim',
        'italic': 'italic',
        'i': 'italic',
        'underline': 'underline',
        'u': 'underline',
        'strike': 'strikethrough',
        's': 'strikethrough',
        'reverse': 'reverse',
        'r': 'reverse',
        
        // Standard colors
        'black': 'black',
        'red': 'red',
        'green': 'green',
        'yellow': 'yellow',
        'blue': 'blue',
        'magenta': 'magenta',
        'cyan': 'cyan',
        'white': 'white',
        
        // Bright colors
        'bright_black': 'bright-black',
        'bright_red': 'bright-red',
        'bright_green': 'bright-green',
        'bright_yellow': 'bright-yellow',
        'bright_blue': 'bright-blue',
        'bright_magenta': 'bright-magenta',
        'bright_cyan': 'bright-cyan',
        'bright_white': 'bright-white',
        
        // Color aliases
        'grey': 'bright-black',
        'gray': 'bright-black'
    };
    
    // Stack to track open tags for proper nesting
    const tagStack = [];
    
    // Parse Rich markup tags: [style]content[/style] or [style]content[/]
    html = html.replace(/\[([^\]]+)\]([^\[]*?)(?:\[\/\1\]|\[\/\])/g, (match, styles, content) => {
        // Handle closing tag shorthand [/]
        const classes = [];
        
        // Split multiple styles (e.g., "bold cyan" or "bold red on white")
        const styleParts = styles.split(/\s+/);
        let bgColor = null;
        
        for (let i = 0; i < styleParts.length; i++) {
            const part = styleParts[i].toLowerCase();
            
            // Handle "on" for background colors (e.g., "red on white")
            if (part === 'on' && i + 1 < styleParts.length) {
                const bg = styleParts[i + 1].toLowerCase();
                if (styleMap[bg]) {
                    bgColor = styleMap[bg];
                }
                i++; // Skip the next part
                continue;
            }
            
            // Map style/color to CSS class
            if (styleMap[part]) {
                classes.push(`ansi-${styleMap[part]}`);
            }
        }
        
        // Add background color if specified
        if (bgColor) {
            classes.push(`ansi-bg-${bgColor}`);
        }
        
        if (classes.length > 0) {
            return `<span class="${classes.join(' ')}">${content}</span>`;
        }
        
        return content;
    });
    
    // Handle any remaining standalone closing tags [/]
    html = html.replace(/\[\/\]/g, '');
    
    return html;
}

async function clearLogs() {
    try {
        const response = await fetch('/api/logs/clear', {
            method: 'POST'
        });
        const result = await response.json();
        
        const logsContent = document.getElementById('logsContent');
        logsContent.innerHTML = '<div class="logs-empty">Logs cleared.</div>';
        lastLogCount = 0;
    } catch (error) {
        console.error('Error clearing logs:', error);
    }
}

// Fetch logs on page load and refresh every 2 seconds
fetchLogs();
setInterval(fetchLogs, 2000);