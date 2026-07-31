# Contributing to Numa

Thank you for your interest in contributing to Numa!

Numa is an early-stage open-source framework for modular agent systems. We welcome contributions from developers, researchers, designers, writers, and AI practitioners.

## Ways to Contribute

- Report bugs or unclear behavior.
- Suggest new features and product directions.
- Improve documentation and examples.
- Propose architecture changes or design notes.
- Submit code changes for agents, runtime, tools, memory, and infrastructure.
- Share references and implementation tradeoffs relevant to agent systems.

## Contribution Principles

- Keep changes focused and easy to review.
- Prefer clear explanations over clever abstractions.
- Document assumptions, limitations, and open questions.
- Treat security, privacy, and observability as first-class concerns.

## Getting Started

Before contributing, please:

1. Read the project documentation.
2. Check existing issues and pull requests.
3. Search before creating a new issue.
4. Fork the repository and create a focused branch for your change.
5. Update documentation when behavior or direction changes.

## Development

Install Python 3.11+ and uv, then synchronize the development environment:

```bash
uv sync --all-groups
```

Run the same checks used by CI:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Repository:

https://github.com/open-numa-ai/numa

## Reporting Issues

If you find a bug or unexpected behavior, please create an issue with:

- A clear description of the problem
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment information

## Pull Requests

Open a pull request with context, tradeoffs, and validation notes. Small, focused pull requests are easier to review and merge.

## Code of Conduct

Be thoughtful, respectful, and constructive. Technical disagreement should focus on evidence, tradeoffs, and the needs of the project.
