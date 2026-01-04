"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
import json
from pathlib import Path

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# Load activities from JSON file
activities_file = os.path.join(Path(__file__).parent, "activities.json")

def load_activities():
    """Load activities from JSON file"""
    with open(activities_file, 'r') as f:
        return json.load(f)

def save_activities():
    """Save activities to JSON file"""
    try:
        with open(activities_file, 'w') as f:
            json.dump(activities, f, indent=2)
    except OSError:
        # Convert file I/O errors into a clear HTTP error response
        raise HTTPException(
            status_code=500,
            detail="Failed to save activities"
        )

# Load activities at startup
activities = load_activities()


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
    save_activities()  # Persist changes to JSON file
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
    save_activities()  # Persist changes to JSON file
    return {"message": f"Unregistered {email} from {activity_name}"}
