import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
/* import { EXRLoader } from "three/addons/loaders/EXRLoader.js"; */

// Theme management
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';

    document.documentElement.setAttribute('data-theme', newTheme);
    try {
        localStorage.setItem('theme', newTheme);
    } catch (e) {
        // localStorage may be unavailable; fail silently
    }

    const themeIcon = document.querySelector('.theme-icon');
    if (themeIcon) {
        themeIcon.textContent = newTheme === 'light' ? '🌙' : '☀️';
    }
}

function loadTheme() {
    let savedTheme = 'dark';
    try {
        const storedTheme = localStorage.getItem('theme');
        if (storedTheme === 'light' || storedTheme === 'dark') {
            savedTheme = storedTheme;
        }
    } catch (e) {
        // localStorage may be unavailable; use default
    }
    document.documentElement.setAttribute('data-theme', savedTheme);

    const themeIcon = document.querySelector('.theme-icon');
    if (themeIcon) {
        themeIcon.textContent = savedTheme === 'light' ? '🌙' : '☀️';
    }
}

loadTheme();

// Joint name mapping: API names -> GLB joint names
const JOINT_NAME_MAP = {
    'r_shoulder_pitch': 'right_shoulder_pitch_joint',
    'r_shoulder_roll': 'right_shoulder_roll_joint',
    'r_arm_yaw': 'right_arm_yaw_joint',
    'r_elbow_pitch': 'right_elbow_pitch_joint',
    'r_forearm_yaw': 'right_forearm_yaw_joint',
    'r_wrist_pitch': 'right_wrist_pitch_joint',
    'r_wrist_roll': 'right_wrist_roll_joint',
    'r_gripper': 'right_gripper_joint',
    'l_shoulder_pitch': 'left_shoulder_pitch_joint',
    'l_shoulder_roll': 'left_shoulder_roll_joint',
    'l_arm_yaw': 'left_arm_yaw_joint',
    'l_elbow_pitch': 'left_elbow_pitch_joint',
    'l_forearm_yaw': 'left_forearm_yaw_joint',
    'l_wrist_pitch': 'left_wrist_pitch_joint',
    'l_wrist_roll': 'left_wrist_roll_joint',
    'l_gripper': 'left_gripper_joint',
    'l_antenna': 'left_ear_joint',
    'r_antenna': 'right_ear_joint',
    'neck_yaw': 'neck_joint',
    'neck_pitch': 'neck_joint',
    'neck_roll': 'neck_joint'
};

// Three.js Scene Setup
let scene, camera, renderer, robot, controls;
let joints = {};
let jointStates = {};
let capturedMovements = [];
let isFullscreen = false;

// Joint offsets to match GLB zero pose to robot's physical zero pose
const JOINT_OFFSETS = {
    'r_shoulder_pitch': 90,
    'l_shoulder_pitch': -90,
    'r_shoulder_roll': 90,
    'l_shoulder_roll': -90,
};

// Store accumulated neck rotations since the neck_joint handles all three axes
let neckRotations = {
    yaw: 0,
    pitch: 0,
    roll: 0
};

function initScene() {
    const container = document.getElementById('canvas-container');
    // Load EXR environment
/*     const exrLoader = new EXRLoader();
    exrLoader.load('/static/room.exr', (texture) => {
        texture.mapping = THREE.EquirectangularReflectionMapping;
        scene.environment = texture;
        scene.background = texture; // Optional: show as background
        
        console.log('[3D] EXR environment loaded');
    }); */

    // Scene setup (Standard Three.js Y-up)
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x333333);

    // Camera setup - closer FOV for zoomed view
    camera = new THREE.PerspectiveCamera(
        35,  // Reduced FOV from 50 to zoom in
        container.clientWidth / container.clientHeight,
        0.1,
        100
    );
    camera.position.set(0, 1.5, 2);  // Adjusted position

    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);

    // OrbitControls
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.enablePan = true;
    controls.mouseButtons = {
        LEFT: THREE.MOUSE.ROTATE,
        MIDDLE: THREE.MOUSE.ROTATE,
        RIGHT: THREE.MOUSE.PAN
    };
    controls.target.set(0, 1, 0);  // Look at upper body/head
    controls.update();

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.6);
    directionalLight.position.set(5, 10, 7.5);
    scene.add(directionalLight);

    // Grid (standard XZ plane)
    const grid = new THREE.GridHelper(10, 20, 0x3a3a3a, 0x555555);
    scene.add(grid);

    // Load Reachy GLB model
    loadReachyModel();

    // Handle window resize
    window.addEventListener('resize', () => {
        if (!isFullscreen) {
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
        }
    });

    animate();
}

function loadReachyModel() {
    const loader = new GLTFLoader();

    loader.load(
        "/static/reachy.glb",
        (gltf) => {
            robot = gltf.scene;
            scene.add(robot);

            // Center the model
            const box = new THREE.Box3().setFromObject(robot);
            const center = new THREE.Vector3();
            box.getCenter(center);
            robot.position.sub(center);
            robot.position.y += 0.8;

            // Rotate 90° to face camera
            robot.rotation.y = -Math.PI / 2;

            // Gather joint references from GLB
            robot.traverse((obj) => {
                const name = obj.name.toLowerCase();

                // Check if this is one of our known joints
                for (const [apiName, glbName] of Object.entries(JOINT_NAME_MAP)) {
                    if (name === glbName.toLowerCase()) {
                        // For neck joints, store the same joint object for all three
                        if (apiName === 'neck_yaw' || apiName === 'neck_pitch' || apiName === 'neck_roll') {
                            joints[apiName] = obj;
                        } else {
                            joints[apiName] = obj;
                        }

                        // Set rotation order to match Blender
                        if (obj.rotation) {
                            obj.rotation.order = 'XYZ';
                        }
                        break;
                    }
                }
            });

            console.log('[3D] Reachy loaded with', Object.keys(joints).length, 'joints');
        },
        undefined,
        (error) => {
            console.error('[3D] Error loading Reachy:', error);
        }
    );
}

function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
}

function toggleFullscreen() {
    const container = document.getElementById('canvas-container');
    const button = document.getElementById('fullscreen-btn');
    
    if (!isFullscreen) {
        // Enter fullscreen
        if (container.requestFullscreen) {
            container.requestFullscreen();
        } else if (container.webkitRequestFullscreen) {
            container.webkitRequestFullscreen();
        } else if (container.msRequestFullscreen) {
            container.msRequestFullscreen();
        }
        isFullscreen = true;
        button.textContent = '⇲ Exit Fullscreen';
        
        // Resize renderer to fullscreen
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    } else {
        // Exit fullscreen
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        } else if (document.msExitFullscreen) {
            document.msExitFullscreen();
        }
        isFullscreen = false;
        button.textContent = '⇱ Fullscreen';
        
        // Resize back to container
        camera.aspect = container.clientWidth / container.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(container.clientWidth, container.clientHeight);
    }
}

// Listen for fullscreen changes
document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement) {
        const container = document.getElementById('canvas-container');
        const button = document.getElementById('fullscreen-btn');
        isFullscreen = false;
        button.textContent = '⇱ Fullscreen';
        camera.aspect = container.clientWidth / container.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(container.clientWidth, container.clientHeight);
    }
});

// API Communication
async function startCompliantMode() {
    try {
        const response = await fetch('/api/movement/start-compliant', {
            method: 'POST'
        });
        const result = await response.json();

        if (result.success) {
            if (result.initial_positions) {
                updateVisualization(result.initial_positions);
            }

            showNotification('Compliant mode activated', 'success');
            updateConnectionStatus(true);
            startPositionUpdates();
        } else {
            showNotification('Failed to start: ' + result.message, 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

async function stopCompliantMode() {
    try {
        const response = await fetch('/api/movement/stop-compliant', {
            method: 'POST'
        });
        const result = await response.json();

        if (result.success) {
            showNotification('Robot stiffened - safe to leave', 'success');

            if (result.stiffened_joints) {
                result.stiffened_joints.forEach(jointName => {
                    updateJointUI(jointName, true);
                });
            }
        } else {
            showNotification('Failed to stop: ' + result.message, 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

async function emergencyStop() {
    try {
        const response = await fetch('/api/movement/emergency-stop', {
            method: 'POST'
        });
        const result = await response.json();

        showNotification('EMERGENCY STOP ACTIVATED', 'error');
        updateConnectionStatus(false);

        if (result.stiffened_joints) {
            result.stiffened_joints.forEach(jointName => {
                updateJointUI(jointName, true);
            });
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

async function toggleJointLock(jointName, locked) {
    try {
        const response = await fetch('/api/movement/toggle-joint', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ joint: jointName, locked: locked })
        });
        const result = await response.json();

        if (result.success) {
            jointStates[jointName] = locked;
            updateJointUI(jointName, locked);
        }
    } catch (error) {
        console.error('Error toggling joint:', error);
    }
}

let positionUpdateInterval = null;

function startPositionUpdates() {
    if (positionUpdateInterval) return;

    positionUpdateInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/movement/positions');
            const data = await response.json();

            if (data.success) {
                updateVisualization(data.positions);
                updateJointValues(data.positions);
            }
        } catch (error) {
            console.error('[ERROR] Position fetch failed:', error);
        }
    }, 100);
}

function stopPositionUpdates() {
    if (positionUpdateInterval) {
        clearInterval(positionUpdateInterval);
        positionUpdateInterval = null;
    }
}

function updateVisualization(positions) {
    const DEG_TO_RAD = Math.PI / 180;

    // Update neck rotations if any neck joint changed
    if ('neck_yaw' in positions) {
        neckRotations.yaw = positions.neck_yaw * DEG_TO_RAD;
    }
    if ('neck_pitch' in positions) {
        neckRotations.pitch = positions.neck_pitch * DEG_TO_RAD;
    }
    if ('neck_roll' in positions) {
        neckRotations.roll = positions.neck_roll * DEG_TO_RAD;
    }

    for (const [jointName, angleDeg] of Object.entries(positions)) {
        const offset = JOINT_OFFSETS[jointName] || 0;
        const angleRad = (angleDeg + offset) * DEG_TO_RAD;
        const joint = joints[jointName];

        if (!joint) continue;

        // Handle Orbita spherical neck joint
        // The Orbita joint is a spherical joint where all three axes interact
        // We need to apply rotations in the correct order and account for coupling
        if (jointName === 'neck_yaw' || jointName === 'neck_pitch' || jointName === 'neck_roll') {
            // Only update when we process neck_yaw (to avoid updating 3 times)
            if (jointName === 'neck_yaw') {
                // Apply intrinsic rotations: Yaw -> Pitch -> Roll
                // This matches how the Orbita actuates
                
                // Create rotation matrix from Euler angles
                // Note: These mappings may need adjustment based on testing
                joint.rotation.order = 'YXZ';  // Yaw-Pitch-Roll order
                joint.rotation.y = neckRotations.yaw;   // Yaw (around vertical)
                joint.rotation.x = neckRotations.pitch; // Pitch (nod up/down)
                joint.rotation.z = neckRotations.roll;  // Roll (tilt side to side)
            }
            continue;
        }

        // All other joints
        if (jointName.includes('shoulder_pitch')) {
            joint.rotation.y = -angleRad;
        }
        else if (jointName.includes('shoulder_roll')) {
            joint.rotation.y = -angleRad;
        }
        else if (jointName.includes('arm_yaw')) {
            joint.rotation.y = -angleRad;
        }
        else if (jointName.includes('elbow_pitch')) {
            joint.rotation.y = -angleRad;
        }
        else if (jointName.includes('forearm_yaw')) {
            joint.rotation.y = angleRad;
        }
        else if (jointName.includes('wrist_pitch')) {
            joint.rotation.y = -angleRad;
        }
        else if (jointName.includes('wrist_roll')) {
            joint.rotation.y = -angleRad;
        }
        else if (jointName.includes('gripper')) {
            joint.rotation.y = angleRad;
        }
        else if (jointName.includes('antenna')) {
            joint.rotation.y = angleRad;
        }
    }
}

function updateJointValues(positions) {
    for (const [jointName, angle] of Object.entries(positions)) {
        const valueElement = document.getElementById(`value-${jointName}`);
        if (valueElement) {
            valueElement.textContent = `${angle.toFixed(2)}°`;
        }
    }
}

async function capturePosition() {
    try {
        const response = await fetch('/api/movement/capture');
        const data = await response.json();

        if (data.success) {
            capturedMovements.push(data.positions);
            updateMovementList();
            showNotification('Position captured', 'success');
        }
    } catch (error) {
        showNotification('Error capturing position: ' + error.message, 'error');
    }
}

function updateMovementList() {
    const container = document.getElementById('movement-list');

    if (capturedMovements.length === 0) {
        container.innerHTML = '<div style="color: var(--text-muted); text-align: center; padding: 2rem;">No movements captured yet</div>';
        return;
    }

    container.innerHTML = '';
    capturedMovements.forEach((movement, index) => {
        const div = document.createElement('div');
        div.className = 'movement-item';
        div.innerHTML = `
            <span>Position ${index + 1}</span>
            <button class="remove-movement" onclick="removeMovement(${index})">Remove</button>
        `;
        container.appendChild(div);
    });
}

function removeMovement(index) {
    capturedMovements.splice(index, 1);
    updateMovementList();
    exportMovements();
}

function clearMovements() {
    if (capturedMovements.length === 0) return;

    if (confirm('Clear all captured movements?')) {
        capturedMovements = [];
        updateMovementList();
        document.getElementById('export-output').value = '';
    }
}

function exportMovements() {
    if (capturedMovements.length === 0) {
        document.getElementById('export-output').value = 'No movements to export';
        return;
    }

    let code = '# Generated movement sequence for Reachy\n';
    code += '# Copy this code and adjust durations as needed\n\n';
    code += 'from reachy_sdk import ReachySDK\n';
    code += 'from reachy_sdk.trajectory import goto\n';
    code += 'from reachy_sdk.trajectory.interpolation import InterpolationMode\n';
    code += 'import time\n\n';
    code += 'reachy = ReachySDK(host="localhost")\n';
    code += 'reachy.turn_on("r_arm")\n';
    code += 'reachy.turn_on("l_arm")\n';
    code += 'reachy.turn_on("head")\n\n';

    capturedMovements.forEach((movement, index) => {
        code += `# Position ${index + 1}\n`;

        const armJoints = {};
        const antennaJoints = {};
        const neckJoints = {};

        for (const [joint, angle] of Object.entries(movement)) {
            if (joint.includes('antenna')) {
                antennaJoints[joint] = angle;
            } else if (joint.startsWith('neck_')) {
                neckJoints[joint] = angle;
            } else {
                armJoints[joint] = angle;
            }
        }

        if (Object.keys(armJoints).length > 0) {
            code += 'goto(\n';
            code += '    goal_positions={\n';

            for (const [joint, angle] of Object.entries(armJoints)) {
                let prefix = '';
                if (joint.startsWith('r_')) {
                    prefix = 'reachy.r_arm.';
                } else if (joint.startsWith('l_')) {
                    prefix = 'reachy.l_arm.';
                }
                code += `        ${prefix}${joint}: ${angle.toFixed(2)},\n`;
            }

            code += '    },\n';
            code += '    duration=1.0,  # Adjust this duration as needed\n';
            code += '    interpolation_mode=InterpolationMode.MINIMUM_JERK\n';
            code += ')\n';
        }

        if (Object.keys(neckJoints).length > 0) {
            code += 'goto(\n';
            code += '    goal_positions={\n';

            for (const [joint, angle] of Object.entries(neckJoints)) {
                code += `        reachy.head.${joint}: ${angle.toFixed(2)},\n`;
            }

            code += '    },\n';
            code += '    duration=1.0,\n';
            code += '    interpolation_mode=InterpolationMode.MINIMUM_JERK\n';
            code += ')\n';
        }

        for (const [joint, angle] of Object.entries(antennaJoints)) {
            code += `reachy.head.${joint}.goal_position = ${angle.toFixed(2)}\n`;
        }

        code += 'time.sleep(0.1)  # Small pause between movements\n\n';
    });

    code += '# Safely turn off the robot\n';
    code += 'reachy.turn_off_smoothly("r_arm")\n';
    code += 'reachy.turn_off_smoothly("l_arm")\n';
    code += 'reachy.turn_off_smoothly("head")\n';

    document.getElementById('export-output').value = code;
}

function copyToClipboard() {
    const textarea = document.getElementById('export-output');
    if (!textarea.value || textarea.value === 'No movements to export') {
        showNotification('Nothing to copy', 'error');
        return;
    }

    textarea.select();
    document.execCommand('copy');
    showNotification('Copied to clipboard', 'success');
}

function lockAll() {
    for (const jointName in jointStates) {
        toggleJointLock(jointName, true);
    }
}

function unlockAll() {
    for (const jointName in jointStates) {
        toggleJointLock(jointName, false);
    }
}

function updateJointUI(jointName, locked) {
    const button = document.getElementById(`lock-${jointName}`);
    if (button) {
        button.className = `lock-toggle ${locked ? 'locked' : 'unlocked'}`;
        button.textContent = locked ? '🔒 Locked' : '🔓 Unlocked';
    }
}

function updateConnectionStatus(connected) {
    const status = document.getElementById('connection-status');
    if (connected) {
        status.className = 'status-indicator status-connected';
        status.textContent = 'Connected';
    } else {
        status.className = 'status-indicator status-disconnected';
        status.textContent = 'Disconnected';
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

async function initializeJointControls() {
    try {
        const response = await fetch('/api/movement/joints');
        const data = await response.json();

        if (data.success) {
            const container = document.getElementById('joint-controls');
            container.innerHTML = '';

            data.joints.forEach(jointName => {
                jointStates[jointName] = false;

                const div = document.createElement('div');
                div.className = 'joint-item';
                div.innerHTML = `
                    <div class="joint-info">
                        <div class="joint-name">${jointName}</div>
                        <div class="joint-value" id="value-${jointName}">0.00°</div>
                    </div>
                    <button 
                        id="lock-${jointName}" 
                        class="lock-toggle locked"
                        data-joint="${jointName}"
                    >
                        🔓 Locked
                    </button>
                `;
                container.appendChild(div);
                
                // Add event listener instead of inline onclick
                const button = div.querySelector(`#lock-${jointName}`);
                button.addEventListener('click', () => {
                    toggleJointLock(jointName, !jointStates[jointName]);
                });
            });

            console.log('[INIT] Joint controls ready');
        }
    } catch (error) {
        console.error('[INIT] Error loading joints:', error);
    }
}

window.testAnimation = function () {
    const testPose = {
        r_shoulder_pitch: -45, r_shoulder_roll: -30, r_arm_yaw: 15, r_elbow_pitch: -90,
        r_forearm_yaw: 20, r_wrist_pitch: 10, l_shoulder_pitch: -20, l_elbow_pitch: -60,
        neck_yaw: 25, neck_pitch: -15, neck_roll: 10, l_antenna: 15, r_antenna: -15
    };
    updateVisualization(testPose);
    console.log('Applied test pose to visualization.');
};

async function connectToReachyTest() {
    try {
        const response = await fetch('/api/movement/start-compliant', {
            method: 'POST'
        });
        const result = await response.json();

        if (result.success) {
            if (result.initial_positions) {
                updateVisualization(result.initial_positions);
                startPositionUpdates();
            }

            showNotification('Connected to Reachy', 'success');
            updateConnectionStatus(true);
        } else {
            showNotification('Failed to connect: ' + result.message, 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

// Make functions globally accessible
window.toggleTheme = toggleTheme;
window.toggleFullscreen = toggleFullscreen;
window.startCompliantMode = startCompliantMode;
window.stopCompliantMode = stopCompliantMode;
window.emergencyStop = emergencyStop;
window.toggleJointLock = toggleJointLock;
window.capturePosition = capturePosition;
window.removeMovement = removeMovement;
window.clearMovements = clearMovements;
window.exportMovements = exportMovements;
window.copyToClipboard = copyToClipboard;
window.lockAll = lockAll;
window.unlockAll = unlockAll;

// Initialize everything
document.addEventListener('DOMContentLoaded', () => {
    initScene();
    initializeJointControls();
    connectToReachyTest();
});