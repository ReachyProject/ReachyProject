// macro_recorder.js
// Extends the movement recorder system without redefining its functions.
// Requires movement_recorder.js to be loaded first.

const JOINT_LIMITS = {
    'r_shoulder_pitch': [-150, 90],
    'r_shoulder_roll': [-180, 10],
    'r_arm_yaw': [-90, 90],
    'r_elbow_pitch': [-125, 0],
    'r_forearm_yaw': [-100, 100],
    'r_wrist_pitch': [-45, 45],
    'r_wrist_roll': [-55, 35],
    'r_gripper': [-50, 25],
    'l_shoulder_pitch': [-150, 90],
    'l_shoulder_roll': [-10, 180],
    'l_arm_yaw': [-90, 90],
    'l_elbow_pitch': [-125, 0],
    'l_forearm_yaw': [-100, 100],
    'l_wrist_pitch': [-45, 45],
    'l_wrist_roll': [-35, 55],
    'l_gripper': [-25, 50],
    'l_antenna': [-30, 30],
    'r_antenna': [-30, 30],
    'neck_yaw': [-45, 45],
    'neck_pitch': [-25, 25],
    'neck_roll': [-20, 20]
};

function clampJointAngle(jointName, angle) {
    const limits = JOINT_LIMITS[jointName];
    if (!limits) return angle;
    return Math.max(limits[0], Math.min(limits[1], angle));
}

function clampPoseAngles(pose) {
    const clamped = {};
    for (const joint in pose) {
        clamped[joint] = clampJointAngle(joint, pose[joint]);
    }
    return clamped;
}

const macros = [];
let currentMacro = null;
window.isSimulating = false;
let captureLoop;
let captureStartTime = null;
let macrosLoaded = false;  // Flag to prevent double-loading

// Persistent storage key
const STORAGE_KEY = 'reachy_macros';

// Load macros from localStorage on startup
function loadMacrosFromStorage() {
    // Prevent loading twice
    if (macrosLoaded) {
        console.log('[MacroRecorder] Macros already loaded, skipping');
        return;
    }
    
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
            const loaded = JSON.parse(stored);
            if (Array.isArray(loaded)) {
                // Clear existing macros first to prevent duplicates
                macros.length = 0;
                macros.push(...loaded);
                macrosLoaded = true;  // Mark as loaded
                console.log(`[MacroRecorder] Loaded ${loaded.length} macros from storage`);
                updateMacroList();
                showNotification(`📂 Loaded ${loaded.length} saved macros`, 'success');
            }
        } else {
            macrosLoaded = true;  // Mark as loaded even if no macros
        }
    } catch (e) {
        console.error('[MacroRecorder] Failed to load macros from storage:', e);
        macrosLoaded = true;  // Mark as attempted to prevent retry
    }
}

// Save macros to localStorage
function saveMacrosToStorage() {
    try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(macros));
        console.log(`[MacroRecorder] Saved ${macros.length} macros to storage`);
    } catch (e) {
        console.error('[MacroRecorder] Failed to save macros to storage:', e);
        showNotification('⚠️ Failed to save macros', 'error');
    }
}

// Load immediately if DOM already loaded, otherwise wait for DOMContentLoaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadMacrosFromStorage, { once: true });
} else {
    // DOM already loaded, load immediately
    loadMacrosFromStorage();
}

export async function startMacro(name) {
    if (currentMacro) {
        showNotification("A macro is already being recorded.", "error");
        return;
    }
    if (!name || name.trim() === '') {
        name = `Macro-${macros.length + 1}`;
    }
    
    currentMacro = { 
        name: name.trim(), 
        movements: [],
        startTime: Date.now()
    };

    showNotification(`🎥 Started macro "${currentMacro.name}"`, "success");
    console.log(`[MacroRecorder] Recording started for: ${currentMacro.name}`);

    // Force clear previous movements without confirmation
    window.capturedMovements = [];
    
    // Clear the export output if it exists
    const exportOutput = document.getElementById('export-output');
    if (exportOutput) {
        exportOutput.value = '';
    }
    
    // Clear the movement list display if the function exists
    if (typeof window.updateMovementList === 'function') {
        window.updateMovementList();
    }
    
    captureStartTime = Date.now();

    // Capture positions every second
    captureLoop = setInterval(function() {
        window.capturePosition();
    }, 1000);
}

export async function stopMacro() {
    if (!currentMacro) {
        showNotification("No macro is currently recording.", "error");
        return;
    }
    
    clearInterval(captureLoop);
    
    // Get captured movements from movement_recorder
    const positions = window.capturedMovements || [];

    if (positions.length === 0) {
        showNotification("No movements captured to save.", "error");
        currentMacro = null;
        return;
    }

    console.log('[MacroRecorder] Raw captured positions:', positions);

    // Convert to proper format with timestamps and clamping
    const baseTime = currentMacro.startTime;
    const clampedMovements = positions.map((pos, index) => {
        // Handle both formats: direct positions or {joints: ...}
        const joints = pos.joints || pos;
        const clampedJoints = clampPoseAngles(joints);
        
        return {
            timestamp: baseTime + (index * 1000), // 1 second intervals
            joints: clampedJoints
        };
    });

    currentMacro.movements = clampedMovements;
    macros.push(currentMacro);

    console.log(`[MacroRecorder] Saved macro: ${currentMacro.name}`, currentMacro);
    console.log(`[MacroRecorder] Movement count: ${clampedMovements.length}`);
    
    // Save to localStorage
    saveMacrosToStorage();
    
    showNotification(`✅ Saved macro "${currentMacro.name}" (${clampedMovements.length} frames)`, "success");

    currentMacro = null;
    captureStartTime = null;
    updateMacroList();
}

async function interpolatePose(fromPose, toPose, steps = 30, duration = 800, sendToTarget = false) {
    const allJoints = new Set([
        ...Object.keys(fromPose || {}),
        ...Object.keys(toPose || {})
    ]);
    const stepTime = duration / steps;

    for (let step = 0; step <= steps; step++) {
        const t = step / steps;
        const easedT = t * t * (3 - 2 * t);

        const interpolated = {};
        for (const joint of allJoints) {
            const startVal = fromPose?.[joint] ?? 0;
            const endVal = toPose?.[joint] ?? 0;
            const rawValue = startVal + (endVal - startVal) * easedT;
            interpolated[joint] = clampJointAngle(joint, rawValue);
        }
        
        // Apply to visualization
        updateVisualization(interpolated);
        window.lastPose = interpolated;
        
        // Send to proxy/robot if requested
        if (sendToTarget) {
            await sendPositionToTarget(interpolated);
        }
        
        await new Promise(r => setTimeout(r, stepTime));
    }
}

async function sendPositionToTarget(positions) {
    const useProxy = window.useProxy || false;
    const socket = window.proxySocket;

    if (useProxy && socket && socket.connected) {
        // Send to proxy
        socket.emit('set_multiple_joints', {
            positions: positions,
            origin: 'macro_player'
        });
    } else {
        // Send to robot API (non-blocking)
        // Note: This won't wait for robot to finish, just sends command
        try {
            fetch("/api/movement/set_positions", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ positions: positions })
            }).catch(err => {
                console.warn('[MacroRecorder] Failed to send to robot:', err);
            });
        } catch (err) {
            // Silently ignore errors during execution
        }
    }
}

async function simulateMacro(name) {
    const macro = macros.find(m => m.name === name);
    if (!macro) {
        showNotification(`Macro "${name}" not found`, 'error');
        return;
    }

    if (window.isSimulating) {
        showNotification("Simulation already in progress.", "error");
        return;
    }

    window.isSimulating = true;
    showNotification(`▶️ Simulating "${name}"...`, 'success');

    const frames = macro.movements;
    if (!frames || frames.length === 0) {
        showNotification(`No movements in macro "${name}"`, 'error');
        window.isSimulating = false;
        return;
    }

    console.log(`[MacroRecorder] Starting simulation of "${name}" with ${frames.length} frames`);

    try {
        // Get current pose or use neutral
        const currentPose = await getCurrentPose();
        const defaultPose = {};
        for (const joint in window.joints) defaultPose[joint] = 0;

        // Move to neutral first
        console.log('[MacroRecorder] Moving to neutral position...');
        await interpolatePose(currentPose || defaultPose, defaultPose, 30, 1200);
        window.lastPose = { ...defaultPose };

        // Move to first frame
        const firstFrame = frames[0];
        const firstJoints = firstFrame.joints || firstFrame;
        console.log('[MacroRecorder] Moving to start position...', firstJoints);
        await interpolatePose(defaultPose, firstJoints, 30, 800);
        window.lastPose = { ...firstJoints };

        // Play through all frames
        let prevFrame = firstFrame;
        let globalMaxSpeed = 0;

        for (let i = 1; i < frames.length; i++) {
            const frame = frames[i];
            const jointsToApply = frame.joints || frame;

            const delay = frame.timestamp && prevFrame.timestamp
                ? (frame.timestamp - prevFrame.timestamp) / 1000
                : 1.0; // Default 1 second if no timestamps

            const prevJoints = prevFrame.joints || prevFrame;
            const currJoints = jointsToApply;
            const maxSpeed = getMaxAngleChange(prevJoints, currJoints, delay);

            if (maxSpeed > globalMaxSpeed) globalMaxSpeed = maxSpeed;
            if (maxSpeed > 90) {
                console.warn(`⚠️ High joint speed detected: ${maxSpeed.toFixed(2)}°/s`);
            }

            console.log(`[MacroRecorder] Frame ${i}/${frames.length}, delay: ${delay}s`);
            await interpolatePose(prevJoints, currJoints, 30, delay * 1000);
            prevFrame = frame;
        }
        
        // Return to neutral
        console.log('[MacroRecorder] Returning to neutral...');
        await interpolatePose(prevFrame.joints || prevFrame, defaultPose, 30, 800);
        window.lastPose = { ...defaultPose };

        showNotification(
            `Macro "${name}" finished (max speed: ${globalMaxSpeed.toFixed(2)}°/s)`,
            'success'
        );
    } catch (err) {
        console.error('[Simulation] Error during macro simulation:', err);
        showNotification('Simulation error. See console for details.', 'error');
    } finally {
        window.isSimulating = false;
    }
}

export async function executeMacro(name) {
    const macro = macros.find(m => m.name === name);
    if (!macro) {
        showNotification(`Macro "${name}" not found.`, "error");
        return;
    }

    const frames = macro.movements;
    if (!frames || frames.length === 0) {
        showNotification(`No movements in macro "${name}"`, 'error');
        return;
    }

    if (window.isSimulating) {
        showNotification("Execution already in progress.", "error");
        return;
    }

    window.isSimulating = true;

    // Check if we're using proxy mode
    const useProxy = window.useProxy || false;
    const socket = window.proxySocket;

    if (useProxy && socket && socket.connected) {
        showNotification(`🖥️ Executing "${name}" on proxy with smooth interpolation`, "success");
        console.log(`[MacroRecorder] Executing macro "${name}" on proxy with ${frames.length} frames`);
    } else {
        showNotification(`🤖 Executing "${name}" on robot with smooth interpolation`, "success");
        console.log(`[MacroRecorder] Executing macro "${name}" on robot with ${frames.length} frames`);
    }

    try {
        // Get current pose or use neutral
        const currentPose = await getCurrentPose();
        const defaultPose = {};
        for (const joint in window.joints) defaultPose[joint] = 0;

        // Move to neutral first (with sending)
        console.log('[MacroExecution] Moving to neutral position...');
        await interpolatePose(currentPose || defaultPose, defaultPose, 30, 1200, true);
        window.lastPose = { ...defaultPose };

        // Move to first frame (with sending)
        const firstFrame = frames[0];
        const firstJoints = firstFrame.joints || firstFrame;
        console.log('[MacroExecution] Moving to start position...', firstJoints);
        await interpolatePose(defaultPose, firstJoints, 30, 800, true);
        window.lastPose = { ...firstJoints };

        // Play through all frames (with sending)
        let prevFrame = firstFrame;
        let globalMaxSpeed = 0;

        for (let i = 1; i < frames.length; i++) {
            const frame = frames[i];
            const jointsToApply = frame.joints || frame;

            const delay = frame.timestamp && prevFrame.timestamp
                ? (frame.timestamp - prevFrame.timestamp) / 1000
                : 1.0; // Default 1 second if no timestamps

            const prevJoints = prevFrame.joints || prevFrame;
            const currJoints = jointsToApply;
            const maxSpeed = getMaxAngleChange(prevJoints, currJoints, delay);

            if (maxSpeed > globalMaxSpeed) globalMaxSpeed = maxSpeed;
            if (maxSpeed > 90) {
                console.warn(`⚠️ High joint speed detected: ${maxSpeed.toFixed(2)}°/s`);
            }

            console.log(`[MacroExecution] Frame ${i + 1}/${frames.length}, delay: ${delay}s`);
            await interpolatePose(prevJoints, currJoints, 30, delay * 1000, true);
            prevFrame = frame;
        }
        
        // Return to neutral (with sending)
        console.log('[MacroExecution] Returning to neutral...');
        await interpolatePose(prevFrame.joints || prevFrame, defaultPose, 30, 800, true);
        window.lastPose = { ...defaultPose };

        showNotification(
            `✅ Finished "${name}" (max speed: ${globalMaxSpeed.toFixed(2)}°/s)`,
            'success'
        );
    } catch (err) {
        console.error('[MacroExecution] Error during execution:', err);
        showNotification('Execution error. See console for details.', 'error');
    } finally {
        window.isSimulating = false;
    }
}

function updateMacroList() {
    const container = document.getElementById("macro-list");
    if (!container) return;

    container.innerHTML = "";
    if (macros.length === 0) {
        container.innerHTML = `<div style="color: var(--text-muted); text-align:center; padding:1rem;">No macros recorded</div>`;
        return;
    }
    
    macros.forEach((macro, index) => {
        const frameCount = macro.movements ? macro.movements.length : 0;
        const div = document.createElement("div");
        div.className = "macro-item";
        div.innerHTML = `
            <div class="macro-info">
                <span style="font-weight: 500;">${macro.name}</span>
                <span style="font-size: 0.85em; color: var(--text-muted);">${frameCount} frames</span>
            </div>
            <div class="btn-group">
                <button class="btn-small btn-secondary" onclick="simulateMacro('${macro.name}')">▶️ Simulate</button>
                <button class="btn-small btn-primary" onclick="executeMacro('${macro.name}')">🤖 Execute</button>
                <button class="btn-small btn-danger" onclick="deleteMacro(${index})">🗑️ Trash</button>
            </div>
        `;
        container.appendChild(div);
    });
}

function deleteMacro(index) {
    if (index < 0 || index >= macros.length) return;
    
    const macro = macros[index];
    if (confirm(`Delete macro "${macro.name}"?`)) {
        macros.splice(index, 1);
        saveMacrosToStorage();  // Save after deletion
        updateMacroList();
        showNotification(`Deleted macro "${macro.name}"`, 'success');
    }
}

function clearAllMacros() {
    if (macros.length === 0) {
        showNotification("No macros to clear", "error");
        return;
    }
    
    if (confirm(`Delete ALL ${macros.length} macros? This cannot be undone!`)) {
        macros.length = 0;  // Clear array
        saveMacrosToStorage();
        updateMacroList();
        showNotification("🗑️ All macros deleted", "success");
    }
}

async function loadExampleMacros() {
    const examples = [
        '/static/macro_crowd_wave.json',
        '/static/macro_greeting_hello.json',
        '/static/macro_hands_in_air.json'
    ];
    
    let loadedCount = 0;
    let errorCount = 0;
    
    for (const url of examples) {
        try {
            const response = await fetch(url);
            if (!response.ok) {
                console.error(`Failed to fetch ${url}: ${response.statusText}`);
                errorCount++;
                continue;
            }
            const data = await response.json();
            
            // Check if this macro already exists (by name)
            const macroName = data[0]?.name;
            if (macroName && macros.some(m => m.name === macroName)) {
                console.log(`[Examples] Skipping "${macroName}" - already exists`);
                continue;
            }
            
            // Import the macro
            if (Array.isArray(data) && data.length > 0) {
                macros.push(...data);
                loadedCount++;
            }
        } catch (e) {
            console.error(`Failed to load ${url}:`, e);
            errorCount++;
        }
    }
    
    if (loadedCount > 0) {
        saveMacrosToStorage();
        updateMacroList();
        showNotification(`📚 Loaded ${loadedCount} example macros`, 'success');
    } else if (errorCount > 0) {
        showNotification(`❌ Failed to load examples (${errorCount} errors)`, 'error');
    } else {
        showNotification(`ℹ️ All examples already loaded`, 'info');
    }
}

export function exportMacros() {
    if (macros.length === 0) {
        showNotification("No macros to export.", "error");
        return;
    }
    const text = JSON.stringify(macros, null, 2);
    navigator.clipboard.writeText(text).then(() => {
        showNotification("📋 Macros copied to clipboard!", "success");
    }).catch(err => {
        console.error('Clipboard error:', err);
        // Fallback: show in alert
        alert('Copy this JSON:\n\n' + text);
    });
}

export function importMacros(jsonText) {
    try {
        const imported = JSON.parse(jsonText);
        if (Array.isArray(imported)) {
            macros.push(...imported);
            saveMacrosToStorage();  // Save after import
            updateMacroList();
            showNotification(`✅ Imported ${imported.length} macros`, "success");
        } else {
            showNotification("❌ Invalid format: expected array", "error");
        }
    } catch (e) {
        console.error('Import error:', e);
        showNotification("❌ Invalid JSON format", "error");
    }
}

function toggleMacroPopup() {
    const popup = document.getElementById('macro-popup');
    if (!popup) {
        console.warn('[Macro Recorder] No macro-popup element found.');
        return;
    }

    const isVisible = popup.style.display === 'block';
    popup.style.display = isVisible ? 'none' : 'block';
}

function getMaxAngleChange(prevJoints, currJoints, deltaT) {
    if (deltaT <= 0) return 0;
    let maxSpeed = 0;
    for (const joint in currJoints) {
        if (joint in prevJoints) {
            const deltaAngle = Math.abs(currJoints[joint] - prevJoints[joint]);
            const speed = deltaAngle / deltaT; // degrees per second
            if (speed > maxSpeed) maxSpeed = speed;
        }
    }
    return maxSpeed;
}

async function getCurrentPose() {
    // Try to get from proxy first
    if (window.useProxy) {
        try {
            const response = await fetch('http://10.24.13.51:5001/state');
            const data = await response.json();
            if (data.success && data.positions) {
                return data.positions;
            }
        } catch (err) {
            console.warn('[MacroRecorder] Could not get proxy state:', err);
        }
    }
    
    // Try to get from robot API
    try {
        const res = await fetch('/api/movement/positions', { method: 'GET' });
        const data = await res.json();
        if (data?.success && data?.positions && typeof data.positions === 'object') {
            return data.positions;
        }
    } catch (err) {
        console.warn('[MacroRecorder] Could not get robot positions:', err);
    }
    
    // Fallback: return current visualization state
    if (window.lastPose) {
        return window.lastPose;
    }
    
    return null;
}

// Export functions to window
window.toggleMacroPopup = toggleMacroPopup;
window.startMacro = startMacro;
window.stopMacro = stopMacro;
window.simulateMacro = simulateMacro;
window.executeMacro = executeMacro;
window.exportMacros = exportMacros;
window.importMacros = importMacros;
window.deleteMacro = deleteMacro;
window.clearAllMacros = clearAllMacros;
window.loadExampleMacros = loadExampleMacros;
window.saveMacrosToStorage = saveMacrosToStorage;
window.loadMacrosFromStorage = loadMacrosFromStorage;
window.macros = macros;  // Expose for debugging