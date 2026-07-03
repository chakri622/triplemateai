# TripleMate ✈️

A multi-agent **AI travel concierge**. Describe a trip in one sentence and
TripleMate assembles real-time flights, hand-picked hotels, and a day-by-day
itinerary — served through a FastAPI web app with a vintage boarding-pass UI.

> Flight data is live *status/schedule* information (via Aviationstack), not
> fares — prices in the itinerary are indicative estimates only.

---

## How it works

A [LangGraph](https://langchain-ai.github.io/langgraph/) `StateGraph` runs four
agents in sequence, sharing a typed `TravelState`:

```
START ─► flight_agent ─► hotel_agent ─► itinerary_agent ─► final_agent ─► END
```

| Node | Responsibility |
|------|----------------|
| `flight_agent`    | Extracts origin/destination from the query (structured LLM output), resolves them to IATA codes, and looks up live flights. |
| `hotel_agent`     | Web-searches the best hotels at the destination. |
| `itinerary_agent` | Drafts a practical, budget-aware itinerary from the flight + hotel results. |
| `final_agent`     | Formats the final answer into clean sections with source links. |

Conversation state is persisted in **Postgres** via LangGraph's
`PostgresSaver` checkpointer, keyed by `thread_id`, so follow-up requests
continue the same session.

## Tech stack

- **Orchestration:** LangGraph + LangChain
- **LLM:** Groq (`llama-3.3-70b-versatile` by default, override with `GROQ_MODEL`)
- **Web/API:** FastAPI + Uvicorn, Jinja2 templates
- **Tools:** Aviationstack (flights), Tavily (web search), `airportsdata` + `pycountry` (offline airport/country data)
- **Memory:** PostgreSQL checkpointer
- **Frontend:** vanilla HTML/CSS/JS (no build step)

## Project structure

```
triplemateai/
├── app.py                 # FastAPI app: routes, static/templates, /api/travel
├── backend.py             # LangGraph agents, graph, Postgres checkpointer
├── main.py                # Entry point — launches the web server
├── test.py                # Ad-hoc checks for tools and the agent
├── tools/
│   ├── flight_tool.py     # Airport lookup, IATA resolution, live flight search
│   └── tavily_tool.py     # Tavily web search
├── templates/index.html   # UI markup
└── static/
    ├── style.css          # Boarding-pass theme
    └── script.js          # Fetches /api/travel and renders results
```

## Tools

### `tools/flight_tool.py`
- `clean_text(text)` — normalize a query (strip stop words like "airport").
- `country_to_code(name)` — country name/code → ISO alpha-2 (via `pycountry`).
- `get_airport(iata)` / `find_airports_by_city(city, country=None)`.
- `get_main_airport_for_city` / `get_main_airport_for_country` — curated primary airports.
- `resolve_location_to_iata(query)` — IATA code, city, or country → a single IATA code.
- `airport_distance_km(a, b)` — great-circle distance.
- `search_flights(origin, destination, ...)` — live flights via Aviationstack.
- LangChain tools: `lookup_airport`, `flight_distance`, `find_flights`.

### `tools/tavily_tool.py`
- `tavily_search(query, max_results=5)` — formatted web results (title, url, snippet).
- LangChain tool: `web_search`.

## Setup

Requires **Python 3.13+**. This project uses [uv](https://docs.astral.sh/uv/).

```bash
# install dependencies
uv sync            # or: pip install -r requirements.txt

# create your .env (see below), then run
python main.py     # or: uvicorn app:app --reload
```

Open <http://127.0.0.1:8000>.

### Environment variables (`.env`)

Create a `.env` file in the project root (it is git-ignored):

```env
GROQ_API_KEY=your_groq_key
TAVILY_API_KEY=your_tavily_key
AVIATIONSTACK_API_KEY=your_aviationstack_key
DATABASE_URL=postgresql://user:password@host/dbname

# optional
GROQ_MODEL=llama-3.3-70b-versatile
DEFAULT_ORIGIN_IATA=AUS
HOST=127.0.0.1
PORT=8000

# optional LangSmith tracing
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT=triplemate
```

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/` | Web UI. |
| `POST` | `/api/travel` | Plan a trip. |
| `GET`  | `/health` | Health check. |

**`POST /api/travel`**

```json
{ "user_query": "Austin to Tokyo next month, best flights and hotels", "thread_id": null }
```

Response:

```json
{
  "success": true,
  "thread_id": "user_...",
  "answer": "## Summary of the trip ...",
  "flight_results": "Flights AUS -> HND ...",
  "hotel_results": "1. **Hotel ...**",
  "itinerary": "...",
  "llm_calls": 4
}
```

Pass the returned `thread_id` back on the next request to continue the same
conversation.

## Notes & limitations

- **No real fares.** Aviationstack (free tier) returns flight *status* for a
  route at query time, so routes without current scheduled flights come back
  empty. For bookable fares, swap in a fares API (Amadeus, Kiwi, etc.).
- **Free-tier limits.** Aviationstack free is HTTP-only and ~100 requests/month.
- **Secrets.** Never commit `.env` or connection strings. Rotate any key that
  has been exposed.
