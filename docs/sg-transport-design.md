# SG Transport Capability Design

## User Intent

Help users navigate between Singapore locations.

## MCP Tool

get_sg_route(
    origin: str,
    destination: str
)

## Input

Example:

Origin:
Maxwell Food Centre

Destination:
Marina Bay Sands


## Output

Example:

{
  "status": "success",
  "route": {
    "origin": "Maxwell Food Centre",
    "destination": "Marina Bay Sands",
    "steps": [
      "Walk to MRT station",
      "Take MRT",
      "Walk to destination"
    ]
  }
}
