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

    // B. Calibration Button
    calibrateBtn.addEventListener('click', () => {
        fetch('/calibrate', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                // Show a quick visual feedback
                calibrateBtn.textContent = "Reset Successful!";
                setTimeout(() => calibrateBtn.textContent = "Recalibrate / Reset", 2000);
            })
            .catch(console.error);
    });

    // C. Voice Testing
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

    // Poll the backend for data
    function fetchState() {
        fetch('/get_state')
            .then(res => res.json())
            .then(data => {
                // Update Timer
                timerVal.textContent = data.state.timer_minutes;
                
                // Update Dashboard Cards
                updateStatus('val-posture', data.state.posture);
                updateStatus('val-eyes', data.state.eyes);
                updateStatus('val-distance', data.state.distance);

                // Update Stats Counters
                countPosture.textContent = data.state.posture_count;
                countEyes.textContent = data.state.eye_strain_count;

                // Handle Real-time Alerts
                handleAlerts(data.alerts);
            })
            .catch(err => {
                // Ignore silent fetch errors if backend is busy
            });
    }

    // Poll rapidly for smooth UI
    setInterval(fetchState, 500);
    
    // Load voices on page load
    window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
});
