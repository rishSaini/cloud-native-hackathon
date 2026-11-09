"""The public board (owner: Karthik, K12).

GET /api/board shows every room for the current slot: status as words (OPEN,
FULL, CLOSED, never color alone), captions, free seats, an open incident and
how fresh the reports are. One Elasticsearch msearch, no per-room loop.
It holds no attendee IDs, no hashes and no scheduler errors.
"""
