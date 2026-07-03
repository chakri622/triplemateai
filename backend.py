
"""LangGraph travel agent.

Wires the flight and web-search tools to a Groq-hosted chat model as a ReAct
agent. Provides a factory that optionally accepts a checkpointer (e.g. the
Postgres saver backed by DATABASE_URL) so conversations can be persisted.
"""

import os

from dotenv import load_dotenv
from typing import TypedDict, Annotated
import operator
import uuid
import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START,END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, AnyMessage
from langchain.agents import create_agent as _create_react_agent
from langchain_groq import ChatGroq

from tools.flight_tool import find_flights, flight_distance, lookup_airport,search_flights, resolve_location_to_iata, get_airports_by_country, airport_distance_km
from tools.tavily_tool import web_search, tavily_search

load_dotenv()

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

def get_database_url() -> str:
    """Get the database URL from the environment variable.

    Returns:
        The database URL string.
    """
    database_url =os.getenv("DATABASE_URL")
    if not database_url:
        raise EnvironmentError("DATABASE_URL is not set in the environment.")
    if "sslmode=" not in database_url:
        separator = "&" if "?" in database_url else "?" 
        # Append sslmode=require if not present
        database_url += f"{separator}sslmode=require"
    return database_url


# ==================================
# LLM
# ==================================

llm = ChatGroq(model=GROQ_MODEL, temperature=0)

# ==================================
# State
# ==================================

class TravelState(TypedDict):
    """State for the travel agent."""
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    origin: str
    destination: str
    flight_results:str
    hotel_results:str
    itenary:str
    llm_calls:int


# =================================
# Route extraction
# =================================

class Route(BaseModel):
    """Origin and destination extracted from a travel query."""
    origin: str = Field(description="Origin city, country, or airport code the traveler departs from.")
    destination: str = Field(description="Destination city, country, or airport code the traveler is going to.")


def _extract_route(user_query: str) -> Route:
    """Use the LLM to pull origin and destination out of a free-text query."""
    extractor = llm.with_structured_output(Route)
    return extractor.invoke([
        SystemMessage(content="Extract the origin and destination locations from the user's travel query. Return plain place names or IATA codes."),
        HumanMessage(content=user_query),
    ])


# =================================
# Flight Agent
# =================================

def flight_agent(state: TravelState) -> TravelState:
    """Flight agent that looks up flights and distances."""
    user_query = state["user_query"]
    route = _extract_route(user_query)
    flight_results = search_flights(route.origin, route.destination, limit=5)
    return {
        "origin": route.origin,
        "destination": route.destination,
        "flight_results": flight_results,
        "messages": [AIMessage(content=f"Flight results found for {route.origin} -> {route.destination}.")],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }

# =================================
# Hotel Agent
# =================================
def hotel_agent(state: TravelState) -> TravelState:
    """Hotel agent that looks up hotels using web search."""
    destination = state.get("destination") or state["user_query"]
    hotel_results = tavily_search(f"best hotels in {destination}", max_results=5)
    return {
        "hotel_results": hotel_results,
        "messages": [AIMessage(content="Hotel results found.")],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }

# =================================
# Itinerary Agent
# =================================
def itinerary_agent(state: TravelState) -> TravelState:
    """Itinerary agent that compiles flight and hotel results into an itinerary."""
    prompt = f"""
    Create a complete travel itinerary based on 
    User Query: {state['user_query']}
    Flight Results: {state.get('flight_results', '')}
    Hotel Results: {state.get('hotel_results', '')}
    Make the iternary practical, budget aware,  concise and easy to follow, and include the source URLs for flights and hotels.
    """
    response = llm.invoke([
        SystemMessage(content="You are a travel itinerary assistant."),
        HumanMessage(content=prompt),
    ])

    return {
        "itenary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


# =================================
# Final Agent
# =================================
def final_agent(state: TravelState) -> TravelState:
    """Final agent that compiles the final response."""
    final_response = f"""
    User Query: {state['user_query']}
    Flight Results: {state.get('flight_results', '')}
    Hotel Results: {state.get('hotel_results', '')}
    Itinerary: {state.get('itenary', '')}
    Format the final answer beautifully using these sections:
    1. Summary of the trip
    2. Flight details with source URLs
    3. Hotel details with source URLs
    4. Itinerary with source URLs
    5. Estimated budget and tips
    6. Final recommendations and advice

    Important: 
    - Be concise and clear.
    - Mention the live flight API may not have real-time prices, so do not invent prices.
    - Keep the response useful for real-world travel planning.
    """
    response = llm.invoke([
        SystemMessage(content="You are a professional AI travel booking assistant."),
        HumanMessage(content=final_response),
    ])
    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


# =================================
# Build Graph
# =================================
graph = StateGraph(
   TravelState,

)

graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)


# =================================
# Postgres Saver
# =================================
DATABASE_URL = get_database_url()
_connection = psycopg.connect(DATABASE_URL,autocommit=True, row_factory=dict_row)

checkpointer = PostgresSaver(_connection)
checkpointer.setup()  # Create tables if not exist

travel_graph = graph.compile(checkpointer=checkpointer)


# =================================
# Run Function
# =================================

def run_travel_agent(user_query: str, thread_id: str | None = None) -> str:
    """Run the travel agent for a given user query.

    Args:
        user_query: The user's travel query.
        thread_id: Optional thread ID for conversation persistence.
    """
    if not thread_id:
        thread_id =f"user_{str(uuid.uuid4().hex)}"  # Generate a new thread ID if not provided
    result = travel_graph.invoke(
        {"messages": [HumanMessage(content=user_query)], 
         "user_query": user_query,"flight_results":"","hotel_results":"","itenary":"","llm_calls":0},
        config={"configurable": {"thread_id": thread_id}},
    )
    final_answer = result["messages"][-1].content
    return{
        "thread_id": thread_id,
        "final_answer": final_answer,
        "flight_results": result.get("flight_results", ""),
        "hotel_results": result.get("hotel_results", ""),
        "itenary": result.get("itenary", ""),
        "llm_calls": result.get("llm_calls", 0),
    }
