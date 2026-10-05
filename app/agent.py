# ruff: noqa
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

import datetime
import inspect
import json
import logging
import os

logger = logging.getLogger(__name__)
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from .a2ui_utils import a2ui_callback

# HARDCODED GCP PROJECT ID & STORAGE BUCKET NAME
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-01-8d05ffe23a8a"
GCS_BUCKET_NAME = "fitcoach-ai-assets-8d05ffe23a8a"

# Load Agent Engine resource name from deployment_metadata.json if available
deployment_metadata_path = Path(__file__).parent.parent / "deployment_metadata.json"
agent_engine_resource_name = None

if deployment_metadata_path.exists():
    try:
        with open(deployment_metadata_path, "r") as f:
            metadata = json.load(f)
            agent_engine_resource_name = metadata.get("remote_agent_runtime_id")
    except Exception as e:
        print(f"Warning: Failed to load deployment_metadata.json: {e}")

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name
)

# Set memory service environment variable so it's used when deployed or run
if agent_engine_resource_name:
    memory_bank_id = agent_engine_resource_name.split("/")[-1]
    os.environ["GOOGLE_CLOUD_AGENT_ENGINE_ID"] = memory_bank_id
elif "GOOGLE_CLOUD_AGENT_ENGINE_ID" not in os.environ:
    os.environ["GOOGLE_CLOUD_AGENT_ENGINE_ID"] = "5044312507875852288"


async def generate_memories_callback(callback_context: CallbackContext):
    """Callback after agent execution to extract and store durable facts into Memory Bank."""
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        logger.warning(f"Failed to add session to memory: {e}")
    return None


def get_firestore_client() -> firestore.Client:
    """Returns a Firestore client initialized with the hardcoded GCP project ID."""
    return firestore.Client(project=FIRESTORE_PROJECT_ID)


def search_firestore_exercises(
    muscle_group: str,
    equipment: str,
) -> Dict[str, Any]:
    """Queries the Cloud Firestore database for exercises matching muscle group or equipment.

    Args:
        muscle_group: Primary muscle group (e.g., 'chest', 'back', 'legs', 'shoulders', 'arms', 'core', 'all').
        equipment: Equipment filter (e.g., 'barbell', 'dumbbell', 'bodyweight', 'machine', 'cables', 'all').

    Returns:
        A dictionary containing status, count, and matching exercise records from Firestore.
    """
    db = get_firestore_client()
    col_ref = db.collection("exercises")
    docs = col_ref.stream()

    matches = []
    m_query = muscle_group.lower()
    e_query = equipment.lower()

    for doc in docs:
        item = doc.to_dict()
        doc_muscle = item.get("muscle_group", "").lower()
        doc_equip = item.get("equipment", "").lower()

        muscle_match = (m_query == "all") or (m_query in doc_muscle)
        equip_match = (e_query == "all") or (e_query in doc_equip)

        if muscle_match and equip_match:
            matches.append(item)

    return {
        "status": "success",
        "source": "firestore",
        "project_id": FIRESTORE_PROJECT_ID,
        "count": len(matches),
        "exercises": matches,
    }


def get_firestore_exercise_details(
    exercise_id: str,
) -> Dict[str, Any]:
    """Retrieves full details for a specific exercise document from Cloud Firestore by its ID.

    Args:
        exercise_id: Unique document ID of the exercise in Firestore (e.g., 'barbell_bench_press', 'barbell_deadlift').

    Returns:
        A dictionary with exercise details or an error message if not found.
    """
    db = get_firestore_client()
    doc_ref = db.collection("exercises").document(exercise_id)
    doc = doc_ref.get()

    if doc.exists:
        return {
            "status": "success",
            "source": "firestore",
            "exercise_id": exercise_id,
            "data": doc.to_dict(),
        }
    return {
        "status": "not_found",
        "message": f"No exercise document found in Firestore with ID '{exercise_id}'.",
    }


def add_firestore_exercise(
    exercise_id: str,
    name: str,
    muscle_group: str,
    equipment: str,
    difficulty: str,
    instructions: str,
    safety_tips: str,
    target_sets_reps: str,
) -> Dict[str, Any]:
    """Creates or updates a custom exercise entry in the Cloud Firestore database.

    Args:
        exercise_id: Unique string identifier for the new exercise (e.g., 'cable_flyes').
        name: Display name of the exercise (e.g., 'Cable Chest Flyes').
        muscle_group: Targeted muscle group ('chest', 'back', 'legs', 'shoulders', 'arms', 'core').
        equipment: Required equipment ('barbell', 'dumbbell', 'cables', 'bodyweight', 'machine').
        difficulty: Exercise difficulty level ('beginner', 'intermediate', 'advanced').
        instructions: Brief step-by-step form instructions.
        safety_tips: Key injury-prevention or safety guidelines.
        target_sets_reps: Standard recommended sets and rep scheme (e.g., '3 sets of 12-15 reps').

    Returns:
        Confirmation dictionary with saved document details.
    """
    db = get_firestore_client()
    exercise_doc = {
        "id": exercise_id,
        "name": name,
        "muscle_group": muscle_group,
        "equipment": equipment,
        "difficulty": difficulty,
        "instructions": instructions,
        "safety_tips": safety_tips,
        "target_sets_reps": target_sets_reps,
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    db.collection("exercises").document(exercise_id).set(exercise_doc)

    return {
        "status": "success",
        "message": f"Successfully added exercise '{name}' to Firestore.",
        "project_id": FIRESTORE_PROJECT_ID,
        "exercise": exercise_doc,
    }


def generate_workout_visual_image(
    prompt: str,
    image_type: str,
    tool_context: ToolContext,
) -> Dict[str, Any]:
    """Generates an image for fitness exercise form guides, motivational art, or milestone badges using gemini-3.1-flash-lite-image in the global region.

    Saves the image as an ADK artifact for the Playground and uploads it to Cloud Storage to return a public HTTPS URL.

    Args:
        prompt: Detailed visual prompt describing the exercise form, workout badge, or motivational visual to generate.
        image_type: Type/category tag for the visual (e.g., 'exercise_form', 'motivation_art', 'milestone_badge').

    Returns:
        A dictionary containing the public Cloud Storage HTTPS URL, filename, and status.
    """
    genai_client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")
    response = genai_client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=prompt,
    )

    image_bytes = None
    mime_type = "image/jpeg"
    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                image_bytes = part.inline_data.data
                mime_type = part.inline_data.mime_type or "image/jpeg"
                break

    if not image_bytes:
        return {
            "status": "error",
            "message": "Failed to extract image bytes from model response.",
        }

    ext = "png" if "png" in mime_type else "jpg"
    safe_type = "".join(c if c.isalnum() or c == "_" else "_" for c in image_type.lower())
    timestamp = int(datetime.datetime.now().timestamp())
    filename = f"{safe_type}_{timestamp}.{ext}"

    # 1. Save as ADK artifact so it appears in Playground's Artifacts panel
    artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    save_res = tool_context.save_artifact(filename=filename, artifact=artifact_part)
    if inspect.isawaitable(save_res):
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(save_res)
        except RuntimeError:
            asyncio.run(save_res)

    # 2. Upload same image bytes to public Cloud Storage bucket
    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"

    return {
        "status": "success",
        "public_url": public_url,
        "filename": filename,
        "prompt": prompt,
        "message": f"Successfully generated image and uploaded to Cloud Storage: {public_url}",
    }


def generate_exercise_demo_video(
    prompt: str,
    tool_context: ToolContext,
) -> Dict[str, Any]:
    """Generates a short demonstration video for a fitness exercise using Google's Omni model (gemini-omni-flash-preview) in the global region.

    Saves the video as an ADK artifact for the Playground and uploads it directly to Cloud Storage (without writing to a local file) to return a public HTTPS URL.

    Args:
        prompt: Detailed description of the exercise form or workout demonstration video to generate (e.g., 'A 3-second video demonstrating a dumbbell bicep curl with proper form').

    Returns:
        A dictionary containing the public Cloud Storage HTTPS URL, filename, and status.
    """
    genai_client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")
    interaction = genai_client.interactions.create(
        model="gemini-omni-flash-preview",
        input=prompt,
    )

    video_bytes = None
    mime_type = "video/mp4"

    if hasattr(interaction, "output_video") and interaction.output_video:
        vid = interaction.output_video
        raw_data = getattr(vid, "data", None)
        if raw_data:
            if isinstance(raw_data, bytes):
                video_bytes = raw_data
            elif isinstance(raw_data, str):
                import base64
                video_bytes = base64.b64decode(raw_data)
        if getattr(vid, "mime_type", None):
            mime_type = vid.mime_type

    if not video_bytes:
        dump = interaction.model_dump()
        out_vid = dump.get("output_video")
        if out_vid and isinstance(out_vid, dict):
            raw_data = out_vid.get("data")
            if raw_data:
                if isinstance(raw_data, str):
                    import base64
                    video_bytes = base64.b64decode(raw_data)
                elif isinstance(raw_data, bytes):
                    video_bytes = raw_data
            mime_type = out_vid.get("mime_type", "video/mp4")

    if not video_bytes:
        return {
            "status": "error",
            "message": "Failed to extract video bytes from gemini-omni-flash-preview interaction response.",
        }

    import uuid
    filename = f"exercise_demo_{uuid.uuid4().hex[:8]}.mp4"

    # 1. Save with tool_context.save_artifact so it shows up in Playground's Artifacts panel
    artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
    save_res = tool_context.save_artifact(filename=filename, artifact=artifact_part)
    if inspect.isawaitable(save_res):
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(save_res)
        except RuntimeError:
            asyncio.run(save_res)

    # 2. Upload same video bytes directly to public Cloud Storage bucket (without writing to disk)
    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(video_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"

    return {
        "status": "success",
        "public_url": public_url,
        "filename": filename,
        "prompt": prompt,
        "message": f"Successfully generated exercise demo video and uploaded to Cloud Storage: {public_url}",
    }


def lookup_food_nutrition_facts(
    query: str,
) -> Dict[str, Any]:
    """Looks up real-world food items, calories, and macronutrient data per 100g from the USDA FoodData Central API.

    Args:
        query: Food product or ingredient search query (e.g., 'greek yogurt', 'whey protein', 'oats', 'chicken breast').

    Returns:
        A dictionary containing matching food products with calories, protein, carbs, fats, and brand info.
    """
    encoded_query = urllib.parse.quote(query)
    api_key = os.environ.get("USDA_API_KEY", "DEMO_KEY")
    url = f"https://api.nal.usda.gov/fdc/v1/foods/search?query={encoded_query}&pageSize=3&api_key={api_key}"

    req = urllib.request.Request(url, headers={"User-Agent": "FitCoachAI/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        products = []
        for food in data.get("foods", []):
            nutrients = {}
            for n in food.get("foodNutrients", []):
                name = n.get("nutrientName", "").lower()
                val = n.get("value", 0.0)
                if "energy" in name:
                    nutrients["calories"] = round(val, 1)
                elif "protein" in name:
                    nutrients["protein_g"] = round(val, 1)
                elif "carbohydrate" in name:
                    nutrients["carbs_g"] = round(val, 1)
                elif "lipid" in name or "fat" in name:
                    nutrients["fat_g"] = round(val, 1)

            products.append({
                "food_name": food.get("description", "Unknown Food"),
                "brand": food.get("brandOwner", "Generic / Standard Reference"),
                "calories": nutrients.get("calories", 0.0),
                "protein_g": nutrients.get("protein_g", 0.0),
                "carbs_g": nutrients.get("carbs_g", 0.0),
                "fat_g": nutrients.get("fat_g", 0.0),
            })

        return {
            "status": "success",
            "query": query,
            "source": "USDA FoodData Central API",
            "count": len(products),
            "products": products,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to fetch food nutrition data: {str(e)}",
        }


def calculate_one_rep_max_and_warmups(
    exercise_name: str,
    weight_kg: float,
    reps: int,
) -> Dict[str, Any]:
    """Calculates estimated One-Rep Max (1RM), percentage training zones, and warmup set progressions.

    Args:
        exercise_name: Name of the exercise (e.g., 'Bench Press', 'Squat', 'Deadlift').
        weight_kg: Weight lifted in kilograms or pounds.
        reps: Number of repetitions completed with good form (1-12).

    Returns:
        A dictionary with estimated 1RM, working weight percentages, and warmup recommendations.
    """
    if reps <= 1:
        estimated_1rm = weight_kg
    else:
        epley = weight_kg * (1 + reps / 30.0)
        brzycki = weight_kg * (36.0 / (37.0 - reps)) if reps < 37 else epley
        estimated_1rm = round((epley + brzycki) / 2.0, 1)

    percentages = {
        "90_percent_heavy_strength": round(estimated_1rm * 0.90, 1),
        "80_percent_hypertrophy": round(estimated_1rm * 0.80, 1),
        "70_percent_endurance": round(estimated_1rm * 0.70, 1),
    }

    warmup_sets = [
        {"set": 1, "weight": round(estimated_1rm * 0.40, 1), "reps": "10 reps", "note": "Light movement prep"},
        {"set": 2, "weight": round(estimated_1rm * 0.60, 1), "reps": "5 reps", "note": "Moderate build-up"},
        {"set": 3, "weight": round(estimated_1rm * 0.75, 1), "reps": "3 reps", "note": "Heavy neural prep"},
    ]

    return {
        "status": "success",
        "exercise": exercise_name,
        "input_weight": weight_kg,
        "input_reps": reps,
        "estimated_1rm": estimated_1rm,
        "training_zones": percentages,
        "recommended_warmup_pyramid": warmup_sets,
    }


def calculate_tdee_and_macros(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str,
    activity_level: str,
    goal: str,
    tool_context: ToolContext,
) -> Dict[str, Any]:
    """Calculates BMR, TDEE, target calories, and macronutrient distributions for a user.

    Args:
        weight_kg: User weight in kilograms.
        height_cm: User height in centimeters.
        age: User age in years.
        gender: Gender ('male' or 'female').
        activity_level: Activity multiplier level ('sedentary', 'light', 'moderate', 'active', 'very_active').
        goal: Weight goal ('weight_loss', 'maintenance', 'muscle_gain').

    Returns:
        A dictionary containing BMR, TDEE, target calories, and macronutrient breakdown in grams.
    """
    if gender.lower() == "male":
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    else:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161

    activity_multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9,
    }
    multiplier = activity_multipliers.get(activity_level.lower(), 1.375)
    tdee = bmr * multiplier

    if goal.lower() == "weight_loss":
        target_calories = tdee - 500
    elif goal.lower() == "muscle_gain":
        target_calories = tdee + 300
    else:
        target_calories = tdee

    protein_g = (target_calories * 0.30) / 4
    fats_g = (target_calories * 0.25) / 9
    carbs_g = (target_calories * 0.45) / 4

    stats = {
        "bmr_kcal": round(bmr, 1),
        "tdee_kcal": round(tdee, 1),
        "target_calories_kcal": round(target_calories, 1),
        "macros_g": {
            "protein": round(protein_g, 1),
            "carbs": round(carbs_g, 1),
            "fats": round(fats_g, 1),
        },
        "calculated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    tool_context.state["body_stats"] = {
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "age": age,
        "gender": gender,
    }
    tool_context.state["nutrition_goals"] = stats

    return {"status": "success", "data": stats}


def update_user_fitness_profile(
    fitness_goals: str,
    injury_history: str,
    experience_level: str,
    tool_context: ToolContext,
    allergies: str = "none",
) -> Dict[str, Any]:
    """Updates and saves the user's fitness profile, injury history, allergies/dietary restrictions, and experience level in session memory.

    Args:
        fitness_goals: Primary fitness objectives (e.g., 'hypertrophy', 'fat loss', 'strength', 'marathon training').
        injury_history: Any past or current injuries or physical limitations (e.g., 'lower back pain', 'rotator cuff tear', 'none').
        experience_level: Training experience level ('beginner', 'intermediate', 'advanced').
        allergies: Food allergies, dietary restrictions, or intolerances (e.g., 'peanuts', 'lactose', 'gluten', 'shellfish', 'none').

    Returns:
        Confirmation dictionary with saved profile state.
    """
    profile = {
        "fitness_goals": fitness_goals,
        "injury_history": injury_history,
        "experience_level": experience_level,
        "allergies": allergies,
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    tool_context.state["user_profile"] = profile
    return {"status": "success", "message": "User fitness profile updated in memory.", "profile": profile}


def log_workout_session(
    workout_name: str,
    exercises: str,
    total_duration_minutes: int,
    notes: str,
    tool_context: ToolContext,
) -> Dict[str, Any]:
    """Logs a completed workout session into user session history memory.

    Args:
        workout_name: Name or title of the workout (e.g., 'Upper Body Push A', 'Leg Day', 'Full Body Cardio').
        exercises: Comma-separated list or summary of exercises completed with sets/reps.
        total_duration_minutes: Duration of the workout session in minutes.
        notes: Additional notes on how the workout felt, energy levels, or weight lifted.

    Returns:
        Confirmation dictionary with total logged workout count.
    """
    history = tool_context.state.get("workout_history", [])
    if not isinstance(history, list):
        history = []

    log_entry = {
        "workout_name": workout_name,
        "exercises": exercises,
        "duration_minutes": total_duration_minutes,
        "notes": notes,
        "logged_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    history.append(log_entry)
    tool_context.state["workout_history"] = history

    return {
        "status": "success",
        "message": f"Logged workout '{workout_name}'.",
        "total_workouts_logged": len(history),
        "entry": log_entry,
    }


def get_user_fitness_profile(
    tool_context: ToolContext,
) -> Dict[str, Any]:
    """Retrieves saved user profile, body stats, nutrition targets, allergies, and workout history from memory.

    Returns:
        Dictionary containing saved user profile, body stats, nutrition goals, allergies, and workout history.
    """
    profile = tool_context.state.get("user_profile", "No fitness profile saved yet.")
    body_stats = tool_context.state.get("body_stats", "No body stats recorded yet.")
    nutrition_goals = tool_context.state.get("nutrition_goals", "No nutrition targets calculated yet.")
    workout_history = tool_context.state.get("workout_history", [])

    return {
        "status": "success",
        "user_profile": profile,
        "body_stats": body_stats,
        "nutrition_goals": nutrition_goals,
        "total_logged_workouts": len(workout_history) if isinstance(workout_history, list) else 0,
        "recent_workouts": workout_history[-3:] if isinstance(workout_history, list) else [],
    }


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

fitcoach_instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are FitCoach AI, an elite, encouraging, and science-backed AI Fitness & Workout Coach "
        "backed by Cloud Firestore database persistence, a sandboxed Python code executor, and Vertex AI Memory Bank."
    ),
    workflow_description=(
        "Help users design custom, effective workout routines, lookup exercises in Cloud Firestore, check food nutrition, "
        "calculate 1RM and warmup pyramids, calculate TDEE and macros, generate short exercise demonstration videos using Google's Omni model, and generate visual guides or milestone badges. "
        "Analyze the user's request and return structured UI surfaces when appropriate."
    ),
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows or Rows of Text. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). Build tables from Rows and Columns of Text, and use Text "
        "with the usageHint property ('h1', 'h2', 'body') for headings and emphasis. "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the public_url returned by generate_workout_visual_image "
        "which uploads to Cloud Storage). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://storage.googleapis.com/...\"}}}. "
        "Never point an Image at a bare filename, an artifact name, or a non-http(s) path. "
        "If you do not have a public URL, add a short Text line noting the image instead. "
        "Cross-Session Memory & Allergy Safety: PreloadMemoryTool automatically retrieves cross-session user memories at turn start into your context. "
        "You MUST strictly remember and enforce all food allergies, intolerances, and dietary restrictions mentioned by the user (peanuts, gluten, dairy, shellfish, etc.). "
        "ALWAYS cross-check all meal plans, food nutrition lookups, and dietary advice against user allergies, and NEVER suggest foods containing their allergens. "
        "No markdown in text; use usageHint ('h1', 'h2', 'body') for headings. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=fitcoach_instruction,
    code_executor=code_executor,
    tools=[
        PreloadMemoryTool(),
        search_firestore_exercises,
        get_firestore_exercise_details,
        add_firestore_exercise,
        generate_workout_visual_image,
        generate_exercise_demo_video,
        lookup_food_nutrition_facts,
        calculate_one_rep_max_and_warmups,
        update_user_fitness_profile,
        calculate_tdee_and_macros,
        log_workout_session,
        get_user_fitness_profile,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
