# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import subprocess
import urllib.request

# HARDCODED GCP PROJECT ID
PROJECT_ID = "qwiklabs-gcp-01-8d05ffe23a8a"

SEED_EXERCISES = [
    {
        "id": "barbell_bench_press",
        "name": "Barbell Bench Press",
        "muscle_group": "chest",
        "equipment": "barbell",
        "difficulty": "intermediate",
        "instructions": "Lie flat on bench, grip barbell slightly wider than shoulder-width. Lower bar to mid-chest with control, press up until arms locked out.",
        "safety_tips": "Keep shoulder blades retracted and depressed. Do not bounce the bar off your chest.",
        "target_sets_reps": "3-4 sets of 6-10 reps"
    },
    {
        "id": "dumbbell_incline_press",
        "name": "Dumbbell Incline Press",
        "muscle_group": "chest",
        "equipment": "dumbbell",
        "difficulty": "beginner",
        "instructions": "Set bench to 30-degree incline. Press dumbbells up over upper chest, bringing them slightly together at the top.",
        "safety_tips": "Keep elbows angled at 45 degrees to body rather than flared out to 90 degrees.",
        "target_sets_reps": "3 sets of 8-12 reps"
    },
    {
        "id": "barbell_deadlift",
        "name": "Barbell Deadlift",
        "muscle_group": "back",
        "equipment": "barbell",
        "difficulty": "advanced",
        "instructions": "Stand with feet hip-width under bar. Hinge at hips, grip bar, pull shoulder blades back, drive through legs to stand tall.",
        "safety_tips": "Brace core hard and maintain neutral spine throughout movement. Never round lower back.",
        "target_sets_reps": "3 sets of 5 reps"
    },
    {
        "id": "dumbbell_bent_over_row",
        "name": "Dumbbell Bent-Over Row",
        "muscle_group": "back",
        "equipment": "dumbbell",
        "difficulty": "intermediate",
        "instructions": "Hinge at hips to a 45-degree angle. Pull dumbbells towards lower ribs driving back with elbows.",
        "safety_tips": "Keep neck neutral looking slightly ahead on floor.",
        "target_sets_reps": "3-4 sets of 8-12 reps"
    },
    {
        "id": "barbell_back_squat",
        "name": "Barbell Back Squat",
        "muscle_group": "legs",
        "equipment": "barbell",
        "difficulty": "intermediate",
        "instructions": "Position bar across upper traps. Unrack, step back, descend until thighs parallel with floor, drive up through midfoot.",
        "safety_tips": "Ensure knees track over toes. Avoid knee valgus (caving inward).",
        "target_sets_reps": "3 sets of 6-10 reps"
    },
    {
        "id": "goblet_squat",
        "name": "Goblet Squat",
        "muscle_group": "legs",
        "equipment": "dumbbell",
        "difficulty": "beginner",
        "instructions": "Hold dumbbell vertically at chest level. Squat down between knees keeping torso upright.",
        "safety_tips": "Keep elbows inside knees at bottom position.",
        "target_sets_reps": "3 sets of 10-15 reps"
    },
    {
        "id": "overhead_dumbbell_press",
        "name": "Overhead Dumbbell Press",
        "muscle_group": "shoulders",
        "equipment": "dumbbell",
        "difficulty": "intermediate",
        "instructions": "Seated or standing, press dumbbells vertically overhead until locked out above head.",
        "safety_tips": "Squeeze glutes and core to avoid excessive lower back arching.",
        "target_sets_reps": "3 sets of 8-12 reps"
    }
]

def py_to_firestore_fields(data: dict) -> dict:
    fields = {}
    for k, v in data.items():
        if isinstance(v, str):
            fields[k] = {"stringValue": v}
        elif isinstance(v, int):
            fields[k] = {"integerValue": str(v)}
        elif isinstance(v, float):
            fields[k] = {"doubleValue": v}
        elif isinstance(v, bool):
            fields[k] = {"booleanValue": v}
    return fields

def seed_firestore():
    print(f"Connecting to Firestore for project '{PROJECT_ID}'...")
    token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()

    for item in SEED_EXERCISES:
        doc_id = item["id"]
        url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/exercises/{doc_id}"
        payload = json.dumps({"fields": py_to_firestore_fields(item)}).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="PATCH"
        )
        with urllib.request.urlopen(req) as resp:
            if resp.status in (200, 201):
                print(f"  [+] Seeded exercise: {item['name']} ({doc_id})")

    print("Firestore seeding complete!")

if __name__ == "__main__":
    seed_firestore()
