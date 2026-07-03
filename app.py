import traceback
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from backend import run_travel_agent

BASE_DIR=Path(__file__).resolve().parent

app = FastAPI(title="TripleMate Travel Agent", description="A travel planning assistant using LangChain and Tavily.", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

class TravelRequest(BaseModel):
    user_query: str
    thread_id: str | None = None

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Render the main HTML page."""
    return templates.TemplateResponse(request=request, name="index.html", context={})


@app.post("/api/travel", response_class=JSONResponse)
async def travel_endpoint(travel_request: TravelRequest):
    """API endpoint to handle travel requests."""
    #add validation for user_query and thread_id
    try:
        if not travel_request.user_query:
            return JSONResponse(content={"success":False,"error": "user_query is required."}, status_code=400)
        if travel_request.thread_id and not isinstance(travel_request.thread_id, str):
            return JSONResponse(content={"success":False,"error": "thread_id must be a string."}, status_code=400)
        result = run_travel_agent(travel_request.user_query, thread_id=travel_request.thread_id)
        return JSONResponse(content={"success":True,
                                     "thread_id": result.get("thread_id"),
                                     "answer": result.get("final_answer"),
                                     "flight_results": result.get("flight_results"),
                                        "hotel_results": result.get("hotel_results"),
                                        "itinerary": result.get("itenary"),
                                        "llm_calls": result.get("llm_calls")
                            })
    except Exception as e:
        print(f"Error in travel_endpoint: {e}")
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve the favicon."""
    return JSONResponse(content={})

@app.get("/health", response_class=JSONResponse)
async def health_check():
    """Health check endpoint."""
    return JSONResponse(content={"status": "ok", "message": "TripleMate Travel Agent is running."})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)