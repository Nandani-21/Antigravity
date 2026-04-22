import os
import cv2
import mediapipe as mp
import math
import time
from flask import Flask, render_template, Response, jsonify

app = Flask(__name__)

# ==========================================
# CONFIGURATION AND THRESHOLDS
# ==========================================
EAR_THRESHOLD = 0.25
EYE_CLOSED_FRAMES = 20
FACE_WIDTH_THRESHOLD = 0.35
SLOUCH_THRESHOLD = 0.25

mp_holistic = mp.solutions.holistic
mp_drawing = mp.solutions.drawing_utils

holistic = mp_holistic.Holistic(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# Global State for Frontend Polling
latest_alerts = []
app_state = {
    "posture": "Analyzing...",
    "eyes": "Analyzing...",
    "distance": "Analyzing...",
    "timer_minutes": 0,
    "start_time": time.time(),
    "posture_count": 0,
    "eye_strain_count": 0
}

# State trackers to ensure we don't count the same event multiple times per second
is_currently_slouching = False
is_currently_fatigued = False

def get_distance(p1, p2):
    return math.hypot(p1.x - p2.x, p1.y - p2.y)

def calculate_ear(landmarks, indices):
    p1, p2, p3, p4, p5, p6 = [landmarks[i] for i in indices]
    vertical_1 = get_distance(p2, p6)
    vertical_2 = get_distance(p3, p5)
    horizontal = get_distance(p1, p4)
    if horizontal == 0: return 0
    return (vertical_1 + vertical_2) / (2.0 * horizontal)

def generate_frames():
    global latest_alerts, app_state, is_currently_slouching, is_currently_fatigued
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Camera could not be opened.")
        return
        
    LEFT_EYE = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE = [362, 385, 387, 263, 373, 380]
    FACE_LEFT = 234
    FACE_RIGHT = 454
    
    closed_eyes_frames = 0
    
    while True:
        success, frame = cap.read()
        if not success:
            time.sleep(0.1)
            continue
            
        frame = cv2.flip(frame, 1)
        height, width, _ = frame.shape
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        results = holistic.process(rgb_frame)
        
        current_alerts = []
        
        # Default states
        current_distance = "Safe"
        current_eyes = "Normal"
        current_posture = "Good"
        
        if results.face_landmarks:
            landmarks = results.face_landmarks.landmark
            
            # --- Draw Face Bounding Box ---
            x_min, y_min = width, height
            x_max, y_max = 0, 0
            for pt in landmarks:
                x, y = int(pt.x * width), int(pt.y * height)
                x_min = min(x_min, x)
                y_min = min(y_min, y)
                x_max = max(x_max, x)
                y_max = max(y_max, y)
            
            # Draw subtle glass-like box around face
            cv2.rectangle(frame, (x_min - 10, y_min - 10), (x_max + 10, y_max + 10), (255, 255, 255), 1)
            cv2.putText(frame, "Face", (x_min - 10, y_min - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            face_width = get_distance(landmarks[FACE_LEFT], landmarks[FACE_RIGHT])
            
            if face_width > FACE_WIDTH_THRESHOLD:
                current_distance = "Too Close"
                current_alerts.append("Too Close to Screen")
                
            left_ear = calculate_ear(landmarks, LEFT_EYE)
            right_ear = calculate_ear(landmarks, RIGHT_EYE)
            avg_ear = (left_ear + right_ear) / 2.0
            
            # Highlight eyes
            for eye in [LEFT_EYE, RIGHT_EYE]:
                for idx in eye:
                    pt = landmarks[idx]
                    cv2.circle(frame, (int(pt.x * width), int(pt.y * height)), 1, (0, 255, 255), -1)
            
            if avg_ear < EAR_THRESHOLD:
                closed_eyes_frames += 1
            else:
                closed_eyes_frames = 0
                
            if closed_eyes_frames > EYE_CLOSED_FRAMES:
                current_eyes = "Strained"
                current_alerts.append("Take a Break (Eye Strain)")
                if not is_currently_fatigued:
                    app_state["eye_strain_count"] += 1
                    is_currently_fatigued = True
            else:
                is_currently_fatigued = False
                
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            nose = landmarks[0]
            left_shoulder = landmarks[11]
            right_shoulder = landmarks[12]
            
            if nose.visibility > 0.5 and left_shoulder.visibility > 0.5 and right_shoulder.visibility > 0.5:
                mid_shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
                neck_distance = mid_shoulder_y - nose.y
                
                bad_posture_detected = False
                if neck_distance < SLOUCH_THRESHOLD:
                    current_posture = "Slouching"
                    current_alerts.append("Sit Straight")
                    bad_posture_detected = True
                    
                shoulder_diff = abs(left_shoulder.y - right_shoulder.y)
                if shoulder_diff > 0.08:
                    if current_posture == "Good":
                        current_posture = "Tilted"
                    current_alerts.append("Align Shoulders")
                    bad_posture_detected = True
                
                if bad_posture_detected:
                    if not is_currently_slouching:
                        app_state["posture_count"] += 1
                        is_currently_slouching = True
                else:
                    is_currently_slouching = False
            
            # Draw Pose lines (shoulders)
            mp_drawing.draw_landmarks(
                frame, results.pose_landmarks, mp_holistic.POSE_CONNECTIONS,
                landmark_drawing_spec=mp_drawing.DrawingSpec(color=(0, 255, 100), thickness=2, circle_radius=2)
            )
            
        elapsed_time = time.time() - app_state["start_time"]
        app_state["timer_minutes"] = int(elapsed_time // 60)
        
        if elapsed_time > 30 * 60:
            current_alerts.append("Session Limit: Take a Walk")
            
        app_state["distance"] = current_distance
        app_state["eyes"] = current_eyes
        app_state["posture"] = current_posture
        
        latest_alerts = list(set(current_alerts))
        
        # Overlay warning text directly on video feed
        if latest_alerts:
            cv2.putText(frame, "WARNING", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
            y_offset = 70
            for alert in latest_alerts:
                cv2.putText(frame, f"- {alert}", (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                y_offset += 30
        
        # Encode frame for web streaming
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/get_state')
def get_state():
    return jsonify({
        "alerts": latest_alerts,
        "state": app_state
    })
    
@app.route('/calibrate', methods=['POST'])
def calibrate():
    global app_state
    app_state["posture_count"] = 0
    app_state["eye_strain_count"] = 0
    app_state["start_time"] = time.time()
    return jsonify({"status": "success"})

if __name__ == '__main__':
    print("Starting Web Server. Please visit http://127.0.0.1:5000 in your browser.")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
