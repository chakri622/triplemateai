"""LangGraph travel agent.

Wires the flight and web-search tools to a Groq-hosted chat model as a ReAct
agent. Provides a factory that optionally accepts a checkpointer (e.g. the
Postgres saver backed by DATABASE_URL) so conversations can be persisted.
"""

import os

from dotenv import load_dotenv
from langchain.agents import create_agent as _create_react_agent
from langchain_groq import ChatGroq

from tools.flight_tool import find_flights, flight_distance, lookup_airport
from tools.tavily_tool import web_search

load_dotenv()

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Tools available to the agent.
TOOLS = [web_search, lookup_airport, flight_distance, find_flights]

SYSTEM_PROMPT = (
    "You are TripleMate, a helpful travel planning assistant. "
    "Use the tools to look up airports, real-time flights, distances, and "
    "current web information (hotels, attractions, advisories). "
    "When a user names a city or country, resolve it to an airport before "
    "searching flights. Flight results are schedules/status only and do not "
    "include ticket prices, so never invent prices. Be concise and cite the "
    "source URLs you get from web search."
)


def create_agent(checkpointer=None):
    """Build the ReAct travel agent.

    Args:
        checkpointer: Optional LangGraph checkpointer for conversation memory.

    Returns:
        A compiled LangGraph agent.
    """
    llm = ChatGroq(model=GROQ_MODEL, temperature=0)
    return _create_react_agent(
        llm,
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )


def run(message: str, thread_id: str | None = None, checkpointer=None) -> str:
    """Send a single message to the agent and return its final reply.

    Args:
        message: The user's message.
        thread_id: Conversation id (only used when a checkpointer is set).
        checkpointer: Optional checkpointer for persistence.

    Returns:
        The agent's final text response.
    """
    agent = create_agent(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread_id}} if thread_id else None
    result = agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config=config,
    )
    return result["messages"][-1].content


# Persistence example (uncomment to store conversations in Postgres):
#
#   from langgraph.checkpoint.postgres import PostgresSaver
#
#   with PostgresSaver.from_conn_string(os.environ["DATABASE_URL"]) as saver:
#       saver.setup()  # first run only: creates checkpoint tables
#       print(run("Plan a weekend in Austin", thread_id="user-1", checkpointer=saver))


if __name__ == "__main__":
    print(
        run(
            "What is the main airport in Tokyo, and suggest one well-reviewed "
            "hotel there with its source link?"
        )
    )
