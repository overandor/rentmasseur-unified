#!/usr/bin/env python3
"""Entry point for HuggingFace Space — runs the military-grade server."""
from server import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
