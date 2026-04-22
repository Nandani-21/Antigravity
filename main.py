import cv2
import mediapipe as mp
import math
import time
import threading
import pyttsx3

# ==========================================
# CONFIGURATION AND THRESHOLDS
# ==========================================
EAR_THRESHOLD = 0.25          # Increased (0.20 is too low sometimes)
EYE_CLOSED_FRAMES = 20        # Slightly higher for stability
FACE_WIDTH_THRESHOLD = 0.35   # Reduced (0.40 triggers too early)
SLOUCH_THRESHOLD = 0.25       # Increased (0.15 is too sensitive)
VOICE_COOLDOWN = 15           # Better spacing between alerts
# Initialize Text-to-Speech engine
# Using a global variable to avoid multiple engine initializations
engine = None
try:
    engine = pyttsx3.init()
    engine.setProperty('rate', 150) # Set speed of speech
except Exception as e:
    print(f"Warning: Text-to-speech could not be initialized. {e}")

def speak(text):
    """Speaks the alert text using a separate thread so it doesn't freeze the video feed."""
    if engine is None:
        return
    def run_speech():
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            print(f"TTS Error: {e}")
            
    threading.Thread(target=run_speech, daemon=True).start()

def get_distance(p1, p2):
    """Calculates Euclidean distance between two points (used for normalized coordinates)."""
    return math.hypot(p1.x - p2.x, p1.y - p2.y)

def calculate_ear(landmarks, indices):
    """
    Calculates the Eye Aspect Ratio (EAR) to detect closed eyes.
    EAR = (Vertical_1 + Vertical_2) / (2 * Horizontal)
    """
    p1, p2, p3, p4, p5, p6 = [landmarks[i] for i in indices]
    
    vertical_1 = get_distance(p2, p6)
    vertical_2 = get_distance(p3, p5)
    horizontal = get_distance(p1, p4)
    
    if horizontal == 0:
        return 0
    return (vertical_1 + vertical_2) / (2.0 * horizontal)

def main():
    # Initialize MediaPipe Holistic model (handles both face and pose)
    mp_holistic = mp.solutions.holistic
    mp_drawing = mp.solutions.drawing_utils
    
    holistic = mp_holistic.Holistic(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    # Start webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    # State variables
    closed_eyes_frames = 0
    last_alert_time = 0
    start_time = time.time()
    
    # Left and Right eye landmark indices from MediaPipe FaceMesh
    LEFT_EYE = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE = [362, 385, 387, 263, 373, 380]
    
    # Face boundary landmarks to measure face width
    FACE_LEFT = 234
    FACE_RIGHT = 454
    
    print("========================================")
    print("Starting AI Posture & Eye Strain Monitor")
    print("Press 'q' in the video window to quit.")
    print("========================================")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame.")
            break
            
        # Flip the frame horizontally for a natural selfie-view
        frame = cv2.flip(frame, 1)
        height, width, _ = frame.shape
        
        # Convert BGR (OpenCV format) to RGB (MediaPipe format)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Process the image to detect face and pose
        results = holistic.process(rgb_frame)
        
        alerts = [] # List to store alerts for the current frame
        ear = 0.0
        face_width = 0.0
        posture_value = 0.0
        
        # ==========================================
        # 1. FACE DISTANCE & EYE STRAIN DETECTION
        # ==========================================
        if results.face_landmarks:
            landmarks = results.face_landmarks.landmark
            
            # -- Face Distance Check --
            # Compare face width to the total frame width
            face_width = get_distance(landmarks[FACE_LEFT], landmarks[FACE_RIGHT])
            if face_width > FACE_WIDTH_THRESHOLD:
                alerts.append("Warning: You are too close to the screen!")
                
            # -- Eye Strain (Blink/Closed Eyes) Check --
            left_ear = calculate_ear(landmarks, LEFT_EYE)
            right_ear = calculate_ear(landmarks, RIGHT_EYE)
            avg_ear = (left_ear + right_ear) / 2.0
            ear = avg_ear
            
            # Optional: Highlight eyes for visual feedback
            for eye in [LEFT_EYE, RIGHT_EYE]:
                for idx in eye:
                    pt = landmarks[idx]
                    cv2.circle(frame, (int(pt.x * width), int(pt.y * height)), 1, (0, 255, 255), -1)
            
            # If EAR is below threshold, eyes are closed
            if avg_ear < EAR_THRESHOLD:
                closed_eyes_frames += 1
            else:
                closed_eyes_frames = 0
                
            # Alert if eyes are closed for too many frames
            if closed_eyes_frames > EYE_CLOSED_FRAMES:
                alerts.append("Eye Strain: Take a 20-second break! Look away.")
                
        # ==========================================
        # 2. POSTURE DETECTION
        # ==========================================
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            nose = landmarks[0]
            left_shoulder = landmarks[11]
            right_shoulder = landmarks[12]
            
            # Proceed only if upper body landmarks are visible
            if nose.visibility > 0.5 and left_shoulder.visibility > 0.5 and right_shoulder.visibility > 0.5:
                # Calculate mid-point of shoulders (y-axis)
                mid_shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
                
                # Vertical distance between nose and shoulders
                neck_distance = mid_shoulder_y - nose.y
                posture_value = neck_distance
                
                # If distance is too small, user is slouching or leaning head down
                if neck_distance < SLOUCH_THRESHOLD:
                    alerts.append("Posture: Sit up straight and maintain good posture!")
                    
                # Check for shoulder tilt / leaning sideways
                shoulder_diff = abs(left_shoulder.y - right_shoulder.y)
                if shoulder_diff > 0.08:
                    alerts.append("Posture: Shoulders are tilted!")
            
            # Draw Pose landmarks (upper body) on the frame
            mp_drawing.draw_landmarks(
                frame, results.pose_landmarks, mp_holistic.POSE_CONNECTIONS,
                landmark_drawing_spec=mp_drawing.DrawingSpec(color=(255, 0, 0), thickness=2, circle_radius=2)
            )
        
        # ==========================================
        # 3. TIMER REMINDER (Optional Enhancement)
        # ==========================================
        elapsed_time = time.time() - start_time
        if elapsed_time > 30 * 60: # 30 minutes
            alerts.append("Timer: 30 minutes passed. Please stretch your legs!")
            start_time = time.time() # Reset timer
            
        # ==========================================
        # 4. DISPLAY ALERTS AND TRIGGER VOICE
        # ==========================================
        current_time = time.time()
        y_pos = 40
        
        if alerts:
            unique_alerts = list(set(alerts)) # Remove duplicate alerts
            
            for alert in unique_alerts:
                # Draw text shadow for better readability
                cv2.putText(frame, alert, (22, y_pos + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
                # Draw alert text
                cv2.putText(frame, alert, (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                y_pos += 35
                
                # Trigger voice alert with cooldown to avoid spamming
                if current_time - last_alert_time > VOICE_COOLDOWN:
                    speak(alert)
                    last_alert_time = current_time
        
        # Display instructions
        cv2.putText(frame, "Press 'q' to exit", (10, height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # 👉 PASTE HERE (after all values are calculated)
        print("EAR:", ear)
        print("Face Width:", face_width)
        print("Posture Distance:", posture_value)

        # Show the frame
        cv2.imshow('AI Posture & Eye Strain Monitor', frame)
        
        # Break loop on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Cleanup resources
    cap.release()
    cv2.destroyAllWindows()
    holistic.close()

if __name__ == "__main__":
    main()
