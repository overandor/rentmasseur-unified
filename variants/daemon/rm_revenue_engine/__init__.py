"""
RM Revenue Engine — RentMasseur API Revenue Engine.

Not AGI. Not a toy. An execution-and-measurement engine.

Architecture:
    API Client → State DB → Market Scanner → C++ Engine → Approval Gate → Experiment Runner

Every action produces:
    - SQLite log entry
    - JSON receipt
    - Before/after snapshot (for mutations)
    - Exit code + captured output

Priority order:
    1. Visibility ON
    2. Availability truthful and refreshed
    3. Dashboard stats logging
    4. Search-rank tracking
    5. Competitor corpus enrichment with visits/day
    6. C++ predictor
    7. Approved profile experiments
    8. Retraining from real dashboard lift
"""

from .state_db import StateDB
from .market_scan import MarketScanner
from .experiment_runner import ExperimentRunner
