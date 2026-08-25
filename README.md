# Aug9 🇸🇬

Singaporean AI LifeOps Agent powered by MCP.

Aug9 is an open-source AI assistant that connects Singapore-specific data sources built on Skills and Model Context Protocol (MCP) tools, allowing an AI agent to answer location and lifestyle questions using live data.

## Vision

Singapore has many excellent digital services, but information is fragmented across different platforms.

Aug9 aims to become a Singapore personal operating system:

- Find places
- Understand surroundings
- Plan activities
- Navigate daily life

## Current Capabilities

### 📍 Singapore Location Intelligence

Powered by OneMap API.

Example:

> Where is Maxwell Food Centre?

Returns:

- Address
- Postal code
- Latitude
- Longitude


### 🌦 Singapore Weather Intelligence

Powered by NEA Weather API.

Example:

> What is the weather at Maxwell Food Centre?

Returns:

- Current forecast
- Location-aware weather conditions


## Architecture

User
 |
 v
OpenAI Agent
 |
 v
Skills
 |
 v
MCP Server
 |
 +--> Location Tool
 |        |
 |        v
 |     OneMap API
 |
 +--> Weather Tool
          |
          v
       NEA API

## Tech Stack

- Python
- OpenAI Agents SDK
- Model Context Protocol (MCP)
- Pydantic
- httpx
- pytest
- uv


## Running Locally

Install dependencies:

```bash
uv sync
