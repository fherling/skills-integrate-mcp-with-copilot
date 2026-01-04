"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
import os
import json
from pathlib import Path
import threading
import time
import copy

# Load activities from JSON file
activities_file = os.path.join(Path(__file__).parent, "activities.json")

# Configuration constants
SAVE_INTERVAL_SECONDS = 5  # How often to batch-save changes to disk
SHUTDOWN_TIMEOUT_SECONDS = 10  # Maximum time to wait for background thread during shutdown

# Flag to track if activities have been modified
activities_dirty = False
activities_lock = threading.Lock()
shutdown_event = threading.Event()
save_thread = None

def load_activities():
    """Load activities from JSON file"""
    with open(activities_file, 'r') as f:
        return json.load(f)

def save_activities_to_disk():
    """Save activities to JSON file (actual disk write)"""
    global activities_dirty
    with activities_lock:
        if not activities_dirty:
            return  # No changes to save
        try:
            # Create a snapshot of activities while holding the lock
            activities_snapshot = copy.deepcopy(activities)
        except Exception as e:
            print(f"Error creating snapshot of activities: {e}")
            return
    
    # Write to disk outside the lock to minimize lock duration
    try:
        with open(activities_file, 'w') as f:
            json.dump(activities_snapshot, f, indent=2)
        with activities_lock:
            activities_dirty = False
    except OSError as e:
        # Log error but don't raise - background task should continue
        print(f"Error saving activities: {e}")

def mark_activities_dirty():
    """Mark activities as modified"""
    global activities_dirty
    with activities_lock:
        activities_dirty = True

def periodic_save():
    """Background task to periodically save activities"""
    while not shutdown_event.is_set():
        # Use wait instead of sleep for more responsive shutdown
        if shutdown_event.wait(SAVE_INTERVAL_SECONDS):
            # shutdown_event was set, exit immediately without saving
            # (lifespan handler will do the final save)
            break
        save_activities_to_disk()

# Load activities at startup
activities = load_activities()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown events"""
    global save_thread
    # Startup: Start background save thread
    save_thread = threading.Thread(target=periodic_save, daemon=True)
    save_thread.start()
    yield
    # Shutdown: Stop background thread and save pending changes
    shutdown_event.set()
    if save_thread:
        save_thread.join(timeout=SHUTDOWN_TIMEOUT_SECONDS)
    save_activities_to_disk()

app = FastAPI(
    title="Mergington High School API",
    description="API for viewing and signing up for extracurricular activities",
    lifespan=lifespan
)

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Validate activity is not at maximum capacity (if a limit is defined)
    max_participants = activity.get("max_participants")
    if max_participants is not None:
        current_count = len(activity.get("participants", []))
        if current_count >= max_participants:
            raise HTTPException(
                status_code=400,
                detail="Activity is at full capacity"
            )
    # Add student
    activity["participants"].append(email)
    mark_activities_dirty()  # Mark for batched save
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    mark_activities_dirty()  # Mark for batched save
    return {"message": f"Unregistered {email} from {activity_name}"}
