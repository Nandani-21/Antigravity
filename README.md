# AI Posture & Eye Strain Monitoring System

A real-time, AI-based application that uses your webcam to monitor your posture, face distance, and eye strain, giving you visual and voice alerts to help maintain a healthy workspace environment.

## Features Included:
1. **Face Distance Detection**: Computes face width relative to the screen to warn you if you are sitting too close.
2. **Eye Strain / Fatigue Detection**: Uses facial landmarks to calculate the Eye Aspect Ratio (EAR). If your eyes remain closed for several consecutive frames, it alerts you to take a break.
3. **Posture Detection**: Analyzes upper-body pose landmarks to detect head tilt (slouching) and uneven shoulder alignment.
4. **Real-time Alert System**: Provides both on-screen visual alerts and Text-To-Speech (TTS) voice alerts.
5. **Timer Reminder**: A built-in timer that reminds you to stand up and stretch every 30 minutes.

## Prerequisites

Ensure you have Python installed (preferably version 3.8+).

## Installation

1. Open your terminal or command prompt.
2. Navigate to the folder containing this project.
3. Install the required dependencies using pip:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the `main.py` script to start the monitoring system:

```bash
python main.py
```

- Allow the application to access your webcam.
- A window will pop up showing the live video feed.
- Ensure your face and shoulders are visible within the camera frame for optimal detection.
- Press the **`q`** key while focused on the video window to exit the application gracefully.

## How It Works
- **Mediapipe Holistic** is used to simultaneously run Face Mesh and upper-body Pose estimation.
- **OpenCV** captures the webcam frames and handles the UI overlay.
- **pyttsx3** handles text-to-speech voice alerts asynchronously on a separate thread, avoiding video freezing.
