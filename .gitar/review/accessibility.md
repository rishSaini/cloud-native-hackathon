# Accessibility review

For `frontend/`: flag new UI where controls have no accessible name, status is
conveyed by color alone (room status must say OPEN, FULL or CLOSED), focus can't
reach an element by keyboard, or motion ignores `prefers-reduced-motion`.
For API responses that the UI shows: status values must be words, not colors.
