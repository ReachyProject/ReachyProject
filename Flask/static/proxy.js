import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { EXRLoader } from "three/addons/loaders/EXRLoader.js";

const SOCKET_URL = "http://localhost:5001";
let socket = null;

let scene, camera, renderer, robot, controls;
let joints = {};
let handles = {};
let currentPositions = {};
let hoveredHandle = null;
let degreeIndicator = null;

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

const JOINT_OFFSETS = {
    'r_shoulder_pitch': 90,
    'l_shoulder_pitch': -90,
    'r_shoulder_roll': 90,
    'l_shoulder_roll': -90,
};

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

document.addEventListener('DOMContentLoaded', () => {
    initScene();
    loadModel();
    initSocket();
    attachUI();
    createDegreeIndicator();
});

function initSocket() {
    socket = io(SOCKET_URL);

    socket.on('connect', () => {
        document.getElementById('proxy-status').textContent = 'Proxy: Online';
        document.getElementById('proxy-status').classList.remove('offline');
        document.getElementById('proxy-status').classList.add('connected');
        socket.emit('request_state');
    });

    socket.on('disconnect', () => {
        document.getElementById('proxy-status').textContent = 'Proxy: Offline';
        document.getElementById('proxy-status').classList.add('offline');
    });

    socket.on('robot_state', (data) => {
        const positions = data.positions || {};
        Object.assign(currentPositions, positions);
        applyPose(positions);
    });

    socket.on('mirror_update', (data) => {
        if (!data) return;
        currentPositions[data.joint] = data.angle;
        applyJointRotation(data.joint, data.angle);
    });

    socket.on('multiple_mirror_update', (data) => {
        const positions = data.positions || {};
        Object.assign(currentPositions, positions);
        applyPose(positions);
    });
}

function attachUI() {
    const resetBtn = document.getElementById('reset-btn');
    resetBtn.addEventListener('click', () => {
        for (const k of Object.keys(joints)) {
            currentPositions[k] = 0;
        }
        applyPose(currentPositions);
        if (socket && socket.connected) socket.emit('set_multiple_joints', { positions: currentPositions, origin: 'proxy' });
    });
}

function initScene() {
    const container = document.getElementById('canvas-container');
    scene = new THREE.Scene();
    const aspect = container.clientWidth / container.clientHeight;
    camera = new THREE.PerspectiveCamera(35, aspect, 0.1, 100);
    camera.position.set(0,1.2,3);

    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);

    controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0,0.85,0);
    controls.update();

    const amb = new THREE.AmbientLight(0xffffff, 0.6); scene.add(amb);
    const dir = new THREE.DirectionalLight(0xffffff, 0.8); dir.position.set(5,10,7.5); scene.add(dir);

    const grid = new THREE.GridHelper(10,20); scene.add(grid);

    const exr = new EXRLoader();
    exr.load('/static/room.exr', (tex) => {
        tex.mapping = THREE.EquirectangularReflectionMapping;
        scene.environment = tex;
        scene.background = tex;
    }, undefined, () => {});

    window.addEventListener('resize', onWindowResize);
    animate();
}

function loadModel() {
    const loader = new GLTFLoader();
    loader.load('/static/reachy.glb', (gltf) => {
        robot = gltf.scene;
        scene.add(robot);
        const box = new THREE.Box3().setFromObject(robot);
        const center = new THREE.Vector3(); box.getCenter(center);
        robot.position.sub(center);
        robot.position.y += 0.7;
        robot.rotation.y = -Math.PI/2;

        robot.traverse((obj) => {
            const name = (obj.name||'').toLowerCase();
            for (const [apiName, glbName] of Object.entries(JOINT_NAME_MAP)) {
                if (name === glbName.toLowerCase()) {
                    joints[apiName] = obj;
                    obj.rotation.order = 'XYZ';
                    createHandlesForJoint(apiName, obj);
                    
                    // Ensure all three neck joint keys reference the same object
                    if (glbName.toLowerCase() === 'neck_joint') {
                        joints['neck_yaw'] = obj;
                        joints['neck_pitch'] = obj;
                        joints['neck_roll'] = obj;
                    }
                }
            }
        });

        if (socket && socket.connected) socket.emit('request_state');
    }, undefined, (err)=>{ console.error('GLB load error',err); });
}

function createHandlesForJoint(jointName, jointObj) {
    const torusRadius = 0.08;
    const tubeRadius = 0.008;
    const geom = new THREE.TorusGeometry(torusRadius, tubeRadius, 16, 32);

    let color = 0x00d9ff;
    let axis = 'y';

    if (jointName.includes("neck_yaw")) { color = 0xff0000; axis = 'y'; }
    if (jointName.includes("neck_pitch")) { color = 0x00ff00; axis = 'x'; }
    if (jointName.includes("neck_roll")) { color = 0x0000ff; axis = 'z'; }

    const mat = new THREE.MeshStandardMaterial({
        color,
        emissive: color,
        emissiveIntensity: 0.5,
        opacity: 0.8,
        transparent: true
    });
    
    const ring = new THREE.Mesh(geom, mat);
    ring.userData.jointName = jointName;
    ring.userData.baseColor = color;
    ring.userData.baseEmissiveIntensity = 0.5;
    
    // Rotate the ring to align with the rotation axis
    if (axis === 'x') {
        ring.rotation.y = Math.PI / 2;
    } else if (axis === 'y') {
        ring.rotation.x = Math.PI / 2;
    }
    
    jointObj.add(ring);
    handles[jointName] = { ring, axis, material: mat };
}

function createDegreeIndicator() {
    // Create HTML overlay for degree display
    const indicator = document.createElement('div');
    indicator.id = 'degree-indicator';
    indicator.style.cssText = `
        position: absolute;
        padding: 8px 12px;
        background: rgba(0, 0, 0, 0.8);
        color: #fff;
        font-family: 'Courier New', monospace;
        font-size: 14px;
        font-weight: bold;
        border-radius: 6px;
        pointer-events: none;
        display: none;
        z-index: 1000;
        border: 2px solid #00d9ff;
        box-shadow: 0 4px 12px rgba(0, 217, 255, 0.4);
    `;
    document.body.appendChild(indicator);
    degreeIndicator = indicator;
}

function updateDegreeIndicator(jointName, angle, mouseX, mouseY) {
    if (!degreeIndicator) return;
    
    const limits = JOINT_LIMITS[jointName];
    const limitText = limits ? ` (${limits[0]}° to ${limits[1]}°)` : '';
    
    degreeIndicator.innerHTML = `
        <div style="color: #00d9ff; margin-bottom: 4px;">${jointName.toUpperCase()}</div>
        <div style="font-size: 18px;">${angle.toFixed(1)}°</div>
        <div style="font-size: 10px; color: #aaa; margin-top: 2px;">${limitText}</div>
    `;
    degreeIndicator.style.left = (mouseX + 20) + 'px';
    degreeIndicator.style.top = (mouseY - 40) + 'px';
    degreeIndicator.style.display = 'block';
}

function hideDegreeIndicator() {
    if (degreeIndicator) {
        degreeIndicator.style.display = 'none';
    }
}

function clampJointAngle(jointName, angle) {
    const limits = JOINT_LIMITS[jointName];
    if (!limits) return angle;
    return Math.max(limits[0], Math.min(limits[1], angle));
}

function applyJointRotation(jointName, angleDeg) {
    const offset = JOINT_OFFSETS[jointName] || 0;
    const angleRad = THREE.MathUtils.degToRad(angleDeg + offset);
    
    // Handle neck joints FIRST before checking joint existence
    if (jointName === 'neck_yaw' || jointName === 'neck_pitch' || jointName === 'neck_roll') {
        const neck = joints['neck_yaw'] || joints['neck_pitch'] || joints['neck_roll'];
        if (!neck) return;

        const yaw   = THREE.MathUtils.degToRad(currentPositions['neck_yaw']   || 0);
        const pitch = THREE.MathUtils.degToRad(currentPositions['neck_pitch'] || 0);
        const roll  = THREE.MathUtils.degToRad(currentPositions['neck_roll']  || 0);

        neck.rotation.order = 'YXZ';
        neck.rotation.y = yaw;
        neck.rotation.x = pitch;
        neck.rotation.z = roll;

        return;
    }

    // For all other joints
    const joint = joints[jointName];
    if (!joint) return;

    if (jointName.includes('shoulder_pitch')) {
        joint.rotation.y = -angleRad;
    } else if (jointName.includes('shoulder_roll')) {
        joint.rotation.y = -angleRad;
    } else if (jointName.includes('arm_yaw')) {
        joint.rotation.y = -angleRad;
    } else if (jointName.includes('elbow_pitch')) {
        joint.rotation.y = -angleRad;
    } else if (jointName.includes('forearm_yaw')) {
        joint.rotation.y = angleRad;
    } else if (jointName.includes('wrist_pitch')) {
        joint.rotation.y = -angleRad;
    } else if (jointName.includes('wrist_roll')) {
        joint.rotation.y = -angleRad;
    } else if (jointName.includes('gripper')) {
        joint.rotation.y = angleRad;
    } else if (jointName.includes('antenna')) {
        joint.rotation.y = angleRad;
    }
}

function applyPose(positions) {
    for (const [j, a] of Object.entries(positions)) {
        applyJointRotation(j, a);
    }
}

function onWindowResize() {
    const container = document.getElementById('canvas-container');
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
}

function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
}

// Hover and drag logic
let dragging = false;
let dragJoint = null;
let dragStartAngle = 0;
let dragStartMouse = new THREE.Vector2();

const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();

// Hover detection
document.addEventListener('pointermove', (ev) => {
    if (dragging) return; // Don't check hover while dragging
    
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
    
    raycaster.setFromCamera(mouse, camera);
    const clickables = [];
    Object.values(handles).forEach(h => {
        if (h.ring) clickables.push(h.ring);
    });
    
    const hits = raycaster.intersectObjects(clickables, true);
    
    // Reset previous hover
    if (hoveredHandle) {
        const h = handles[hoveredHandle];
        if (h && h.material) {
            h.material.emissiveIntensity = h.ring.userData.baseEmissiveIntensity;
            h.material.opacity = 0.8;
        }
        hoveredHandle = null;
        renderer.domElement.style.cursor = 'default';
    }
    
    // Set new hover
    if (hits.length > 0) {
        const hit = hits[0].object;
        let cur = hit;
        while (cur && !cur.userData.jointName) cur = cur.parent;
        if (cur) {
            hoveredHandle = cur.userData.jointName;
            const h = handles[hoveredHandle];
            if (h && h.material) {
                h.material.emissiveIntensity = 1.2; // Brighten on hover
                h.material.opacity = 1.0;
            }
            renderer.domElement.style.cursor = 'grab';
        }
    }
});

// Start drag
document.addEventListener('pointerdown', (ev) => {
    if (!renderer || !hoveredHandle) return;
    
    dragJoint = hoveredHandle;
    dragging = true;
    dragStartAngle = currentPositions[dragJoint] || 0;
    
    const rect = renderer.domElement.getBoundingClientRect();
    dragStartMouse.set(
        ((ev.clientX - rect.left) / rect.width) * 2 - 1,
        -((ev.clientY - rect.top) / rect.height) * 2 + 1
    );
    
    controls.enabled = false;
    renderer.domElement.style.cursor = 'grabbing';
    
    // Show initial angle
    updateDegreeIndicator(dragJoint, dragStartAngle, ev.clientX, ev.clientY);
});

// Drag move
document.addEventListener('pointermove', (ev) => {
    if (!dragging || !dragJoint) return;

    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;

    const h = handles[dragJoint];
    if (!h) return;

    const joint = joints[dragJoint];
    if (!joint) return;

    // Get rotation axis in world space
    const localAxis = new THREE.Vector3(
        h.axis === 'x' ? 1 : 0,
        h.axis === 'y' ? 1 : 0,
        h.axis === 'z' ? 1 : 0
    );
    const worldAxis = localAxis.clone().transformDirection(joint.matrixWorld);

    // Project world axis into screen-space
    const p1 = joint.getWorldPosition(new THREE.Vector3());
    const p2 = p1.clone().add(worldAxis);

    const sp1 = p1.clone().project(camera);
    const sp2 = p2.clone().project(camera);

    const axisScreen = new THREE.Vector2(sp2.x - sp1.x, sp2.y - sp1.y).normalize();

    // Compute TOTAL mouse delta from drag start (not just from previous frame)
    const totalDelta = new THREE.Vector2(
        mouse.x - dragStartMouse.x,
        mouse.y - dragStartMouse.y
    );

    // Project onto axis
    const dragAmount = totalDelta.dot(axisScreen);

    // Convert to degrees - adjustable sensitivity
    const sensitivity = 120; // degrees per unit NDC
    const deltaDeg = dragAmount * sensitivity;

    // Calculate new angle RELATIVE to start angle
    const rawAngle = dragStartAngle + deltaDeg;
    const newAngle = clampJointAngle(dragJoint, rawAngle);

    currentPositions[dragJoint] = newAngle;
    applyJointRotation(dragJoint, newAngle);

    // Update degree indicator
    updateDegreeIndicator(dragJoint, newAngle, ev.clientX, ev.clientY);

    // Network push
    if (socket && socket.connected) {
        socket.emit('joint_update', {
            joint: dragJoint,
            angle: newAngle,
            origin: 'proxy'
        });
    }
});

// End drag
document.addEventListener('pointerup', () => {
    if (dragging) {
        dragging = false;
        dragJoint = null;
        controls.enabled = true;
        renderer.domElement.style.cursor = hoveredHandle ? 'grab' : 'default';
        hideDegreeIndicator();
    }
});

// expose for debugging
window.proxy = {
    applyPose, applyJointRotation, currentPositions, joints
};