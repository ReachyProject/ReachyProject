// Theme management
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    
    const themeIcon = document.querySelector('.theme-icon');
    themeIcon.textContent = newTheme === 'light' ? '🌙' : '☀️';
}

function loadTheme() {
    const savedTheme = 'dark'; // Default to dark since we can't use localStorage
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    const themeIcon = document.querySelector('.theme-icon');
    if (themeIcon) {
        themeIcon.textContent = savedTheme === 'light' ? '🌙' : '☀️';
    }
}

loadTheme();

// Three.js Scene Setup
let scene, camera, renderer, robot;
let joints = {};
let jointStates = {};
let capturedMovements = [];

function initScene() {
    const container = document.getElementById('canvas-container');
    
    scene = new THREE.Scene();
    scene.background = new THREE.Color(
        getComputedStyle(document.documentElement).getPropertyValue('--bg-primary').trim()
    );
    
    // Camera positioned for front-facing view
    camera = new THREE.PerspectiveCamera(
        50,  // Reduced FOV for less distortion
        container.clientWidth / container.clientHeight,
        0.1,
        1000
    );
    // Front-facing position - directly in front at eye level
    camera.position.set(0, 0.65, 1.8);  // Straight ahead, at torso height
    camera.lookAt(0, 0.65, 0);  // Looking at robot's center
    
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);
    
    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambientLight);
    
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.6);
    directionalLight.position.set(5, 10, 7.5);
    scene.add(directionalLight);
    
    // Grid
    const gridHelper = new THREE.GridHelper(2, 20, 0x444444, 0x222222);
    scene.add(gridHelper);
    
    // Create simple robot representation
    createRobotModel();
    
    // Mouse controls
    addMouseControls();
    
    // Handle window resize
    window.addEventListener('resize', () => {
        camera.aspect = container.clientWidth / container.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(container.clientWidth, container.clientHeight);
    });
    
    animate();
}

function createRobotModel() {
    robot = new THREE.Group();
    
    const whiteMaterial = new THREE.MeshPhongMaterial({ color: 0xf0f0f0 });
    const darkMaterial = new THREE.MeshPhongMaterial({ color: 0x1a1a1a });
    const jointMaterial = new THREE.MeshPhongMaterial({ color: 0xe0e0e0 });
    
    const torsoHeight = 0.35;
    const shoulderY = 0.743;
    const topWidth = 0.45;
    
    // TORSO
    const torsoDepth = 0.15;
    const torsoShape = new THREE.Shape();
    const bottomWidth = 0.22;
    const radius = 0.05;
    
    torsoShape.moveTo(-bottomWidth/2 + radius, 0);
    torsoShape.lineTo(bottomWidth/2 - radius, 0);
    torsoShape.quadraticCurveTo(bottomWidth/2, 0, bottomWidth/2, radius);
    torsoShape.lineTo(topWidth/2, torsoHeight - radius);
    torsoShape.quadraticCurveTo(topWidth/2, torsoHeight, topWidth/2 - radius, torsoHeight);
    torsoShape.lineTo(-topWidth/2 + radius, torsoHeight);
    torsoShape.quadraticCurveTo(-topWidth/2, torsoHeight, -topWidth/2, torsoHeight - radius);
    torsoShape.lineTo(-bottomWidth/2, radius);
    torsoShape.quadraticCurveTo(-bottomWidth/2, 0, -bottomWidth/2 + radius, 0);
    
    const extrudeSettings = {
        steps: 2,
        depth: torsoDepth,
        bevelEnabled: true,
        bevelThickness: 0.015,
        bevelSize: 0.015,
        bevelSegments: 5
    };
    
    const torsoGeometry = new THREE.ExtrudeGeometry(torsoShape, extrudeSettings);
    const torso = new THREE.Mesh(torsoGeometry, whiteMaterial);
    torso.position.set(0, 0.393, -torsoDepth/2);
    robot.add(torso);
    
    // ===== RIGHT ARM - BALL JOINT SHOULDER =====
    const rShoulderX = topWidth/2 + 0.06;
    
    const rShoulderGroup = new THREE.Group();
    rShoulderGroup.position.set(rShoulderX, shoulderY, 0);
    robot.add(rShoulderGroup);
    
    joints['r_shoulder_pitch'] = rShoulderGroup;
    joints['r_shoulder_roll'] = rShoulderGroup;
    joints['r_arm_yaw'] = rShoulderGroup;
    
    const rShoulderGeometry = new THREE.SphereGeometry(0.055, 20, 20);
    const rShoulderVis = new THREE.Mesh(rShoulderGeometry, jointMaterial);
    rShoulderGroup.add(rShoulderVis);
    
    const rUpperArmGeometry = new THREE.CylinderGeometry(0.03, 0.03, 0.28, 16);
    const rUpperArmVis = new THREE.Mesh(rUpperArmGeometry, whiteMaterial);
    rUpperArmVis.position.set(0, -0.14, 0);
    rShoulderGroup.add(rUpperArmVis);
    
    const rElbowPitchGroup = new THREE.Group();
    rElbowPitchGroup.position.set(0, -0.28, 0);
    rShoulderGroup.add(rElbowPitchGroup);
    joints['r_elbow_pitch'] = rElbowPitchGroup;
    
    const rElbowGeometry = new THREE.SphereGeometry(0.04, 20, 20);
    const rElbowVis = new THREE.Mesh(rElbowGeometry, jointMaterial);
    rElbowPitchGroup.add(rElbowVis);
    
    const rForearmYawGroup = new THREE.Group();
    rForearmYawGroup.position.set(0, 0, 0);
    rElbowPitchGroup.add(rForearmYawGroup);
    joints['r_forearm_yaw'] = rForearmYawGroup;
    
    const rForearmGeometry = new THREE.CylinderGeometry(0.025, 0.028, 0.25, 16);
    const rForearmVis = new THREE.Mesh(rForearmGeometry, whiteMaterial);
    rForearmVis.position.set(0, -0.125, 0);
    rForearmYawGroup.add(rForearmVis);
    
    const rWristPitchGroup = new THREE.Group();
    rWristPitchGroup.position.set(0, -0.25, 0);
    rForearmYawGroup.add(rWristPitchGroup);
    joints['r_wrist_pitch'] = rWristPitchGroup;
    
    const rWristRollGroup = new THREE.Group();
    rWristRollGroup.position.set(0, 0, 0);
    rWristPitchGroup.add(rWristRollGroup);
    joints['r_wrist_roll'] = rWristRollGroup;
    
    const rWristGeometry = new THREE.SphereGeometry(0.04, 16, 16);
    const rWristVis = new THREE.Mesh(rWristGeometry, jointMaterial);
    rWristRollGroup.add(rWristVis);
    
    const rGripperGroup = new THREE.Group();
    rGripperGroup.position.set(0, -0.04, 0);
    rWristRollGroup.add(rGripperGroup);
    joints['r_gripper'] = rGripperGroup;
    
    const rGripperBaseGeometry = new THREE.BoxGeometry(0.05, 0.08, 0.055);
    const rGripperBase = new THREE.Mesh(rGripperBaseGeometry, whiteMaterial);
    rGripperGroup.add(rGripperBase);
    
    const rGripper = createGripper(whiteMaterial);
    rGripper.position.set(0, -0.04, 0);
    rGripperGroup.add(rGripper);
    
    // ===== LEFT ARM - BALL JOINT SHOULDER =====
    const lShoulderX = -(topWidth/2 + 0.06);
    
    const lShoulderGroup = new THREE.Group();
    lShoulderGroup.position.set(lShoulderX, shoulderY, 0);
    robot.add(lShoulderGroup);
    
    joints['l_shoulder_pitch'] = lShoulderGroup;
    joints['l_shoulder_roll'] = lShoulderGroup;
    joints['l_arm_yaw'] = lShoulderGroup;
    
    const lShoulderVis = new THREE.Mesh(rShoulderGeometry.clone(), jointMaterial);
    lShoulderGroup.add(lShoulderVis);
    
    const lUpperArmVis = new THREE.Mesh(rUpperArmGeometry.clone(), whiteMaterial);
    lUpperArmVis.position.set(0, -0.14, 0);
    lShoulderGroup.add(lUpperArmVis);
    
    const lElbowPitchGroup = new THREE.Group();
    lElbowPitchGroup.position.set(0, -0.28, 0);
    lShoulderGroup.add(lElbowPitchGroup);
    joints['l_elbow_pitch'] = lElbowPitchGroup;
    
    const lElbowVis = new THREE.Mesh(rElbowGeometry.clone(), jointMaterial);
    lElbowPitchGroup.add(lElbowVis);
    
    const lForearmYawGroup = new THREE.Group();
    lForearmYawGroup.position.set(0, 0, 0);
    lElbowPitchGroup.add(lForearmYawGroup);
    joints['l_forearm_yaw'] = lForearmYawGroup;
    
    const lForearmVis = new THREE.Mesh(rForearmGeometry.clone(), whiteMaterial);
    lForearmVis.position.set(0, -0.125, 0);
    lForearmYawGroup.add(lForearmVis);
    
    const lWristPitchGroup = new THREE.Group();
    lWristPitchGroup.position.set(0, -0.25, 0);
    lForearmYawGroup.add(lWristPitchGroup);
    joints['l_wrist_pitch'] = lWristPitchGroup;
    
    const lWristRollGroup = new THREE.Group();
    lWristRollGroup.position.set(0, 0, 0);
    lWristPitchGroup.add(lWristRollGroup);
    joints['l_wrist_roll'] = lWristRollGroup;
    
    const lWristVis = new THREE.Mesh(rWristGeometry.clone(), jointMaterial);
    lWristRollGroup.add(lWristVis);
    
    const lGripperGroup = new THREE.Group();
    lGripperGroup.position.set(0, -0.04, 0);
    lWristRollGroup.add(lGripperGroup);
    joints['l_gripper'] = lGripperGroup;
    
    const lGripperBase = new THREE.Mesh(rGripperBaseGeometry.clone(), whiteMaterial);
    lGripperGroup.add(lGripperBase);
    
    const lGripper = createGripper(whiteMaterial);
    lGripper.position.set(0, -0.04, 0);
    lGripperGroup.add(lGripper);
    
    // ===== NECK/HEAD - BALL JOINT =====
    const neckY = shoulderY + 0.05;
    
    // Neck ball joint group - handles pitch, roll, and yaw
    const neckGroup = new THREE.Group();
    neckGroup.position.set(0, neckY, 0);
    robot.add(neckGroup);
    
    // Store references for all three neck rotations
    joints['neck_pitch'] = neckGroup;
    joints['neck_roll'] = neckGroup;
    joints['neck_yaw'] = neckGroup;
    
    // Visual neck ball
    const neckGeometry = new THREE.SphereGeometry(0.065, 20, 20);
    const neckVis = new THREE.Mesh(neckGeometry, jointMaterial);
    neckGroup.add(neckVis);
    
    // Head attached to neck
    const headWidth = 0.253;
    const headHeight = 0.175;
    const headDepth = 0.108;
    const headOffsetY = 0.48 - 0.18 - headHeight;
    
    const headShape = new THREE.Shape();
    const hRadius = 0.025;
    const hw = headWidth / 2;
    const hh = headHeight / 2;
    
    headShape.moveTo(-hw + hRadius, -hh);
    headShape.lineTo(hw - hRadius, -hh);
    headShape.quadraticCurveTo(hw, -hh, hw, -hh + hRadius);
    headShape.lineTo(hw, hh - hRadius);
    headShape.quadraticCurveTo(hw, hh, hw - hRadius, hh);
    headShape.lineTo(-hw + hRadius, hh);
    headShape.quadraticCurveTo(-hw, hh, -hw, hh - hRadius);
    headShape.lineTo(-hw, -hh + hRadius);
    headShape.quadraticCurveTo(-hw, -hh, -hw + hRadius, -hh);
    
    const headExtrudeSettings = {
        steps: 2,
        depth: headDepth,
        bevelEnabled: true,
        bevelThickness: 0.012,
        bevelSize: 0.012,
        bevelSegments: 5
    };
    
    const headGeometry = new THREE.ExtrudeGeometry(headShape, headExtrudeSettings);
    const head = new THREE.Mesh(headGeometry, whiteMaterial);
    head.position.set(0, headOffsetY, -headDepth/2);
    neckGroup.add(head);
    joints['head'] = head;
    
    // Antennas attached to head
    const antennaSpacing = headWidth/2;
    const antennaBaseY = headOffsetY + headHeight/2;
    const antennaHeight = 0.14;
    
    const antennaGeometry = new THREE.CylinderGeometry(0.005, 0.005, antennaHeight, 12);
    const antennaMaterial = new THREE.MeshPhongMaterial({ color: 0x2a2a2a });
    const antennaBaseGeometry = new THREE.CylinderGeometry(0.012, 0.015, 0.025, 12);
    
    const leftAntennaBase = new THREE.Mesh(antennaBaseGeometry, darkMaterial);
    leftAntennaBase.position.set(-antennaSpacing, antennaBaseY + 0.0125, -headDepth/2);
    neckGroup.add(leftAntennaBase);
    
    const rightAntennaBase = new THREE.Mesh(antennaBaseGeometry, darkMaterial);
    rightAntennaBase.position.set(antennaSpacing, antennaBaseY + 0.0125, -headDepth/2);
    neckGroup.add(rightAntennaBase);
    
    // Antenna groups for rotation
    const leftAntennaGroup = new THREE.Group();
    leftAntennaGroup.position.set(-antennaSpacing, antennaBaseY + 0.025, -headDepth/2);
    neckGroup.add(leftAntennaGroup);
    joints['l_antenna'] = leftAntennaGroup;
    
    const leftAntenna = new THREE.Mesh(antennaGeometry, antennaMaterial);
    leftAntenna.position.set(0, antennaHeight/2, 0);
    leftAntennaGroup.add(leftAntenna);
    
    const leftTip = new THREE.Mesh(new THREE.SphereGeometry(0.01, 12, 12), darkMaterial);
    leftTip.position.set(0, antennaHeight, 0);
    leftAntennaGroup.add(leftTip);
    
    const rightAntennaGroup = new THREE.Group();
    rightAntennaGroup.position.set(antennaSpacing, antennaBaseY + 0.025, -headDepth/2);
    neckGroup.add(rightAntennaGroup);
    joints['r_antenna'] = rightAntennaGroup;
    
    const rightAntenna = new THREE.Mesh(antennaGeometry, antennaMaterial);
    rightAntenna.position.set(0, antennaHeight/2, 0);
    rightAntennaGroup.add(rightAntenna);
    
    const rightTip = new THREE.Mesh(new THREE.SphereGeometry(0.01, 12, 12), darkMaterial);
    rightTip.position.set(0, antennaHeight, 0);
    rightAntennaGroup.add(rightTip);
    
    // Log all registered joints
    console.log('[3D] Robot model created. Registered joints:', Object.keys(joints));
    console.log('[3D] Total joints registered:', Object.keys(joints).length);

    scene.add(robot);
}

function createLimb(radius, length, material, name) {
    const geometry = new THREE.CylinderGeometry(radius, radius, length, 8);
    const limb = new THREE.Mesh(geometry, material);
    joints[name] = limb;
    return limb;
}

function createGripper(material) {
    const group = new THREE.Group();
    
    // Thumb opposable segments
    const thumbGeometry = new THREE.BoxGeometry(0.008, 0.04, 0.04);
    
    const leftThumb = new THREE.Mesh(thumbGeometry, material);
    leftThumb.position.set(-0.02, -0.02, 0.0);
    leftThumb.rotation.z = 0.3;
    group.add(leftThumb);
    
    const rightThumb = new THREE.Mesh(thumbGeometry, material);
    rightThumb.position.set(0.02, -0.02, 0.0);
    rightThumb.rotation.z = -0.3;
    group.add(rightThumb);
    
    return group;
}

function addMouseControls() {
    let isDragging = false;
    let previousMousePosition = { x: 0, y: 0 };
    let isPanning = false;
    
    const container = document.getElementById('canvas-container');
    
    container.addEventListener('mousedown', (e) => {
        isDragging = true;
        isPanning = e.button === 2; // Right click for panning
        previousMousePosition = { x: e.offsetX, y: e.offsetY };
        e.preventDefault();
    });
    
    container.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        
        const deltaMove = {
            x: e.offsetX - previousMousePosition.x,
            y: e.offsetY - previousMousePosition.y
        };
        
        if (isPanning) {
            // Pan camera
            const panSpeed = 0.003;
            camera.position.x -= deltaMove.x * panSpeed;
            camera.position.y += deltaMove.y * panSpeed;
        } else {
            // Rotate camera around robot
            const rotationSpeed = 0.005;
            const radius = Math.sqrt(
                camera.position.x ** 2 + 
                camera.position.z ** 2
            );
            
            const angle = Math.atan2(camera.position.z, camera.position.x);
            const newAngle = angle + deltaMove.x * rotationSpeed;
            
            camera.position.x = radius * Math.cos(newAngle);
            camera.position.z = radius * Math.sin(newAngle);
            camera.position.y += deltaMove.y * 0.003;
            
            camera.lookAt(0, 0.5, 0);  // Look at robot center (adjusted for accurate height)
        }
        
        previousMousePosition = { x: e.offsetX, y: e.offsetY };
    });
    
    container.addEventListener('mouseup', () => {
        isDragging = false;
        isPanning = false;
    });
    
    container.addEventListener('mouseleave', () => {
        isDragging = false;
        isPanning = false;
    });
    
    container.addEventListener('contextmenu', (e) => {
        e.preventDefault();
    });
    
    container.addEventListener('wheel', (e) => {
        e.preventDefault();
        const zoomSpeed = 0.1;
        const direction = e.deltaY > 0 ? 1 : -1;
        
        const zoomFactor = 1 + direction * zoomSpeed;
        camera.position.x *= zoomFactor;
        camera.position.y *= zoomFactor;
        camera.position.z *= zoomFactor;
    });
}

function animate() {
    requestAnimationFrame(animate);
    renderer.render(scene, camera);
}

// API Communication
async function startCompliantMode() {
    try {
        console.log('[CONTROL] Starting compliant mode...');
        const response = await fetch('/api/movement/start-compliant', {
            method: 'POST'
        });
        const result = await response.json();
        
        console.log('[CONTROL] Start compliant response:', result);
        
        if (result.success) {
            // Initialize Three.js with actual robot starting positions
            if (result.initial_positions) {
                console.log('[CONTROL] Setting initial Three.js positions:', result.initial_positions);
                updateVisualization(result.initial_positions);
            }
            
            showNotification('Compliant mode activated', 'success');
            updateConnectionStatus(true);
            startPositionUpdates();
            console.log('[CONTROL] Compliant mode activated successfully');
        } else {
            showNotification('Failed to start: ' + result.message, 'error');
            console.error('[CONTROL] Failed to start compliant mode:', result.message);
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
        console.error('[CONTROL] Exception in startCompliantMode:', error);
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
            updateConnectionStatus(false);
            stopPositionUpdates();
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
        stopPositionUpdates();
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
    
    console.log('[DEBUG] Starting position updates...');
    let updateCount = 0;
    let lastPositions = null;
    
    positionUpdateInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/movement/positions');
            const data = await response.json();
            
            if (data.success) {
                updateCount++;
                
                // Check if positions actually changed
                const positionsChanged = !lastPositions || 
                    JSON.stringify(data.positions) !== JSON.stringify(lastPositions);
                
                if (positionsChanged) {
                    console.log(`[DEBUG] Positions CHANGED at update #${updateCount}`);
                    
                    // Show which joints changed
                    if (lastPositions) {
                        for (const [joint, angle] of Object.entries(data.positions)) {
                            if (lastPositions[joint] !== angle) {
                                console.log(`[DEBUG] ${joint}: ${lastPositions[joint]}° → ${angle}°`);
                            }
                        }
                    }
                }
                
                // Log periodically
                if (updateCount === 1 || updateCount % 50 === 0) {
                    console.log(`[DEBUG] Position update #${updateCount}:`, data.positions);
                }
                
                lastPositions = {...data.positions};
                updateVisualization(data.positions);
                updateJointValues(data.positions);
            } else {
                console.error('[DEBUG] Failed to fetch positions:', data.message);
            }
        } catch (error) {
            console.error('[DEBUG] Error fetching positions:', error);
        }
    }, 100);
    
    console.log('[DEBUG] Position update interval started');
}

function stopPositionUpdates() {
    if (positionUpdateInterval) {
        clearInterval(positionUpdateInterval);
        positionUpdateInterval = null;
    }
}

function updateVisualization(positions) {
    const DEG_TO_RAD = Math.PI / 180;
    let updatedJoints = 0;
    let failedJoints = [];
    
    console.log('[VIZ] Updating visualization with', Object.keys(positions).length, 'joints');
    
    for (const [jointName, angleDeg] of Object.entries(positions)) {
        const angleRad = angleDeg * DEG_TO_RAD;
        const joint = joints[jointName];
        
        if (!joint) {
            failedJoints.push(jointName);
            continue;
        }
        
        // Log first few joint updates for debugging
        if (updatedJoints < 3) {
            console.log(`[VIZ] Updating ${jointName}: ${angleDeg}° (${angleRad.toFixed(3)} rad)`);
        }
        
        // Apply rotation based on joint type
        if (jointName.includes('shoulder_pitch')) {
            joint.rotation.x = angleRad;
            updatedJoints++;
        }
        else if (jointName.includes('shoulder_roll')) {
            joint.rotation.z = angleRad;
            updatedJoints++;
        }
        else if (jointName.includes('arm_yaw')) {
            joint.rotation.y = angleRad;
            updatedJoints++;
        }
        else if (jointName.includes('elbow_pitch')) {
            joint.rotation.x = angleRad;
            updatedJoints++;
        }
        else if (jointName.includes('forearm_yaw')) {
            joint.rotation.y = angleRad;
            updatedJoints++;
        }
        else if (jointName.includes('wrist_pitch')) {
            joint.rotation.x = angleRad;
            updatedJoints++;
        }
        else if (jointName.includes('wrist_roll')) {
            joint.rotation.z = angleRad;
            updatedJoints++;
        }
        else if (jointName.includes('gripper')) {
            const normalized = (angleDeg + 50) / 75;
            joint.scale.set(1, Math.max(0.3, normalized), 1);
            updatedJoints++;
        }
        else if (jointName.includes('neck_pitch')) {
            joint.rotation.x = angleRad;
            updatedJoints++;
        }
        else if (jointName.includes('neck_roll')) {
            joint.rotation.z = angleRad;
            updatedJoints++;
        }
        else if (jointName.includes('neck_yaw')) {
            joint.rotation.y = angleRad;
            updatedJoints++;
        }
        else if (jointName.includes('antenna')) {
            joint.rotation.z = angleRad;
            updatedJoints++;
        }
        else {
            console.warn(`[VIZ] Unknown joint type: ${jointName}`);
        }
    }
    
    if (failedJoints.length > 0) {
        console.warn('[VIZ] Joints not found in Three.js model:', failedJoints);
    }
    
    console.log(`[VIZ] Updated ${updatedJoints} joints successfully`);
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
        
        // Separate arm joints from antennas and neck
        const armJoints = {};
        const antennaJoints = {};
        let neckRoll = null, neckPitch = null, neckYaw = null;
        
        for (const [joint, angle] of Object.entries(movement)) {
            if (joint.includes('antenna')) {
                antennaJoints[joint] = angle;
            } else if (joint === 'neck_roll') {
                neckRoll = angle;
            } else if (joint === 'neck_pitch') {
                neckPitch = angle;
            } else if (joint === 'neck_yaw') {
                neckYaw = angle;
            } else {
                armJoints[joint] = angle;
            }
        }
        
        // Arm movements using goto
        if (Object.keys(armJoints).length > 0) {
            code += 'goto(\n';
            code += '    goal_positions={\n';
            
            for (const [joint, angle] of Object.entries(armJoints)) {
                code += `        reachy.${joint}: ${angle},\n`;
            }
            
            code += '    },\n';
            code += '    duration=1.0,  # Adjust this duration as needed\n';
            code += '    interpolation_mode=InterpolationMode.MINIMUM_JERK\n';
            code += ')\n';
        }
        
        // Antenna movements (direct goal_position)
        for (const [joint, angle] of Object.entries(antennaJoints)) {
            code += `reachy.head.${joint}.goal_position = ${angle}\n`;
        }
        
        // Head orientation (note: look_at requires computing from neck angles)
        if (neckRoll !== null || neckPitch !== null || neckYaw !== null) {
            code += `# Head orientation: roll=${neckRoll || 0}°, pitch=${neckPitch || 0}°, yaw=${neckYaw || 0}°\n`;
            code += `# Note: Manually position head and use look_at() with target coordinates\n`;
            code += `# Example: reachy.head.look_at(x=0.5, y=0, z=0, duration=1.0)\n`;
        }
        
        code += 'time.sleep(0.1)  # Small pause between movements\n\n';
    });
    
    code += '# Safely turn off the robot\n';
    code += 'reachy.turn_off_smoothly("r_arm")\n';
    code += 'reachy.turn_off_smoothly("l_arm")\n';
    code += 'reachy.turn_off("head")\n';
    
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
    console.log(`[${type}] ${message}`);
    
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

// Initialize joint controls
async function initializeJointControls() {
    try {
        console.log('[INIT] Initializing joint controls...');
        const response = await fetch('/api/movement/joints');
        const data = await response.json();
        
        console.log('[INIT] Received joint data:', data);
        
        if (data.success) {
            const container = document.getElementById('joint-controls');
            container.innerHTML = '';
            
            console.log('[INIT] Found', data.joints.length, 'joints');
            
            data.joints.forEach(jointName => {
                jointStates[jointName] = false; // Default unlocked
                
                console.log('[INIT] Adding control for joint:', jointName);
                
                const div = document.createElement('div');
                div.className = 'joint-item';
                div.innerHTML = `
                    <div class="joint-info">
                        <div class="joint-name">${jointName}</div>
                        <div class="joint-value" id="value-${jointName}">0.00°</div>
                    </div>
                    <button 
                        id="lock-${jointName}" 
                        class="lock-toggle unlocked"
                        onclick="toggleJointLock('${jointName}', !jointStates['${jointName}'])"
                    >
                        🔓 Unlocked
                    </button>
                `;
                container.appendChild(div);
            });
            
            console.log('[INIT] Joint controls initialized successfully');
            
            // Debug: Check if Three.js joints match
            console.log('[INIT] Three.js joints available:', Object.keys(joints));
            const missingJoints = data.joints.filter(j => !joints[j]);
            if (missingJoints.length > 0) {
                console.warn('[INIT] WARNING: These joints are missing from Three.js model:', missingJoints);
            }
        }
    } catch (error) {
        console.error('[INIT] Error loading joints:', error);
    }
}

/**
 * Smooth interpolation between two joint angle states
 */
function interpolateJointStates(startState, endState, progress) {
    const result = {};
    
    // Get all unique joint names from both states
    const allJoints = new Set([...Object.keys(startState), ...Object.keys(endState)]);
    
    for (const joint of allJoints) {
        const startAngle = startState[joint] || 0;
        const endAngle = endState[joint] || 0;
        
        // Linear interpolation (lerp)
        result[joint] = startAngle + (endAngle - startAngle) * progress;
    }
    
    return result;
}

/**
 * Easing function for smoother animation (ease-in-out cubic)
 */
function easeInOutCubic(t) {
    return t < 0.5 
        ? 4 * t * t * t 
        : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

/**
 * Animate between current state and target state
 */
function animateToState(targetState, duration = 1000) {
    // Get current state
    const currentState = {};
    for (const jointName in joints) {
        const joint = joints[jointName];
        if (joint && joint.rotation) {
            const RAD_TO_DEG = 180 / Math.PI;
            
            if (jointName.includes('shoulder_pitch')) {
                currentState[jointName] = joint.rotation.x * RAD_TO_DEG;
            } else if (jointName.includes('shoulder_roll')) {
                currentState[jointName] = joint.rotation.z * RAD_TO_DEG;
            } else if (jointName.includes('arm_yaw')) {
                currentState[jointName] = joint.rotation.y * RAD_TO_DEG;
            } else if (jointName.includes('elbow_pitch')) {
                currentState[jointName] = joint.rotation.x * RAD_TO_DEG;
            } else if (jointName.includes('forearm_yaw')) {
                currentState[jointName] = joint.rotation.y * RAD_TO_DEG;
            } else if (jointName.includes('wrist_pitch')) {
                currentState[jointName] = joint.rotation.x * RAD_TO_DEG;
            } else if (jointName.includes('wrist_roll')) {
                currentState[jointName] = joint.rotation.z * RAD_TO_DEG;
            } else if (jointName.includes('neck_yaw')) {
                currentState[jointName] = joint.rotation.y * RAD_TO_DEG;
            } else if (jointName.includes('neck_pitch')) {
                currentState[jointName] = joint.rotation.x * RAD_TO_DEG;
            } else if (jointName.includes('neck_roll')) {
                currentState[jointName] = joint.rotation.z * RAD_TO_DEG;
            } else if (jointName.includes('antenna')) {
                currentState[jointName] = joint.rotation.z * RAD_TO_DEG;
            }
        }
    }
    
    const startTime = Date.now();
    
    function updateAnimation() {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easedProgress = easeInOutCubic(progress);
        
        const interpolatedState = interpolateJointStates(currentState, targetState, easedProgress);
        updateVisualization(interpolatedState);
        
        if (progress < 1) {
            requestAnimationFrame(updateAnimation);
        }
    }
    
    requestAnimationFrame(updateAnimation);
}

/**
 * Animate through a sequence of poses
 */
function animatePoseSequence(poses, durationPerPose = 1000) {
    let currentPoseIndex = 0;
    
    function animateNextPose() {
        if (currentPoseIndex >= poses.length) {
            console.log('Animation sequence complete!');
            return;
        }
        
        const targetPose = poses[currentPoseIndex];
        console.log(`Animating to pose ${currentPoseIndex + 1}/${poses.length}`);
        
        animateToState(targetPose, durationPerPose);
        
        currentPoseIndex++;
        setTimeout(animateNextPose, durationPerPose + 100); // Small pause between poses
    }
    
    animateNextPose();
}

// Updated test functions with interpolation

window.testJointAnimation = function() {
    console.log('Testing smooth joint animation...');
    
    const testPose = {
        r_shoulder_pitch: -45,
        r_shoulder_roll: -30,
        r_arm_yaw: 15,
        r_elbow_pitch: -90,
        r_forearm_yaw: 20,
        r_wrist_pitch: 10,
        l_shoulder_pitch: -20,
        l_elbow_pitch: -60,
        l_antenna: 15,
        r_antenna: -15
    };
    
    animateToState(testPose, 1500);
    console.log('Animating to test pose...');
};

window.testWave = function() {
    console.log('Testing smooth wave animation...');
    
    const poses = [
        // Start: Arm up
        { 
            r_shoulder_pitch: -90, 
            r_shoulder_roll: 22.5, 
            r_elbow_pitch: -90,
            r_forearm_yaw: 22.5, 
            r_wrist_roll: 0 
        },
        // Wave right
        { 
            r_shoulder_pitch: -90, 
            r_shoulder_roll: 22.5, 
            r_elbow_pitch: -90,
            r_forearm_yaw: 22.5,  
            r_wrist_roll: 30 
        },
        // Wave left
        { 
            r_shoulder_pitch: -90, 
            r_shoulder_roll: 22.5, 
            r_elbow_pitch: -90,
            r_forearm_yaw: 22.5, 
            r_wrist_roll: -30 
        },
        // Wave right
        { 
            r_shoulder_pitch: -90, 
            r_shoulder_roll: 22.5, 
            r_elbow_pitch: -90,
            r_forearm_yaw: 22.5, 
            r_wrist_roll: 30 
        },
        // Wave left
        { 
            r_shoulder_pitch: -90, 
            r_shoulder_roll: 22.5, 
            r_elbow_pitch: -90,
            r_forearm_yaw: 22.5,
            r_wrist_roll: -30 
        },
        // Center
        { 
            r_shoulder_pitch: -90, 
            r_shoulder_roll: 22.5, 
            r_elbow_pitch: -90, 
            r_forearm_yaw: 22.5,
            r_wrist_roll: 0 
        },
        // Return to neutral
        { 
            r_shoulder_pitch: 0, 
            r_shoulder_roll: 0,
            r_forearm_yaw: 0,  
            r_elbow_pitch: 0,
            r_wrist_roll: 0
        }
    ];
    
    animatePoseSequence(poses, 800);
};

window.testHead = function() {
    console.log('Testing smooth wave animation...');
    
    const poses = [
        // Start: Arm up
        { 
            neck_roll: -22, 
            neck_yaw: 22.5, 
            neck_pitch: 0,
            l_antenna: -15,
            r_antenna: 15
        },
        // Wave right
        { 
            neck_roll: 22, 
            neck_yaw: -22.5, 
            neck_pitch: 0,
            l_antenna: 15,
            r_antenna: -15
        },
        // Wave left
        { 
            neck_roll: -22, 
            neck_yaw: 22.5, 
            neck_pitch: 0,
            l_antenna: -15,
            r_antenna: 15
        },
        // Wave right
        { 
            neck_roll: 22, 
            neck_yaw: -22.5, 
            neck_pitch: 0,
            l_antenna: 15,
            r_antenna: -15
        },
        // Wave left
        { 
            neck_roll: -22, 
            neck_yaw: 22.5, 
            neck_pitch: 0,
            l_antenna: -15,
            r_antenna: 15
        },
        // Center
        { 
            neck_roll: 22, 
            neck_yaw: -22.5, 
            neck_pitch: 0,
            l_antenna: 15,
            r_antenna: -15
        },
        // Return to neutral
        { 
            neck_roll: 0, 
            neck_yaw: 0, 
            neck_pitch: 0,
            l_antenna: 0,
            r_antenna: 0
            
        }
    ];
    
    animatePoseSequence(poses, 800);
};

window.testBothArms = function() {
    console.log('Testing both arms animation...');
    
    const poses = [
        // Both arms forward
        {
            r_shoulder_pitch: -90,
            r_elbow_pitch: 0,
            l_shoulder_pitch: -90,
            l_elbow_pitch: 0
        },
        // Both arms to sides
        {
            r_shoulder_pitch: -45,
            r_shoulder_roll: -90,
            r_elbow_pitch: 0,
            l_shoulder_pitch: -45,
            l_shoulder_roll: 90,
            l_elbow_pitch: 0
        },
        // Cross arms
        {
            r_shoulder_pitch: 0,
            r_shoulder_roll: 45,
            r_elbow_pitch: -90,
            l_shoulder_pitch: 0,
            l_shoulder_roll: -45,
            l_elbow_pitch: -90
        },
        // Return to neutral
        {
            r_shoulder_pitch: 0,
            r_shoulder_roll: 0,
            r_elbow_pitch: 0,
            l_shoulder_pitch: 0,
            l_shoulder_roll: 0,
            l_elbow_pitch: 0
        }
    ];
    
    animatePoseSequence(poses, 1200);
};

window.resetToNeutralPose = function() {
    console.log('Smoothly resetting to neutral pose...');
    
    const neutralPose = {
        r_shoulder_pitch: 0,
        r_shoulder_roll: 0,
        r_elbow_pitch: 0,
        l_shoulder_pitch: 0,
        l_shoulder_roll: 0,
        l_elbow_pitch: 0,
        l_antenna: 0,
        r_antenna: 0
    };
    
    animateToState(neutralPose, 1500);
};

// Helper function to test a custom pose with smooth animation
window.animateTo = function(pose, duration = 1000) {
    animateToState(pose, duration);
    console.log('Animating to custom pose:', pose);
};

// Initialize everything
document.addEventListener('DOMContentLoaded', () => {
    initScene();
    initializeJointControls();
});

let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        // Force reflow
        document.body.style.display = 'none';
        document.body.offsetHeight; // Trigger reflow
        document.body.style.display = '';
    }, 250);
});