## Smart Food Discovery Agent

AI-powered food travel guide and restaurant discovery experience.

Click anywhere on an interactive 3D globe, let the agent understand where you are, and get **short, curated recommendations** for:

- **Local food culture** and must-try dishes
- **Nearby restaurants, cafes, and bars**
- **Specific restaurant deep dives** (reviews + “what makes it special”)

The system is split into:

- **Backend (`backend/`)** – FastAPI + LangChain/LangGraph + Groq + Brave Search + OpenStreetMap/Wikipedia.
- **Frontend (`frontend/`)** – Next.js App Router + React + Tailwind-based UI + globe visualization + streaming AI chat.

---

## Project Structure

### Root

- **`backend/`** – Python FastAPI service and LangChain / data-fetching logic.
- **`frontend/`** – Next.js frontend app (Vercel-ready).
- **`README.md`** – This file.
- **`.gitignore`** – Git ignores for Python, Node, etc.

### Backend (`backend/`)

- **`main.py`**
  - Defines the **FastAPI app** `Smart Food Discovery API`.
  - Endpoints:
    - **`POST /chat`** – One-shot chat with the agent.
      - Request body (`ChatRequest`):
        - `lat`, `lon`: user coordinates.
        - `location_name`: human-readable location label.
        - `message`: user question.
        - `preferences`: optional text (“I like spicy food, cheap eats…”).
        - `restaurant_yelp_id`: optional stable ID for a specific restaurant.
      - Internally:
        - Calls `run_agent(...)` from `agent.py` to get a concise answer + tools used.
        - Calls `search_restaurants(...)` from `food.py` to fetch nearby restaurants.
      - Response (`ChatResponse`):
        - `response`: final answer text (≤ 50 words, enforced in the agent prompt).
        - `tools_used`: list of tool names the agent called.
        - `restaurants`: list of restaurant dicts.
        - `type`: `"chat"`.
    - **`POST /chat/stream`** – **Server-Sent Events (SSE)** streaming chat.
      - Wraps `run_agent_stream(...)` from `agent.py`.
      - Streams incremental tokens (`type: "token"`) and a final `done` event:
        - Includes `tools_used`, `full_response`, and `restaurants`.
    - **`GET /food/restaurants`**
      - Query params: `lat`, `lon`.
      - Calls `search_restaurants(...)` in `food.py` and returns `{"restaurants": [...]}`.
    - **`POST /location/summary`**
      - Used when the user “clicks on the map”.
      - Builds a fixed internal question like:
        - “What is this place like, what is it known for, and what are great things to eat nearby?”
      - Calls `run_agent(...)` and `search_restaurants(...)` to return:
        - Short textual overview + restaurant list.
      - Response model: `LocationSummaryResponse`.
    - **`GET /food/reviews`**
      - Query params: `city`, optional `dish_or_restaurant`.
      - Uses `brave_search_food_reviews(...)` to fetch review-like web results.
    - **`GET /health`**
      - Returns `{ status: "ok", openai_configured: bool }`.
      - Checks for `OPENAI_API_KEY` or `CHATGPT_API_KEY` in env (optional).
  - CORS is configured to **allow `http://localhost:3000`** (frontend dev).

- **`agent.py`**
  - Builds the **LangGraph-based ReAct agent** with Groq:
    - Uses `ChatGroq` with model `meta-llama/llama-4-scout-17b-16e-instruct`.
    - System prompt:
      - Agent is a **world-class food travel guide**.
      - **Hard constraint**: final response **must be ≤ 50 words**.
      - Always:
        - Use `get_location_name_tool` when the location looks like raw coordinates.
        - Use `brave_search_tool` + `get_local_dishes_tool` + `search_restaurants_tool` for good coverage.
      - For reviews and comprehensive overviews, prioritize Brave search-based tools.
  - Tool registry (`TOOLS`):
    - `search_restaurants_tool`, `search_food_reviews_tool`, `search_regional_food_tool`,
      `get_city_food_culture_tool`, `get_trending_dishes_tool`, `get_location_name_tool`,
      `get_local_dishes_tool`, `brave_search_tool` (all defined in `tools.py`).
  - **`get_agent()`**
    - Lazy-creates and caches the agent using `GROQ_API_KEY`.
  - **`run_agent(...)`**
    - Builds a context string from:
      - `location_name`, `lat`, `lon`, `preferences`, and `restaurant_yelp_id` (if provided).
    - Invokes the agent with `{"messages": [("user", full_input)]}`.
    - Extracts the most recent plain AI message (no tool calls) as the final answer.
    - Walks messages to extract **unique tool names** used.
  - **`run_agent_stream(...)`**
    - Same context as `run_agent`.
    - Uses `agent.astream(..., stream_mode=["messages", "values"])` to:
      - Yield individual **text tokens** as `"token"` events.
      - Accumulate `tools_used` and `full_response`, then emit a final `"done"` event.

- **`tools.py`**
  - Wraps low-level `food.py` functions into **LangChain tools** using `@tool`.
  - Tools:
    - **`search_restaurants_tool`**
      - Inputs: `lat`, `lon`, optional `cuisine`, `limit`.
      - Calls `search_restaurants(...)` and returns a **formatted multiline string** with:
        - Names, cuisine, rating, review count, address, hours, URLs, short description.
      - Also uses `brave_count_restaurants(...)` to estimate restaurant density.
    - **`search_food_reviews_tool`**
      - Uses `brave_search_food_reviews(...)` for city + dish/restaurant.
      - Returns a bulleted list of review snippets.
    - **`search_regional_food_tool`**
      - Uses `brave_search_food(...)`.
      - Focused on **“what is this region known for?”** food-wise.
    - **`get_city_food_culture_tool`**
      - Returns a trimmed text snippet from Wikipedia via `get_city_food_culture(...)`.
    - **`get_trending_dishes_tool`**
      - Uses `get_trending_dishes(...)` to get trending dishes and short descriptions.
    - **`get_location_name_tool`**
      - Uses `reverse_geocode(...)` to convert lat/lon into `{city, state, country}`.
    - **`get_local_dishes_tool`**
      - Uses `get_local_dishes(...)` to stitch together:
        - Wikipedia-derived dishes.
        - Brave search dishes.
        - Local restaurant cuisine tags.
    - **`brave_search_tool`**
      - Uses `brave_search_comprehensive(...)` to get an LLM-summarized overview of web results.

- **`food.py`**
  - **External endpoints/constants**:
    - `NOMINATIM_REVERSE` – OpenStreetMap Nominatim reverse geocoding.
    - `OVERPASS_URL` – Overpass API for OpenStreetMap.
    - `WIKIPEDIA_REST` – Wikipedia REST endpoint (HTML).
    - `BRAVE_SEARCH_URL`, `BRAVE_LOCAL_POIS_URL`, `BRAVE_LOCAL_DESC_URL` – Brave Search web + local POIs.
  - **Core helpers**:
    - `_make_restaurant_id(name, address)` – builds a **stable, URL-safe ID** for restaurants.
    - `_brave_headers()` – attaches `BRAVE_SEARCH_API_KEY` if configured.
    - `_brave_web_search(query, ...)` – thin wrapper around Brave Web Search.
    - `_get_llm()` – Groq `ChatGroq` configured for extraction / summarization.
  - **Brave-based helpers**:
    - `brave_search_comprehensive(query, count)` – full-text web search + Groq summarization for overviews.
    - `brave_search_food(city, query_extra)` – food-focused search results for a city.
    - `brave_search_food_reviews(city, dish_or_restaurant)` – review-focused web results.
    - `brave_search_restaurants(lat, lon, city, cuisine, limit)` – restaurant results, uses Brave local enrichments if available.
    - `brave_count_restaurants(lat, lon, city, cuisine)` – approximate restaurant counts using Brave meta fields.
    - `_enrich_brave_locations(locations)` – calls `BRAVE_LOCAL_POIS_URL` and maps into restaurant objects.
    - `brave_llm_restaurants(lat, lon, city, limit)` – uses Brave web results + Groq to **LLM-extract structured restaurants**.
  - **Restaurant and food discovery**:
    - `search_restaurants(lat, lon, cuisine, limit)`:
      1. Reverse geocodes coordinates to get `city`.
      2. Tries `brave_llm_restaurants(...)`.
      3. Falls back to `brave_search_restaurants(...)`.
      4. If needed, falls back to **Overpass API (OpenStreetMap)** to query `amenity=restaurant|cafe|bar|fast_food` around the point.
    - `get_city_food_culture(city)`:
      - Calls Wikipedia REST HTML, strips tags, and tries to extract food/cuisine sections.
    - `reverse_geocode(lat, lon)`:
      - Uses Nominatim to get `city`, `state`, `country`, and display name.
    - `get_local_dishes(lat, lon, city)`:
      - Combines Wikipedia + Brave + local cuisines to infer local dishes and cuisine tags.
    - `get_trending_dishes(city)`:
      - Brave-powered trending/must-try dishes.
  - **`requirements.txt`**
    - Includes `fastapi`, `uvicorn`, `httpx`, `python-dotenv`, `langchain-groq`, `langgraph`, etc.
  - **`.env.example`**
    - Template for backend environment variables (you copy to `.env`).

### Frontend (`frontend/`)

High-level: **Next.js 16 App Router**, **React 19**, **Tailwind v4**, streaming AI chat using `@ai-sdk/react` and Groq, plus a **3D globe** for selecting locations.

- **`package.json`**
  - **Runtime deps**:
    - `next`, `react`, `react-dom`
    - `ai`, `@ai-sdk/react`, `@ai-sdk/groq`, `@ai-sdk/openai`
    - `globe.gl`, `three`, `@googlemaps/js-api-loader`
    - `lucide-react`, `framer-motion`, `react-markdown`, `zod`
  - **Scripts**:
    - `npm run dev` – dev server.
    - `npm run build` – production build.
    - `npm start` – start built app.
    - `npm run lint` – ESLint.

- **`src/app/page.tsx`**
  - Main landing page (`/`).
  - State:
    - `selectedLocation` – `{ lat, lon, name }` or `null`.
    - `restaurants` – list of `Restaurant` from backend.
    - `tagline` – short summary of current city’s food scene (fed from chat).
    - `activeMenu` – `"discover"` or `"restaurants"`.
    - `visitedCities` – list of previously clicked/selected locations.
    - `programmaticMessage` / `programmaticYelpId` – programmatic prompts sent to chat (e.g., from clicking a restaurant card).
  - Components (by import name):
    - `GlobeWithNoSSR` – dynamic import of `Globe` (client-only 3D globe).
    - `SearchBar` – search by city/place name (calls `loadLocationData`).
    - `VisitedCities` – list of previously selected cities with quick re-focus and remove.
    - `LocationOverlay` – shows current location + loading state over the globe.
    - `FoodPanel` – summary panel for city/tagline + counts.
    - `RestaurantGrid` – grid of nearby restaurants with “Ask about this place” actions.
    - `AgentChat` – main chat component streaming from `/api/chat/stream`.
  - `loadLocationData(lat, lon, name)`:
    - Sets current selection, shows loading.
    - Fetches nearby restaurants via `fetchRestaurants(lat, lon)` (wrapper to backend `GET /food/restaurants`).
    - Seeds `programmaticMessage` with a **passionate overview request** for the selected city.
  - Menu behavior:
    - **Discover**:
      - Shows nearby restaurant grid (if any) + chat.
      - Automatically sends an overview-style question.
    - **Restaurants**:
      - Focuses UI on restaurant list + chat targeted at restaurant Q&A.
    - Clicking on a restaurant:
      - Sets `programmaticMessage` like “Tell me more about X - what makes it special?”
      - Also passes a stable restaurant identifier (id/yelp_id/name) to the backend.

- **`src/components/AgentChat.tsx`**
  - Client-side, uses `useChat` from `@ai-sdk/react` with **SSE streaming**:
    - API: `/api/chat/stream` (Next.js route – see below).
  - Enhancements:
    - Custom **markdown renderer** with `react-markdown`:
      - Highlights restaurant names in responses.
      - Styled headings, bullet lists, links, code, blockquotes.
    - Shows which tools the model used (e.g. `🗺️ restaurants`, `⭐ reviews`) based on tool call metadata.
    - Suggested chip prompts for each menu context:
      - Discover / Restaurants / Guide.
    - Extracts a **“tagline”** from the first response to show in `FoodPanel`.
    - Automatically sends programmatic questions when:
      - Menu changes (Discover/Restaurants).
      - User clicks a restaurant in `RestaurantGrid`.

- **`src/app/api/chat/stream/route.ts`**
  - **Next.js API route** used by `AgentChat`.
  - Uses `ai` + Groq:
    - `streamText`, `tool`, `convertToModelMessages`, `stepCountIs`.
    - `createGroq` with `GROQ_API_KEY`.
  - Reads request body:
    - `messages` (UIMessage[] from frontend chat hook).
    - `lat`, `lon`, `location_name`, `preferences`, `active_menu`, `restaurant_yelp_id`.
  - System prompt:
    - Includes location + menu context + preferences.
    - Enforces **“Keep responses under 50 words. Use short bullet points. Include food emojis.”**
  - Defines **inline tools** (these proxy the Python backend):
    - `search_restaurants_tool`:
      - Calls `${API_BASE}/food/restaurants?lat=...&lon=...` where `API_BASE = process.env.API_URL ?? "http://localhost:8000"`.
    - `search_restaurant_reviews_tool`:
      - Calls `${API_BASE}/food/reviews?city=...&dish_or_restaurant=...`.
  - Uses `stopWhen: stepCountIs(5)` to keep tool use bounded.
  - Returns an SSE **UI message stream** compatible with `@ai-sdk/react`.

- **`src/types/index.ts`**
  - Shared frontend types:
    - `Restaurant`, `FoodEvent`, `Location`, `ChatMessage`, `Preferences`.

> Note: Several components (`Globe`, `FoodPanel`, `RestaurantGrid`, etc.) live in `frontend/src/components/` and are responsible purely for presentation/UX around the data and chat system described above.

---

## Environment Variables

### Backend (`backend/.env`)

Copy `.env.example` to `.env` and fill in:

- **`GROQ_API_KEY`** – required for all Groq LLM calls.
- **`BRAVE_SEARCH_API_KEY`** – required for Brave web + local search.
- Optional:
  - **`OPENAI_API_KEY` / `CHATGPT_API_KEY`** – only used by `/health` to report if OpenAI is configured (not core to functionality).

Other external APIs (Nominatim, Overpass, Wikipedia) are **free and keyless**, but must respect rate limits.

### Frontend (`frontend` environment)

For local dev:

- **`GROQ_API_KEY`** – used by the Next.js API route to talk to Groq.
- **`API_URL`** – base URL of the backend FastAPI service.
  - Local dev default is `http://localhost:8000`.
  - In production (e.g. Render/Railway), set to your deployed backend URL.

On Vercel, you will configure these as **Project Environment Variables**.

---

## Local Development Setup

### 1. Clone and install

```bash
git clone <your-repo-url> aiproject
cd aiproject
```

### 2. Backend setup (FastAPI)

```bash
cd backend
cp .env.example .env
# Edit .env and set GROQ_API_KEY, BRAVE_SEARCH_API_KEY, etc.

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run the API server
uvicorn main:app --reload --port 8000
```

Backend will now be available at **`http://localhost:8000`**.

Key endpoints for debugging:

- **`GET /health`** – simple health check.
- **`GET /food/restaurants?lat=...&lon=...`** – inspect raw restaurant JSON.
- **`GET /food/reviews?city=...&dish_or_restaurant=...`** – inspect raw review data.

### 3. Frontend setup (Next.js)

In a new terminal:

```bash
cd frontend

# Create a .env.local for the frontend if needed
cat <<EOF > .env.local
GROQ_API_KEY=your_groq_key_here
API_URL=http://localhost:8000
EOF

npm install
npm run dev
```

Then open **`http://localhost:3000`**.

Flow:

1. The globe loads – click on any city/region or use the search bar.
2. Frontend calls `GET /food/restaurants` on the backend.
3. `AgentChat` uses `POST /api/chat/stream` (Next.js API) which:
   - Streams Groq LLM output.
   - Uses tools to call backend `/food/restaurants` and `/food/reviews`.
4. You see a **short, emoji-filled food guide** + highlighted restaurant names.

---

## Deployment Guide

You typically deploy:

- **Frontend** → **Vercel** (Next.js).
- **Backend** → **Render** or **Railway** as a long-running web service.

### 1. Deploy Backend (Render or Railway)

The backend is a standard FastAPI + Uvicorn service.

#### Render (Web Service)

- **Create new Web Service** from your Git repo.
- Root directory: `backend`.
- Build command (example):

```bash
pip install -r requirements.txt
```

- Start command:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

- Environment:
  - `GROQ_API_KEY=...`
  - `BRAVE_SEARCH_API_KEY=...`
  - (Optional) `OPENAI_API_KEY`, `CHATGPT_API_KEY`.

Make note of the Render URL, e.g.:

- `https://smart-food-backend.onrender.com`

#### Railway (Service)

- **Create new Service** → connect GitHub repo or Dockerfile.
- If not using Docker, configure:
  - Root dir: `backend`.
  - Build command: `pip install -r requirements.txt`.
  - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- Set environment variables:
  - `GROQ_API_KEY`, `BRAVE_SEARCH_API_KEY`, etc.

Railway will give you a public URL similar to:

- `https://smart-food-backend.up.railway.app`

> Whichever platform you use, ensure the backend URL is HTTPS and publicly reachable from Vercel.

### 2. Configure Frontend to Point at Backend

On the **frontend side**, the Next.js API route uses:

- `API_BASE = process.env.API_URL ?? "http://localhost:8000";`

So in production you must set:

- **On Vercel → Project Settings → Environment Variables**
  - `API_URL=https://your-backend-url-from-render-or-railway`
  - `GROQ_API_KEY=your_production_groq_key`

You do **not** expose any key from the Python backend to the browser – only to the server runtime (Vercel and backend service).

### 3. Deploy Frontend to Vercel

1. Push this repo to GitHub.
2. In Vercel:
   - “New Project” → import your repo.
   - Root directory: `frontend`.
   - Framework preset: **Next.js**.
3. Set environment variables:
   - `GROQ_API_KEY=...` (same or different from backend – used by Next.js route).
   - `API_URL=https://your-backend-service-url`.
4. Build & deploy.

Vercel will expose a URL such as:

- `https://smart-food-frontend.vercel.app`

When a user visits:

1. Browser hits Vercel-hosted Next.js app.
2. Chat requests go to `/api/chat/stream` on Vercel (serverless function).
3. That function calls Groq + your backend (`API_URL`) as tools.

---

## APIs and Data Sources

- **Brave Search API**
  - Web and local POI search for restaurants, dishes, and reviews.
  - Requires `BRAVE_SEARCH_API_KEY`.
- **Groq**
  - LLM inference for:
    - ReAct agent orchestration (`agent.py`).
    - Web result summarization / structured extraction (`food.py`).
    - Frontend streaming chat (`/api/chat/stream`).
- **OpenStreetMap / Overpass**
  - Restaurant/cafe/bar discovery by latitude/longitude (fallback when Brave doesn’t give enough).
- **Nominatim (OpenStreetMap)**
  - Reverse geocoding from coordinates → `{city, state, country}`.
- **Wikipedia REST**
  - City pages for food culture and cuisine context.

---

## How Everything Fits Together

1. **User picks a location** on the globe / search.
2. Frontend:
   - Calls `GET /food/restaurants` to show a **nearby restaurant grid**.
   - Seeds a question to the chat agent about the local food scene.
3. Next.js API (`/api/chat/stream`):
   - Streams LLM output from Groq.
   - Uses tools to fetch structured data from the backend.
4. Backend:
   - Uses Brave, Overpass, Wikipedia, and Groq extraction to build a **rich, structured picture** of the location’s food world.
5. The agent:
   - Responds with a **short, emoji-rich summary** and references the tools used.
6. The UI:
   - Highlights restaurant names in the text.
   - Lets the user click restaurants to ask follow-up questions with focused reviews.

This README should give you everything you need to **understand, run, and deploy** the project end to end.

