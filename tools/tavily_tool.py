"""Tavily search tool.

Wraps the Tavily API client and exposes a simple search function that takes a
query string. The API key is read from the TAVILY_API_KEY environment variable.
"""

import os

from dotenv import load_dotenv
from langchain_core.tools import tool
from tavily import TavilyClient

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
if not TAVILY_API_KEY:
    raise EnvironmentError("TAVILY_API_KEY is not set in the environment.")

# Shared client instance, configured from environment variables.
client = TavilyClient(api_key=TAVILY_API_KEY)


def tavily_search(query: str, max_results: int = 5) -> str:
    """Run a Tavily web search for the given query.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return.

    Returns:
        A numbered string list of the results, each entry formatted as
        "title\nurl\nsnippet", separated by blank lines.
    """
    response = client.search(
        query=query,
        search_depth="advanced",
        include_answer=True,
        max_results=max_results,
    )

    formatted = []
    for i, result in enumerate(response.get("results", []), start=1):
        title = result.get("title", "")
        url = result.get("url", "")
        snippet = result.get("content", "")
        if len(snippet) > 300:
            snippet = snippet[:300] + "..."
        formatted.append(f"{i}. **{title}**\n{url}\n{snippet}")

    return "\n\n".join(formatted)


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for up-to-date information and return the top results.

    Use this to look up current facts such as hotels, attractions, events,
    travel advisories, or anything not known offline. Returns a numbered list
    of results, each with a title, URL, and a short snippet.

    Args:
        query: What to search for.
        max_results: Maximum number of results to return (default 5).
    """
    return tavily_search(query, max_results=max_results)


if __name__ == "__main__":
    print(tavily_search("What is the best time to visit Austin, Texas?", max_results=3))
