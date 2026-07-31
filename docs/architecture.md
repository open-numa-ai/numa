# Architecture

Numa is organized as a personal intelligence system with three major layers: intelligence, memory, and runtime.

## System Overview

```text
                Numa

                  |
      ------------------------

      Intelligence Layer

      - Research Agent
      - Discovery Engine
      - Reasoning Engine


      Memory Layer

      - Personal Memory
      - Knowledge Graph


      Runtime Layer

      - Agent Runtime
      - Tool Ecosystem

      ------------------------

                  |

              Internet
```

## Intelligence Layer

The intelligence layer is responsible for turning goals, memories, and external information into useful insight.

Core responsibilities:

- Research topics across external sources.
- Discover information the user may not know to search for.
- Reason over context, evidence, and assumptions.
- Produce summaries, reports, questions, and recommendations.

## Memory Layer

The memory layer stores durable context owned by the user.

Core responsibilities:

- Maintain long-term user memory.
- Represent entities, concepts, and relationships in a knowledge graph.
- Preserve provenance for facts, sources, and derived conclusions.
- Support retrieval for future reasoning and discovery.

## Runtime Layer

The runtime layer provides the execution environment for agents and tools.

Core responsibilities:

- Coordinate agent tasks.
- Manage tool access and execution.
- Connect to external sources.
- Provide observability, scheduling, and safety controls.

## Design Constraints

- User data should remain portable and understandable.
- Memory should be explainable, inspectable, and correctable.
- Autonomous behavior should be bounded by explicit user intent.
- Knowledge discovery should surface provenance and uncertainty.
