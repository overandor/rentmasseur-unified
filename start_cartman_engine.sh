#!/bin/bash
# Wrapper to start Cartman engine with correct python
export PATH="/Users/alep/miniconda3/bin:$PATH"
export PYTHONPATH="/Users/alep/miniconda3/lib/python3.12/site-packages"
exec /Users/alep/miniconda3/bin/python3 "/Users/alep/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension/cartman_engine.py"
