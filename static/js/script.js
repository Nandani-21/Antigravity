document.addEventListener('DOMContentLoaded', () => {
    const alertsContainer = document.getElementById('alerts-container');
    const timerVal = document.getElementById('timer-val');
    const voiceToggle = document.getElementById('voice-toggle');
    const testVoiceBtn = document.getElementById('test-voice');
    const calibrateBtn = document.getElementById('calibrate-btn');
    const themeToggle = document.getElementById('theme-toggle');
    const videoContainer = document.getElementById('video-container');
    const alertSound = document.getElementById('alert-sound');

    // Stats
    const countPosture = document.getElementById('count-posture');
    const countEyes = document.getElementById('count-eyes');

    let lastAlertArray = [];
    let lastSpokenTime = 0;
    const VOICE_COOLDOWN = 15000; // 15 seconds

    // A. Theme Switcher (Dark/Light)
    themeToggle.addEventListener('click', () => {
        const root = document.documentElement;
        const currentTheme = root.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        root.setAttribute('data-theme', newTheme);
        
        // Update Icon
        themeToggle.innerHTML = newTheme === 'dark' ? '<i class="ph ph-sun"></i>' : '<i class="ph ph-moon"></i>';
    });

    // B. Voice Testing & Audio Config
    testVoiceBtn.addEventListener('click', () => {
        playAlertSound();
        speak("Voice alerts are active and working properly!");
    });

    function playAlertSound() {
        if (!voiceToggle.checked) return;
        alertSound.currentTime = 0; // Rewind
        alertSound.play().catch(e => console.log("Audio play prevented by browser policy"));
    }

    function speak(text) {
        if (!voiceToggle.checked) return;
        
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.05;
        
        const voices = window.speechSynthesis.getVoices();
        const goodVoice = voices.find(v => v.lang.includes('en-') && (v.name.includes('Google') || v.name.includes('Natural')));
        if (goodVoice) utterance.voice = goodVoice;
        
        window.speechSynthesis.speak(utterance);
    }

    // Update the UI text and colors
    function updateStatus(id, value) {
        const el = document.getElementById(id);
        const card = el.closest('.stat-card');
        const icon = card.querySelector('.stat-icon i');

        el.textContent = value;
        el.className = 'stat-value';
        
        // Reset icon color class
        icon.className = icon.className.split(' ')[0] + ' ' + icon.className.split(' ')[1];

        // Apply new color class based on status rules
        if (value === 'Good' || value === 'Normal' || value === 'Safe') {
            el.classList.add('status-good');
            icon.classList.add('status-good');
        } else if (value === 'Slouching' || value === 'Strained' || value === 'Too Close') {
            el.classList.add('status-danger');
            icon.classList.add('status-danger');
        } else {
            el.classList.add('status-warning');
            icon.classList.add('status-warning');
        }
    }

    // Handle incoming alerts
    function handleAlerts(alerts) {
        // Optimization: only redraw if alerts have changed
        if (JSON.stringify(alerts) === JSON.stringify(lastAlertArray)) return;
        lastAlertArray = alerts;

        alertsContainer.innerHTML = '';
        
        if (alerts.length > 0) {
            // Flash red border around the webcam
            videoContainer.classList.add('alert-flash');
            
            // Build the Alert popup cards
            alerts.forEach(alert => {
                const div = document.createElement('div');
                div.className = 'alert-box';
                div.innerHTML = `<i class="ph-fill ph-warning-octagon"></i> <span>${alert}</span>`;
                alertsContainer.appendChild(div);
            });

            // Trigger Voice / Sound
            const now = Date.now();
            if (now - lastSpokenTime > VOICE_COOLDOWN) {
                playAlertSound();
                speak(alerts[0]); // Speak the most critical one
                lastSpokenTime = now;
            }
        } else {
            // Remove flash if safe
            videoContainer.classList.remove('alert-flash');
        }
    }

    // ==========================================
    // C. AI LOGIC (MediaPipe JS)
    // ==========================================
    let state = {
        posture: 'Scanning',
        eyes: 'Scanning',
        distance: 'Scanning',
        posture_count: 0,
        eye_strain_count: 0,
    };

    const EAR_THRESHOLD = 0.25;
    const EYE_CLOSED_FRAMES = 15; // Adjusted for ~30FPS browser processing
    const FACE_WIDTH_THRESHOLD = 0.35;
    const SLOUCH_THRESHOLD = 0.25;

    let eyeClosedCounter = 0;
    let sessionStartTime = Date.now();

    // Reset logic
    calibrateBtn.addEventListener('click', () => {
        state.posture_count = 0;
        state.eye_strain_count = 0;
        sessionStartTime = Date.now();
        countPosture.textContent = 0;
        countEyes.textContent = 0;
        timerVal.textContent = 0;
        calibrateBtn.textContent = "Reset Successful!";
        setTimeout(() => calibrateBtn.textContent = "RECALIBRATE", 2000);
    });

    const videoElement = document.getElementById('video-stream');
    const canvasElement = document.getElementById('output-canvas');
    const canvasCtx = canvasElement.getContext('2d');

    const holistic = new Holistic({locateFile: (file) => {
        return `https://cdn.jsdelivr.net/npm/@mediapipe/holistic/${file}`;
    }});

    holistic.setOptions({
        modelComplexity: 1,
        smoothLandmarks: true,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5
    });
    holistic.onResults(onResults);

    const camera = new Camera(videoElement, {
        onFrame: async () => {
            await holistic.send({image: videoElement});
        },
        width: 640,
        height: 480
    });
    camera.start();

    function calcDist(p1, p2) {
        if (!p1 || !p2) return 0;
        return Math.hypot(p1.x - p2.x, p1.y - p2.y);
    }

    function getEAR(landmarks) {
        // Left eye
        const leftV1 = calcDist(landmarks[385], landmarks[380]);
        const leftV2 = calcDist(landmarks[387], landmarks[373]);
        const leftH = calcDist(landmarks[362], landmarks[263]);
        const leftEAR = leftH > 0 ? (leftV1 + leftV2) / (2.0 * leftH) : 0;

        // Right eye
        const rightV1 = calcDist(landmarks[160], landmarks[144]);
        const rightV2 = calcDist(landmarks[158], landmarks[153]);
        const rightH = calcDist(landmarks[33], landmarks[133]);
        const rightEAR = rightH > 0 ? (rightV1 + rightV2) / (2.0 * rightH) : 0;

        return (leftEAR + rightEAR) / 2.0;
    }

    function onResults(results) {
        // Update Timer
        const minutes = Math.floor((Date.now() - sessionStartTime) / 60000);
        timerVal.textContent = minutes;
        
        // Draw Video and Landmarks
        canvasElement.width = videoElement.videoWidth;
        canvasElement.height = videoElement.videoHeight;
        canvasCtx.save();
        canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);
        canvasCtx.drawImage(results.image, 0, 0, canvasElement.width, canvasElement.height);

        // Draw visual skeleton if we want
        if (results.poseLandmarks) {
            window.drawConnectors(canvasCtx, results.poseLandmarks, window.POSE_CONNECTIONS, {color: '#00f0ff', lineWidth: 4});
            window.drawLandmarks(canvasCtx, results.poseLandmarks, {color: '#ff2a5f', lineWidth: 2, radius: 3});
        }
        if (results.faceLandmarks) {
            window.drawConnectors(canvasCtx, results.faceLandmarks, window.FACEMESH_TESSELATION, {color: '#C0C0C070', lineWidth: 1});
        }
        canvasCtx.restore();

        let alerts = [];

        // 1. Face Distance & Eyes
        if (results.faceLandmarks) {
            const leftPoint = results.faceLandmarks[234];
            const rightPoint = results.faceLandmarks[454];
            const faceWidth = calcDist(leftPoint, rightPoint);

            if (faceWidth > FACE_WIDTH_THRESHOLD) {
                state.distance = "Too Close";
                alerts.push("You are too close to the screen");
            } else {
                state.distance = "Safe";
            }
            
            // EAR
            const ear = getEAR(results.faceLandmarks);
            if (ear < EAR_THRESHOLD) {
                eyeClosedCounter++;
                if (eyeClosedCounter === EYE_CLOSED_FRAMES) {
                    state.eye_strain_count++;
                }
                if (eyeClosedCounter >= EYE_CLOSED_FRAMES) {
                    state.eyes = "Strained";
                    alerts.push("Take a break, your eyes need rest");
                }
            } else {
                eyeClosedCounter = 0;
                state.eyes = "Normal";
            }
        } else {
            state.distance = "Scanning";
            state.eyes = "Scanning";
        }

        // 2. Posture
        if (results.poseLandmarks) {
            const leftShoulder = results.poseLandmarks[11];
            const rightShoulder = results.poseLandmarks[12];
            const nose = results.poseLandmarks[0];
            
            const midShoulderY = (leftShoulder.y + rightShoulder.y) / 2.0;
            const noseToShoulder = midShoulderY - nose.y;

            let badPosture = false;

            // Slouch logic
            if (noseToShoulder < SLOUCH_THRESHOLD) {
                alerts.push("Sit straight and maintain good posture");
                badPosture = true;
            }

            // Tilt logic
            const shoulderTilt = Math.abs(leftShoulder.y - rightShoulder.y);
            if (shoulderTilt > 0.05) {
                alerts.push("Your shoulders are tilted");
                badPosture = true;
            }

            if (badPosture) {
                if (state.posture === "Good" || state.posture === "Scanning") {
                    state.posture_count++;
                }
                state.posture = "Slouching";
            } else {
                state.posture = "Good";
            }
        } else {
            state.posture = "Scanning";
        }

        // 3. Update UI
        updateStatus('val-posture', state.posture);
        updateStatus('val-eyes', state.eyes);
        updateStatus('val-distance', state.distance);
        countPosture.textContent = state.posture_count;
        countEyes.textContent = state.eye_strain_count;

        handleAlerts(alerts);
    }

    // Load voices on page load
    window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
});
