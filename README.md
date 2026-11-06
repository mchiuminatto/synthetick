# Synthetick

Synthetick generates synthetic historic tick data (timestamp, bid, ask) for an instrument and a date range, through an API.

A client requests a tick range, polls its status, and downloads the ticks page by page. The ticks come from an arithmetic random walk with drift and volatility, with irregular timing and a random spread.

This is a work in progress. The first iteration covers the historic tick range through the API only.

## Documentation


- [Domain analysis](docs/design/domain-analysis.md): domain model, rules, endpoints and data model.
- [Tech stack](docs/design/tech-stack.md): technology decisions.
- [Synthetic price generation](docs/design/synthetic-price-generation.md): the random walk reference.



