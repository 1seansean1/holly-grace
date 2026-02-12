"""Holly Grace Construction Crew — specialized builder agents.

Each crew member is a registered agent that Holly Grace can dispatch
to handle specific aspects of constructing and maintaining workflows.
All crew agents run through the Control Tower as durable, interruptible runs.

Crew roster:
  - Architect: workflow graph topology design
  - Tool Smith: LangChain tool creation
  - MCP Creator: MCP server connector building
  - Test Engineer: test writing and evaluation
  - Wiring Tech: registry and scheduler wiring
  - Program Manager: construction project coordination
  - Finance Officer: budget and cost analysis
  - Lead Researcher: deep research protocol (multi-agent swarm)
  - Critic: proposal review and challenge
  - Wise Old Man: past lessons recall
  - Epsilon Tuner: morphogenetic monitoring
  - Strategic Advisor: cross-workflow business strategy
  - System Engineer: automated system documentation
  - Cyber Security Expert: security reviews and policies
  - Product Manager: feature backlog management
  - Debugger: runtime diagnostics via 12-phase hypothesis-testing protocol
"""

from src.holly.crew.registry import CREW_AGENTS, get_crew_agent, list_crew
