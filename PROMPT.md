## Step 1 – Project Seed Prompt

Build a full-stack **AI food discovery app** with:

- **Backend (`backend/`)**: Python FastAPI, Groq LLM (LangChain/LangGraph), Brave Search, OpenStreetMap/Overpass, Wikipedia. Expose endpoints for:
  - `/chat` and `/chat/stream` – location‑aware food guide chat (≤ 50‑word answers).
  - `/food/restaurants` – nearby restaurants from Brave/OSM.
  - `/food/reviews` – restaurant review snippets via Brave.
  - `/location/summary` – short summary for map clicks.

- **Frontend (`frontend/`)**: Next.js (App Router) + React with:
  - A 3D globe to pick locations, plus a search bar.
  - Panels for visited cities, location overlay, restaurant grid, and an AI “Food Guide Chat”.
  - Streaming chat via an API route that calls Groq and uses tools to hit the FastAPI backend.

Make the UI modern, dark-themed, and travel/food styled. Configure for **local dev** and **deployment** with:

- Frontend on **Vercel**.
- Backend on **Render or Railway** as a long‑running FastAPI service.

---

## Step 2 – Fix globe selection + buttons

“Fix the globe click handling and buttons so that selecting a city reliably:

- focuses the globe on that point,
- updates the right-hand panel,
- and triggers an automatic ‘overview of the food scene here’ chat message.”

---

## Step 3 – Add search, chips, and richer chat

“Add a search bar to jump to cities by name and show suggested prompt chips for each mode (Discover, Restaurants, Guide). Make the AI chat feel like a concise food travel guide: ≤ 50 words, bullet-style, with food emojis.”

---

## Step 4 – Polish UX and deployment

“Refine the dark, food-travel UI, make restaurant cards clickable to ask about a specific place, and document how to run locally and deploy: frontend on Vercel, backend FastAPI on Render or Railway.”

