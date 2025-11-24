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

export async function startMacro(name) {
    if (currentMacro) {
        showNotification("A macro is already being recorded.", "error");
        return;
    }
    if (!name) name = `Macro-${macros.length + 1}`;
    currentMacro = { name, movements: [] };

    showNotification(`🎥 Started macro "${name}"`, "success");
    console.log(`[MacroRecorder] Recording started for: ${name}`);

    window.clearMovements();

    captureLoop = setInterval(function() {
        window.capturePosition();
        console.log("This will repeat.");
    }, 1000);
}

export async function stopMacro() {
    if (!currentMacro) {
        showNotification("No macro is currently recording.", "error");
        return;
    }
    clearInterval(captureLoop);
    const textarea = document.getElementById("export-output");
    const movementData = textarea ? textarea.value : "";

    const positions = window.capturedMovements || [];

    if (positions.length === 0) {
        showNotification("No movements captured to save.", "error");
        return;
    }

    // Deep copy and clamp all joint angles
    const clampedMovements = positions.map(frame => {
        const joints = frame.joints || frame;
        const clampedJoints = clampPoseAngles(joints);
        return {
            ...frame,
            joints: clampedJoints
        };
    });

    currentMacro.movements = clampedMovements;
    macros.push(currentMacro);

    console.log(`[MacroRecorder] Saved macro: ${currentMacro.name}`, currentMacro);
    showNotification(`✅ Saved macro "${currentMacro.name}"`, "success");

    currentMacro = null;
    updateMacroList();
}

async function interpolatePose(fromPose, toPose, steps = 30, duration = 800) {
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
        updateVisualization(interpolated);
        window.lastPose = interpolated;
        await new Promise(r => setTimeout(r, stepTime));
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
    showNotification(`Simulating "${name}"...`, 'success');

    const frames = macro.movements;
    if (!frames || frames.length === 0) {
        showNotification(`No movements in macro "${name}"`, 'error');
        window.isSimulating = false;
        return;
    }

    try {
       const currentPose = await getRobotPose();

        if (!currentPose) {
            showNotification("Couldn't fetch robot pose. Using neutral instead.", "error");
        }

        const defaultPose = {};
        for (const joint in window.joints) defaultPose[joint] = 0;

        await interpolatePose(currentPose || defaultPose, defaultPose, 30, 1200);
        window.lastPose = { ...defaultPose };

        const firstFrame = frames[0];
        const firstJoints = firstFrame.joints || firstFrame;
        await interpolatePose(defaultPose, firstJoints, 30, 800);
        window.lastPose = { ...firstJoints };

        let prevFrame = firstFrame;
        let globalMaxSpeed = 0;

        for (let i = 1; i < frames.length; i++) {
            const frame = frames[i];
            const jointsToApply = frame.joints || frame;

            const delay = frame.timestamp && prevFrame.timestamp
                ? (frame.timestamp - prevFrame.timestamp) / 1000
                : 0.4;

            const prevJoints = prevFrame.joints || prevFrame;
            const currJoints = jointsToApply;
            const maxSpeed = getMaxAngleChange(prevJoints, currJoints, delay);

            if (maxSpeed > globalMaxSpeed) globalMaxSpeed = maxSpeed;
            if (maxSpeed > 90) {
                console.warn(`⚠️ High joint speed detected: ${maxSpeed.toFixed(2)}°/s`);
            }

            await interpolatePose(prevJoints, currJoints, 30, delay * 1000);
            prevFrame = frame;
        }
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
    console.log(`[MacroRecorder] Executing macro on robot: ${name}`);
    showNotification(`🤖 Executing "${name}" on Reachy`, "success");

    for (const movement of macro.movements) {
        await fetch("/api/movement/goto", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ positions: movement, duration: 1.0 })
        });
        await new Promise(r => setTimeout(r, 1100)); // wait for move
    }
    showNotification(`✅ Finished executing "${name}"`, "success");
}


function updateMacroList() {
    const container = document.getElementById("macro-list");
    if (!container) return;

    container.innerHTML = "";
    if (macros.length === 0) {
        container.innerHTML = `<div style="color: var(--text-muted); text-align:center; padding:1rem;">No macros recorded</div>`;
        return;
    }
    macros.forEach(macro => {
        const div = document.createElement("div");
        div.className = "macro-item";
        div.innerHTML = `
            <div class="macro-info">
                <span>${macro.name}</span>
            </div>
            <div class="btn-group">
                <button class="btn-small btn-secondary" onclick="simulateMacro('${macro.name}')">▶️ Simulate</button>
                <button class="btn-small btn-primary" onclick="executeMacro('${macro.name}')">🤖 Execute</button>
            </div>
        `;
        container.appendChild(div);
    });
}

export function exportMacros() {
    if (macros.length === 0) {
        showNotification("No macros to export.", "error");
        return;
    }
    const text = JSON.stringify(macros, null, 2);
    navigator.clipboard.writeText(text).then(() => {
        showNotification("📋 Macros copied to clipboard!", "success");
    });
}

export function importMacros(jsonText) {
    try {
        const imported = JSON.parse(jsonText);
        if (Array.isArray(imported)) {
            macros.push(...imported);
            updateMacroList();
            showNotification("✅ Macros imported successfully", "success");
        }
    } catch (e) {
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

async function getRobotPose() {
    try {
        const res = await fetch('/api/movement/positions', { method: 'GET' });
        const data = await res.json();
        if (data?.success && data?.positions && typeof data.positions === 'object') {
            return data.positions; // { joint: deg, ... }
        }
        console.warn('[MacroRecorder] positions call returned no data:', data);
        return null;
    } catch (err) {
        console.error('[MacroRecorder] positions fetch failed:', err);
        return null;
    }
}

window.toggleMacroPopup = toggleMacroPopup;
window.startMacro = startMacro;
window.stopMacro = stopMacro;
window.simulateMacro = simulateMacro;
window.executeMacro = executeMacro;
window.exportMacros = exportMacros;
window.importMacros = importMacros;