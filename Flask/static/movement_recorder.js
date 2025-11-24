import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { EXRLoader } from "three/addons/loaders/EXRLoader.js";

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

// Add this near the top with other global variables
let initialCameraPosition = { x: 0, y: 1, z: 2.5 };
let initialControlsTarget = { x: 0, y: 0.85, z: 0 };

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
    const exrLoader = new EXRLoader();
    exrLoader.load('/static/room.exr', (texture) => {
        texture.mapping = THREE.EquirectangularReflectionMapping;
        scene.environment = texture;
        scene.background = texture;

        console.log('[3D] EXR environment loaded');
    });

    // Scene setup
    scene = new THREE.Scene();

    // Camera setup
    camera = new THREE.PerspectiveCamera(
        30,
        container.clientWidth / container.clientHeight,
        0.1,
        100
    );
    camera.position.set(initialCameraPosition.x, initialCameraPosition.y, initialCameraPosition.z);

    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio); // Add this for better quality
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
    controls.target.set(initialControlsTarget.x, initialControlsTarget.y, initialControlsTarget.z);
    controls.update();

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.6);
    directionalLight.position.set(5, 10, 7.5);
    scene.add(directionalLight);

    // Grid
    const grid = new THREE.GridHelper(10, 20, 0x3a3a3a, 0x555555);
    scene.add(grid);

    // Load Reachy GLB model
    loadReachyModel();

    // Handle window resize
    window.addEventListener('resize', onWindowResize);

    animate();
}

function onWindowResize() {
    const container = document.getElementById('canvas-container');

    if (isFullscreen) {
        // Use window dimensions in fullscreen
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    } else {
        // Use container dimensions normally
        camera.aspect = container.clientWidth / container.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(container.clientWidth, container.clientHeight);
    }
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
            robot.position.y += 0.7;
            robot.position.z += 0.1
            robot.position.x -= 0.05;

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
                            joints['neck_yaw'] = obj;
                            joints['neck_pitch'] = obj;
                            joints['neck_roll'] = obj;
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

             setTimeout(() => {
                initMeshCollisionDetection();
            }, 100); // Small delay to ensure all joints are set up

            document.getElementById('loading-screen').style.display = "none";
            console.log('[3D] Reachy loaded with', Object.keys(joints).length, 'joints');
        },
        undefined,
        (error) => {
            console.error('[3D] Error loading Reachy:', error);
        }
    );
}

let collisionCheckCounter = 0;
const COLLISION_CHECK_INTERVAL = 3; // Check every 3 frames


function animate() {
    requestAnimationFrame(animate);
    controls.update();

    // Throttled collision checking
    if (robot && robotMeshes.length > 0) {
        collisionCheckCounter++;
        if (collisionCheckCounter >= COLLISION_CHECK_INTERVAL) {
            const collisions = checkMeshCollisions();
            visualizeCollision(collisions);
            collisionCheckCounter = 0;
        }
    }
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
    } else {
        // Exit fullscreen
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
            document.webkitExitFullscreen();
        } else if (document.msExitFullscreen) {
            document.msExitFullscreen();
        }
    }
}

// Listen for fullscreen changes
document.addEventListener('fullscreenchange', handleFullscreenChange);
document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
document.addEventListener('mozfullscreenchange', handleFullscreenChange);
document.addEventListener('msfullscreenchange', handleFullscreenChange);

function handleFullscreenChange() {
    const button = document.getElementById('fullscreen-btn');
    const container = document.getElementById('canvas-container');

    if (document.fullscreenElement || document.webkitFullscreenElement ||
        document.mozFullScreenElement || document.msFullscreenElement) {
        // Entered fullscreen
        isFullscreen = true;
        button.textContent = '⇲ Exit Fullscreen';

        // Update renderer to fullscreen dimensions
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    } else {
        // Exited fullscreen
        isFullscreen = false;
        button.textContent = '⇱ Fullscreen';

        // Update renderer back to container dimensions
        camera.aspect = container.clientWidth / container.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(container.clientWidth, container.clientHeight);
    }
}

function resetCamera() {
    // Smoothly animate camera back to initial position
    camera.position.set(initialCameraPosition.x, initialCameraPosition.y, initialCameraPosition.z);
    controls.target.set(initialControlsTarget.x, initialControlsTarget.y, initialControlsTarget.z);
    controls.update();

    showNotification('Camera view reset', 'success');
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

            if (data.success && !window.isSimulating) {
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

        // Head joints
        if (jointName.includes('neck_yaw') || jointName.includes('neck_pitch') || jointName.includes('neck_roll')) {
            joint.rotation.order = 'YXZ';
            joint.rotation.y = neckRotations.yaw;
            joint.rotation.x = neckRotations.pitch;
            joint.rotation.z = neckRotations.roll;
        }
        // All other joints
        else if (jointName.includes('shoulder_pitch')) {
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
    if (useProxy) {
        try {
            const response = await fetch('http://localhost:5001/state');
            const data = await response.json();
            if (data.success) {
                capturedMovements.push(data.positions);
                console.log(data.positions);
                updateMovementList();
                showNotification('Position captured', 'success');
            }
        } catch (error) {
            showNotification('Error capturing proxy position: ' + error.message, 'error');
        }
    } else {
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

async function copyToClipboard() {
    const textarea = document.getElementById('export-output');
    if (!textarea.value || textarea.value === 'No movements to export') {
        showNotification('Nothing to copy', 'error');
        return;
    }

    try {
        await navigator.clipboard.writeText(textarea.value);
        showNotification('Copied to clipboard', 'success');
    } catch (fallbackErr) {
        showNotification('Failed to copy to clipboard', 'error');
        console.error('Copy failed:', fallbackErr);
    }
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
        if (useProxy) {
            status.textContent = 'Connected - Proxy';
        }
        else {
            status.textContent = 'Connected';
        }
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

let useProxy = false;
let proxySocket = null;
const PROXY_URL = "http://localhost:5001";

async function tryRobotThenProxy() {
    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 800);
        const res = await fetch('/api/movement/start-compliant', { signal: controller.signal, cache: 'no-store' });
        clearTimeout(timeout);
        if (res.ok) {
            const data = await res.json();
            if (data && data.positions) {
                console.log('[movement] Connected to robot API.');
                useProxy = false;
                // apply initial positions
                if (window.updateVisualization) window.updateVisualization(data.positions);
                return;
            }
        }
        throw new Error('robot positions fetch failed');
    } catch (err) {
        console.warn('[movement] Robot unavailable, falling back to proxy:', err.message || err);
        useProxy = true;
        await connectToProxy();
    }
}

async function connectToProxy() {
    if (proxySocket && proxySocket.connected) return;
    proxySocket = io(PROXY_URL);

    proxySocket.on('connect', () => {
        console.log('[movement] connected to proxy websocket');
        updateConnectionStatus(true);
        // request state
        proxySocket.emit('request_state');
    });

    proxySocket.on('disconnect', () => {
        console.log('[movement] disconnected from proxy websocket');
        updateConnectionStatus(false);
    });

    proxySocket.on('robot_state', (data) => {
        const positions = data.positions || {};
        if (window.updateVisualization) window.updateVisualization(positions);
        if (window.updateJointValues) window.updateJointValues(positions);
    });

    proxySocket.on('mirror_update', (data) => {
        if (!data) return;
        const obj = { [data.joint]: data.angle };
        if (window.updateVisualization) window.updateVisualization(obj);
        if (window.updateJointValues) window.updateJointValues(obj);
        // capture if recording
        if (window.captureMovementFrame) window.captureMovementFrame(obj);
    });

    proxySocket.on('multiple_mirror_update', (data) => {
        const positions = data.positions || {};
        if (window.updateVisualization) window.updateVisualization(positions);
        if (window.updateJointValues) window.updateJointValues(positions);
        if (window.captureMovementFrame) window.captureMovementFrame(positions);
    });
}

// override startPositionUpdates to try robot then proxy
function startPositionUpdatesOverride() {
    // existing behavior expected elsewhere; attempt robot first
    tryRobotThenProxy();
}

// hook into window for page code to call
window.startPositionUpdates = startPositionUpdatesOverride;

// When user manipulates UI (sliders), call this to send to robot or proxy
window.sendJointUpdate = async function(jointName, angle) {
    if (!useProxy) {
        // try robot API
        try {
            const res = await fetch('/api/movement/goto', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ positions: { [jointName]: angle }, duration: 0.0 })
            });
            if (!res.ok) throw new Error('robot goto failed');
            return;
        } catch (err) {
            console.warn('[movement] robot goto failed, switching to proxy:', err);
            // fallback to proxy
            useProxy = true;
            await connectToProxy();
        }
    }

    // send to proxy
    if (proxySocket && proxySocket.connected) {
        proxySocket.emit('joint_update', { joint: jointName, angle, origin: 'movement_recorder' });
    } else {
        console.warn('[movement] no proxy socket to send update');
    }
};

// export for debug
window._movement_fallback = { tryRobotThenProxy, connectToProxy, proxySocket };

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
window.resetCamera = resetCamera;
window.showNotification = showNotification;
window.updateVisualization = updateVisualization;
window.capturedMovements = capturedMovements;
window.joints = joints;

// Hamburger menu functionality
function initHamburgerMenu() {
    const hamburger = document.getElementById('hamburger');
    const navLinks = document.getElementById('navLinks');

    if (hamburger && navLinks) {
        hamburger.addEventListener('click', () => {
            hamburger.classList.toggle('active');
            navLinks.classList.toggle('active');
            document.body.classList.toggle('menu-open');
        });

        // Close menu when clicking on a link
        const links = navLinks.querySelectorAll('.nav-link');
        links.forEach(link => {
            link.addEventListener('click', () => {
                hamburger.classList.remove('active');
                navLinks.classList.remove('active');
                document.body.classList.remove('menu-open');
            });
        });

        // Close menu when clicking outside
        document.addEventListener('click', (event) => {
            const isClickInsideNav = navLinks.contains(event.target);
            const isClickOnHamburger = hamburger.contains(event.target);

            if (!isClickInsideNav && !isClickOnHamburger && navLinks.classList.contains('active')) {
                hamburger.classList.remove('active');
                navLinks.classList.remove('active');
                document.body.classList.remove('menu-open');
            }
        });
    }
}

import { computeBoundsTree, disposeBoundsTree, acceleratedRaycast } from 'three-mesh-bvh';

// Add BVH to THREE.BufferGeometry prototype
THREE.BufferGeometry.prototype.computeBoundsTree = computeBoundsTree;
THREE.BufferGeometry.prototype.disposeBoundsTree = disposeBoundsTree;
THREE.Mesh.prototype.raycast = acceleratedRaycast;

// ... your existing code ...

// Add near the top with other global variables
let robotMeshes = [];
let meshToJointMap = new Map();
let isColliding = false;

// Define which parts should NOT check collision with each other
const IGNORE_COLLISION_PAIRS = [
    // Adjacent joints in right arm chain
    ['r_shoulder_pitch', 'r_shoulder_roll'],
    ['r_shoulder_roll', 'r_arm_yaw'],
    ['r_arm_yaw', 'r_elbow_pitch'],
    ['r_elbow_pitch', 'r_forearm_yaw'],
    ['r_forearm_yaw', 'r_wrist_pitch'],
    ['r_wrist_pitch', 'r_wrist_roll'],
    ['r_wrist_roll', 'r_gripper'],

    ['base', 'l_shoulder_pitch'],
    ['base', 'r_shoulder_pitch'],

    // Adjacent joints in left arm chain
    ['l_shoulder_pitch', 'l_shoulder_roll'],
    ['l_shoulder_roll', 'l_arm_yaw'],
    ['l_arm_yaw', 'l_elbow_pitch'],
    ['l_elbow_pitch', 'l_forearm_yaw'],
    ['l_forearm_yaw', 'l_wrist_pitch'],
    ['l_wrist_pitch', 'l_wrist_roll'],
    ['l_wrist_roll', 'l_gripper'],

    // Neck joints
    ['neck_yaw', 'neck_pitch'],
    ['neck_pitch', 'neck_roll'],

    // Antennas shouldn't collide with head
    ['l_antenna', 'neck_yaw'],
    ['l_antenna', 'neck_pitch'],
    ['l_antenna', 'neck_roll'],
    ['r_antenna', 'neck_yaw'],
    ['r_antenna', 'neck_pitch'],
    ['r_antenna', 'neck_roll'],
    ['l_antenna', 'r_antenna'],
];

function shouldIgnoreCollision(joint1, joint2) {
    if (joint1 === joint2)
        return true

    return IGNORE_COLLISION_PAIRS.some(pair =>
        (pair[0] === joint1 && pair[1] === joint2) ||
        (pair[0] === joint2 && pair[1] === joint1)
    );
}

function initMeshCollisionDetection() {
    robotMeshes = [];
    meshToJointMap.clear();

    // Traverse the robot and collect all meshes
    robot.traverse((child) => {
        if (child.isMesh && child.geometry) {
            // Compute BVH for this mesh
            if (!child.geometry.boundsTree) {
                child.geometry.computeBoundsTree();
            }

            // Find which joint this mesh belongs to
            let parentJoint = null;
            let parent = child.parent;

            while (parent) {
                // Check if this parent is one of our tracked joints
                for (const [jointName, jointObj] of Object.entries(joints)) {
                    if (parent === jointObj) {
                        parentJoint = jointName;
                        break;
                    }
                }
                if (parentJoint) break;
                parent = parent.parent;
            }

            // If no specific joint found, it might be part of the base/torso
            if (!parentJoint) {
                parentJoint = 'base';
            }

            robotMeshes.push(child);
            meshToJointMap.set(child, parentJoint);

            console.log(`[Collision] Registered mesh for joint: ${parentJoint}`);
        }
    });

    console.log(`[Collision] Initialized ${robotMeshes.length} meshes for collision detection`);
}

function checkMeshCollisions() {
    const collisions = [];
    const collidingMeshPairs = new Set();

    // Check each pair of meshes
    for (let i = 0; i < robotMeshes.length; i++) {
        for (let j = i + 1; j < robotMeshes.length; j++) {
            const mesh1 = robotMeshes[i];
            const mesh2 = robotMeshes[j];

            const joint1 = meshToJointMap.get(mesh1);
            const joint2 = meshToJointMap.get(mesh2);

            // Skip if these joints should ignore collisions
            if (shouldIgnoreCollision(joint1, joint2)) {
                continue;
            }

            // Update world matrices
            mesh1.updateMatrixWorld(true);
            mesh2.updateMatrixWorld(true);

            // Get geometries and their world transforms
            const geom1 = mesh1.geometry;
            const geom2 = mesh2.geometry;

            if (!geom1.boundsTree || !geom2.boundsTree) {
                continue;
            }

            // Transform mesh2's BVH into mesh1's local space
            const matrix = new THREE.Matrix4();
            matrix.copy(mesh1.matrixWorld).invert().multiply(mesh2.matrixWorld);

            // Check for intersection
            const intersects = geom1.boundsTree.intersectsGeometry(geom2, matrix);

            if (intersects) {
                const pairKey = `${joint1}-${joint2}`;
                if (!collidingMeshPairs.has(pairKey)) {
                    collisions.push({
                        joint1: joint1,
                        joint2: joint2,
                        mesh1: mesh1,
                        mesh2: mesh2
                    });
                    collidingMeshPairs.add(pairKey);
                }
            }
        }
    }

    return collisions;
}

function visualizeCollision(collisions) {
    // Remove old collision indicators
    const oldIndicators = scene.children.filter(child => child.userData.isCollisionIndicator);
    oldIndicators.forEach(indicator => scene.remove(indicator));

    isColliding = collisions.length > 0;

    if (isColliding) {
        // Create visual indicators at collision points
        collisions.forEach(collision => {
            // Get world positions of the colliding meshes
            const pos1 = new THREE.Vector3();
            const pos2 = new THREE.Vector3();
            collision.mesh1.getWorldPosition(pos1);
            collision.mesh2.getWorldPosition(pos2);

            // Create a sphere at the midpoint
            const midpoint = new THREE.Vector3().addVectors(pos1, pos2).multiplyScalar(0.5);
            const geometry = new THREE.SphereGeometry(0.03, 16, 16);
            const material = new THREE.MeshBasicMaterial({
                color: 0xff0000,
                transparent: true,
                opacity: 0.7
            });
            const indicator = new THREE.Mesh(geometry, material);
            indicator.position.copy(midpoint);
            indicator.userData.isCollisionIndicator = true;
            scene.add(indicator);
        });

        showCollisionWarning(collisions);
    } else {
        hideCollisionWarning();
    }
}

function showCollisionWarning(collisions) {
    let warning = document.getElementById('collision-warning');
    if (!warning) {
        warning = document.createElement('div');
        warning.id = 'collision-warning';
        warning.style.cssText = `
            position: fixed;
            top: 120px;
            right: 20px;
            background: rgba(239, 68, 68, 0.95);
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            font-weight: 600;
            z-index: 9999;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            max-width: 300px;
        `;
        document.body.appendChild(warning);
    }

    const uniqueCollisions = [...new Set(collisions.map(c => `${c.joint1} ↔ ${c.joint2}`))];
    const collisionText = uniqueCollisions.join('<br>');

    warning.innerHTML = `
        ⚠️ COLLISION DETECTED
        <div style="font-size: 0.85em; margin-top: 0.5rem; opacity: 0.9;">
            ${collisionText}
        </div>
    `;
    warning.style.display = 'block';
}

function hideCollisionWarning() {
    const warning = document.getElementById('collision-warning');
    if (warning) {
        warning.style.display = 'none';
    }
}

// Optional: Highlight colliding meshes
function highlightCollidingMeshes(collisions) {
    // Reset all mesh colors first
    robotMeshes.forEach(mesh => {
        if (mesh.material && mesh.userData.originalColor) {
            mesh.material.color.copy(mesh.userData.originalColor);
            mesh.material.emissive.setHex(0x000000);
        }
    });

    // Highlight colliding meshes
    collisions.forEach(collision => {
        [collision.mesh1, collision.mesh2].forEach(mesh => {
            if (mesh.material) {
                // Store original color if not already stored
                if (!mesh.userData.originalColor) {
                    mesh.userData.originalColor = mesh.material.color.clone();
                }
                // Make it glow red
                mesh.material.emissive.setHex(0xff0000);
                mesh.material.emissiveIntensity = 0.5;
            }
        });
    });
}


// Update the DOMContentLoaded listener at the bottom
document.addEventListener('DOMContentLoaded', () => {
    initScene();
    initializeJointControls();
    tryRobotThenProxy();
    initHamburgerMenu(); // Add this line
});