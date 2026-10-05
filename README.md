# FitCoach AI — Personal Fitness & Nutrition AI Agent

FitCoach AI is an intelligent, multi-modal personal fitness and nutrition assistant built on the Google Agent Development Kit (ADK), Google Cloud, and Vertex AI. It helps users design custom hypertrophy workout routines, search exercise databases, compute precise nutritional macro splits and One-Rep Max warmups, generate exercise demo videos, and visualize workout achievements with AI-generated visual badges.

![FitCoach AI Demo](demo.gif)

---

## 🌟 Implemented Features & Architecture

FitCoach AI connects LLM reasoning with real-world fitness tools and Google Cloud infrastructure:

### 🧠 Core Agent & Memory
* **Vertex AI Memory Bank Engine**: Persists long-term user fitness preferences, workout history, and personal goals across conversational sessions via automated memory callbacks (`PreloadMemoryTool` and `generate_memories_callback`).

### 🗄️ Database & Storage Services
* **Cloud Firestore**: Real-time database for exercise libraries (`exercises` collection) and persistent user fitness profiles (`users` collection).
* **Google Cloud Storage (GCS)**: Public asset bucket (`fitcoach-ai-assets-8d05ffe23a8a`) for storing generated workout badges and video media.

### 🎨 Multimodal Media Generation
* **Vertex AI Imagen 3 (`gemini-3.1-flash-lite-image`)**: Generates visual workout form guides, motivational achievement badges, and infographics directly within response cards.
* **Vertex AI Gemini Omni (`gemini-omni-flash-preview`)**: Generates short, AI-rendered exercise execution videos in the `global` location. Saves video bytes to ADK Playground Artifacts and uploads public video URLs to Cloud Storage.

### 🥗 Nutrition & Fitness Calculators
* **USDA FoodData Central API**: Fetches live nutritional data, calorie counts, macronutrients, and micronutrient profiles for foods.
* **TDEE & Macro Calculator**: Computes Total Daily Energy Expenditure (Mifflin-St Jeor equation) and goal-adjusted protein/carb/fat splits.
* **1RM & Warmup Pyramid Calculator**: Calculates One-Rep Max using Brzycki & Epley formulas and builds 5-set warm-up weight progression pyramids.

### 💻 Rich Adaptive UI (A2UI)
* **A2UI Schema Manager (v0.8)**: Generates structured, adaptive UI JSON components (Cards, Columns, Rows, Dividers, Images, Icons) rendered natively by the custom frontend interface.

---

## 🛠️ Project Structure

```
fitcoach-ai/
├── app/
│   ├── agent.py               # Main agent logic, tools, callbacks, and A2UI definitions
│   ├── fast_api_app.py        # FastAPI server wrapping ADK agent endpoints
│   └── app_utils/             # Helpers for memory, Firestore, and GCP credentials
├── frontend/                  # Web frontend interface
│   ├── static/index.html      # Responsive chat interface with A2UI renderer
│   ├── package.json           # Frontend dependencies & scripts
│   └── server.mjs             # Node.js proxy backend connecting frontend to Agent Engine
├── seed_firestore.py          # Script for populating Firestore exercise collection
├── pyproject.toml             # Python dependencies and project setup
├── agents-cli-manifest.yaml   # Manifest for agents-cli deployment
└── demo.gif                   # Recorded live application demonstration
```

---

## 🚀 Local Setup & Running Instructions

### Prerequisites
* **Python 3.11+** and [uv](https://docs.astral.sh/uv/) package manager
* **Node.js 18+** and `npm`
* **Google Cloud SDK** (`gcloud`) authenticated with access to Firestore, Vertex AI, and Cloud Storage

### 1. Install Backend Dependencies
From the project root:

```bash
uv pip install -e .
```

### 2. Seed Firestore Exercise Library
Initialize the exercise database in Cloud Firestore:

```bash
uv run python seed_firestore.py
```

### 3. Run Agent Backend (Playground / ADK)
To launch the agent locally using the ADK Playground:

```bash
agents-cli playground
```

Or run using ADK directly:

```bash
uv run adk web .
```

### 4. Run Custom Frontend
In a separate terminal, navigate to the `frontend/` directory and install dependencies:

```bash
cd frontend
npm install
```

Start the frontend development server:

```bash
npm run dev
```

---

## 🔒 Security & Environment Variables

Key configuration settings managed via environment variables or `.env`:

* `FIRESTORE_PROJECT_ID`: GCP project hosting Cloud Firestore.
* `GCS_BUCKET_NAME`: Public GCS bucket for AI-generated assets (`fitcoach-ai-assets-8d05ffe23a8a`).
* `USDA_API_KEY`: API key for FoodData Central nutrition lookups.
* `GOOGLE_GENAI_USE_VERTEXAI`: Set to `true` to route AI calls through Vertex AI.

---

## 📝 License

This project is built for the AI Governance & Agent Platform ecosystem using Google Agent Development Kit (ADK).
