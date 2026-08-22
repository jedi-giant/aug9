---
name: sg-transport
description: Provide Singapore transport directions between locations.
---

# SG Transport

Use this skill when users ask:

- how to travel between Singapore locations
- MRT directions
- bus directions
- public transport options
- journey routes

Available tool:

`get_sg_route(origin, destination)`

Rules:

1. Resolve locations before generating routes.
2. Prefer official Singapore transport data.
3. Do not invent travel times.
4. Explain route steps clearly.
5. Include walking segments where available.
