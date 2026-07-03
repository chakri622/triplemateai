"""Entry point for the TripleMate travel concierge web app.

Launches the FastAPI application defined in ``app.py`` with uvicorn.
Run with: ``python main.py`` (or ``uvicorn app:app --reload``).
"""

import os

import uvicorn


def main():
    """Start the TripleMate web server."""
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    # Pass the import string (not the app object) so --reload works.
    uvicorn.run("app:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
