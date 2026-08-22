---
name: sg-place-finder
description: Resolve Singapore places, addresses, MRT stations and postal codes using Aug9 location tools, based on Singapore Government data and APIs.
---

# SG Place Finder

Use this skill when the user needs to identify or resolve a physical location in Singapore.

## Available tools

Use:

`resolve_sg_location(query)`

Use when the user needs:
- an address
- postal code
- coordinates
- canonical place information

Use:

`get_sg_weather(query)`

Use when the user asks about:
- current/local weather
- whether it may rain at a place
- weather conditions around a Singapore location

The query may contain:

- place names
- building names
- MRT station names
- Singapore postal codes
- street addresses

## Procedure

1. Identify the Singapore location the user is referring to.
2. Call `resolve_sg_location` with the user's location text.
3. Use the returned canonical location information.
4. Do not invent coordinates, addresses, or postal codes.
5. If the tool returns `no_results`, explain that the location could not be resolved.
6. If the tool returns an API or network error, do not present guessed location information.
7. If the user asks specifically about weather at a Singapore location, use `get_sg_weather` rather than only resolving the location.
8. Do not answer weather questions from model memory when a live weather tool is available.

## Expected successful result

A successful result contains:

- name
- address
- postal_code
- latitude
- longitude
