# Prompt: build the Affinity frontend

Copy everything below this line into your coding agent.

---

You are building the frontend for **Affinity**, a hackathon project at the Cloud Native Hackathon in Salt Lake City (November 9, 2026, during KubeCon week). Submissions close at 5:30 PM Mountain Time, so favor working, polished, demo-ready screens over completeness. Build in small steps and keep the app runnable after every step.

## 1. What Affinity is

Affinity makes sure nobody at a big conference ends up lost or alone.

1. Each attendee makes a small card on their phone: what they're working on and how people should talk to them, for example "Please face me, I read lips."
2. The app finds them a talk that matches their interests, has seats, and meets their needs, such as working captions.
3. If a room fills up or closes, the app moves them to the next best talk before they walk over.
4. At every break, the app gives them a small group: "3:30, the quiet table by the window, with two people working on similar things."
5. Everyone in the group reads each other's cards first, so nobody has to explain themselves.
6. If both people agree, the app remembers who they met and where.

The twist: the backend runs the conference on Kubernetes. Attendees are Pods, rooms and break tables are Nodes, seats are a schedulable resource, and the real Kubernetes scheduler decides where each person goes. The frontend should make that twist visible and fun without getting in the way of the human experience.

Pitch line: *"Nobody should fly to a conference and end up standing alone."*

## 2. Read these first

Before writing code, read:

- `AGENTS.md` and `CLAUDE.md` for this repo's conventions
- `docs/AFFINITY.md` for the full design, especially the privacy section
- `frontend/index.html` for how the current page is built
- `backend/app/main.py` for how the page and `/rum.js` are served
- `Dockerfile` to see how frontend files get into the image

Facts about the current setup that you must respect:

- The frontend is a single `frontend/index.html` with no build step.
- FastAPI serves it at `/` by reading the file and replacing `{{VERSION}}` with the app version. Keep `{{VERSION}}` in the page footer so the team can check which commit is live.
- The page loads `/rum.js`, which starts Dash0 real-user monitoring when configured. Keep that script tag.
- The page currently calls `GET /api/search?q=`. Keep that working for talk search.
- The page title currently says TalkScout. Rename it to Affinity.

If you need more than one file, add a FastAPI `StaticFiles` mount at `/static` serving `frontend/static/`, and check the `Dockerfile` copies the whole `frontend/` folder. Keep that backend change minimal and in its own pull request.

## 3. Technical constraints

- **No build step.** Use plain HTML, CSS and JavaScript ES modules. No React, no bundler, no npm install for the frontend. This keeps the Docker image and CI unchanged.
- **Hash routing** so the backend only ever serves `/`. Routes are listed in section 8.
- **Mobile first.** Design for a 375px-wide phone, then make it work up to desktop. The big-screen board is designed for a 1920×1080 projector.
- **External assets:** load fonts from Google Fonts with system-font fallbacks so the app still works if the venue Wi-Fi blocks them. Use no other CDNs unless needed, and pin exact versions if you do.
- **Performance:** the board must stay smooth with 1,000 animated dots. Use a single `<canvas>` with `requestAnimationFrame`, and pause animation when the tab is hidden.
- **No secrets in the frontend.** All keys stay on the server.

## 4. The two visual themes

The phone and the big screen deliberately look different.

### Phone: warm paper

Cozy, calm and friendly, like real name cards on a table.

- Cream background, soft rounded cards with a very subtle shadow and an optional faint paper texture
- Plenty of white space, with one main action per screen
- Large, friendly type

### Big screen: constellation

A deep navy night sky.

- Every attendee is a soft glowing star.
- Rooms are softly lit regions of the sky.
- When a break group forms, faint lines join its stars into a small constellation.

### Design tokens

Define these as CSS custom properties on `:root` and use them everywhere. Check every text-on-background pair with a contrast checker and adjust shades until normal text meets WCAG AA (4.5:1) and large text meets 3:1.

```css
:root {
  /* paper (phone) */
  --paper: #FBF7F0;
  --paper-raised: #FFFDF9;
  --ink: #2A2A35;
  --ink-soft: #5E5C66;
  --line: #E8E1D5;

  /* sky (board) */
  --sky: #0E1430;
  --sky-raised: #18204A;
  --starlight: #F4F1FF;
  --starlight-soft: #B9B6D9;

  /* accents */
  --coral: #E8735A;
  --teal: #2BA59A;

  /* calm status colors, always paired with a word */
  --ok: #3E9E6E;
  --warn: #C98A1B;
  --alert: #C4566A;

  /* type */
  --font-ui: "Nunito", "Inter", system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-code: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace;

  /* shape and motion */
  --radius-card: 20px;
  --radius-control: 12px;
  --ease: cubic-bezier(0.65, 0, 0.35, 1);
  --move: 500ms;
}
```

### Typography

- Use `--font-ui` for everything people read.
- Use `--font-code` only for Kubernetes-flavored details: random attendee IDs, status words like `Running`, and the kubectl mode.
- Body text is at least 16px on the phone. Headings use weight 600 or lighter. Avoid all caps except short status labels like `FULL`.

### Per-person color

Every attendee gets a soft color generated from their random ID, so their star, card accent and group lines all match.

```js
function personHue(id) {
  let h = 0;
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return h % 360;
}
// star color: `hsl(${hue} 70% 78%)`, card accent: `hsl(${hue} 55% 45%)`
```

Colors are never the only way to tell people apart.

## 5. Human mode and kubectl mode

Add a toggle in settings, and on the board, that switches between two ways of showing the same state.

| Human mode (default) | kubectl mode |
|---|---|
| "You're in Room 251, 2:30 PM" | `attendee-7f3k   Running   room-251` |
| "Matching talks are full. Here are others." | `Pending: 0/40 nodes available: 12 Insufficient affinity.dev/seats` |
| "Moving you to a new room" | `Evicted → Pending → Scheduled` |
| "Your break group is ready" | `podgroup/g-91ab   Scheduled   table-6` |

Rules:

- Human mode is always the default. kubectl mode is a playful extra.
- kubectl mode uses `--font-code` and a dark terminal-like panel, but keeps the same layout and accessible structure.
- kubectl mode must never reveal access needs or card text. Show opaque labels only, such as `cap-c7`.

## 6. Accessibility requirements

This project is about inclusion, so accessibility is part of the product, not a polish step.

- Use semantic HTML: real `<button>`, `<a>`, `<form>`, `<label>`, headings in order, and landmarks.
- Every control has a visible label or an accessible name.
- Everything works by keyboard, with a clear, visible focus style.
- Touch targets are at least 44×44px.
- Never show status by color alone. A full room says `FULL`, an incident says `INCIDENT`, and so on.
- Respect `prefers-reduced-motion`. With it on, there's no breathing, gliding or glowing: dots appear in their new place, groups appear already joined, and the card flip becomes a crossfade.
- Respect the user's text size. Use `rem`, and make sure layouts survive 200% zoom.
- Announce important changes politely with an `aria-live="polite"` region, for example "You've been moved to Room 251." Throttle announcements so screen reader users aren't flooded.
- The board's canvas is decorative for screen readers. Provide an equivalent visually hidden summary: a list of rooms with status and seat counts, plus the "people alone" number.
- Add a **calm mode** toggle: muted colors, no animation, no sounds, and fewer elements on screen.
- Add a **text size** control on the phone with at least three sizes.
- Test with VoiceOver on iPhone and with a keyboard on desktop. Run an automated check such as the axe browser extension, and fix every serious issue.

## 7. Privacy rules for the frontend

- The board never shows names, card text or access needs. It only shows random IDs such as `attendee-7f3k` and room-level information.
- Never put card text, names or access needs in URLs, query strings, `console.log` output or error messages.
- Store only the session token in the browser. Fetch the card from the API when needed, and don't save card text in `localStorage`.
- Card input fields must be excluded from Dash0 session recording or masked. Check the Dash0 web SDK documentation for the right option, and verify in Dash0 that card text doesn't appear.
- QR share links contain only a short-lived signed token, never card content.
- Every screen showing someone else's card offers "Leave group" and "Report a concern."

## 8. Routes and screens

Use these hash routes:

| Route | Screen |
|---|---|
| `#/` | Welcome and onboarding |
| `#/now` | Your current talk and status |
| `#/card` | Your card |
| `#/card/show` | Show across the table |
| `#/group` | Your break group |
| `#/report` | Report this room |
| `#/met` | People you've met |
| `#/settings` | Settings |
| `#/c/:token` | Someone's shared card, opened from a QR code |
| `#/board` | Big-screen board |
| `#/staff` | Staff incidents |

The phone has a bottom tab bar with Now, Card, Group, Report and Met. The board and staff screens have no tab bar.

### 8.1 Welcome and onboarding (`#/`)

1. **Welcome:** "Find your talk. Find your people." with one button: "Make my card."
2. **Pick a template:** 4 or 5 large tappable tiles, each pre-filling the "how to talk to me" field. Use neutral, behavior-based wording, never diagnosis words:
   - "Please face me when you talk"
   - "Give me time to finish my words"
   - "Say your name when you walk up"
   - "I do better one-on-one"
   - "This is my first conference"
   - "Start from scratch"
3. **Fill in the card:** name (required), pronouns, working on, ask me about, how to talk to me, best way to reach me, looking for. Show a live preview of the card as they type.
4. **What you need from a room or table (private):** checkboxes such as working captions, quiet, step-free and good lighting. Explain in one line that this is private and only used to pick suitable rooms.
5. **Done moment:** a star in the person's color softly appears, with the text *"You're attendee-7f3k. Look for yourself on the big screen."*

Keep the whole flow under 30 seconds for someone using a template.

### 8.2 Now (`#/now`)

- A large card for the current or next talk: title, time, room, walking hint if known, and badges such as "Seats left" and "Captions on," each with an icon and a word.
- **Status pill** that steps through `Pending → Scheduled → Running`, with a friendly word underneath:
  - Pending: "Finding you a seat"
  - Scheduled: "You're in. Head over."
  - Running: "Enjoy the talk"
- **Reroute banner:** when the room fills or closes, a warm amber banner slides in from the top: *"Room 151 filled up. We moved you to Room 251."* Include "Show other options" and "Undo" if the old room becomes available.
- Every room report shows its age, for example "Reported 2 min ago."
- If the person can't be placed, explain in plain words and list the closest options with space.

### 8.3 Card (`#/card`)

- **Flip card:** the front shows name, pronouns and "working on." Tapping flips it to "how to talk to me," "best way to reach me" and "looking for." Provide a visible "Flip" button too, because the tap target alone isn't discoverable for everyone.
- Buttons: "Share card" (shows a QR code), "Show across the table," "Edit," and "Delete my card."
- Deleting asks for confirmation and explains it also removes the card from groups and shared links.

### 8.4 Show across the table (`#/card/show`)

- Full screen, huge high-contrast text, showing only name and "how to talk to me."
- A "Flip for across the table" button rotates the card 180° so the person opposite can read it.
- Try the Screen Wake Lock API so the screen stays on, and fail silently if unsupported.
- A large "Done" button returns to the card.

### 8.5 Group (`#/group`)

- Before the break: *"Your table in 2:00"* with a gentle countdown, and an opt-in toggle: "Find me a group at the next break."
- **Reveal moment:** faces or initials in each person's color slide together into one group, with a short phone vibration if supported and allowed. With reduced motion, the group simply appears.
- Shows the time and place, such as "3:30, quiet table by the window."
- Each member's card is shown in compact form, with "how to talk to me" first.
- A suggested opener: *"Try asking: How do you test startup speed?"*
- Buttons: "I'm here," "Running late," "Leave group" and "Report a concern."
- After 3 minutes, if someone hasn't arrived, show: *"We're adding someone so nobody waits alone."*

### 8.6 Report (`#/report`)

- The current room name at the top, with a link to change room.
- One-thumb grid of large buttons: Seats left, Standing room, Full, Too loud, Captions working, Captions down, Elevator or aisle problem.
- Captions down and access problems are visually distinct and say "Staff will be alerted."
- After tapping: *"Thanks. 3 others said the same."* or *"Thanks. Staff have been alerted."*
- Rate-limit on the client: one report per room per signal every 2 minutes, and explain that kindly if someone taps again.

### 8.7 People you've met (`#/met`)

- A stack of saved connection cards, each saying where you met: *"Sam · quiet table · Tuesday 3:30."*
- A "Save this person" flow that only completes when both people agree. Show a pending state until the other person confirms.
- **Your constellation:** a small canvas where each person you met is a star connected to yours. It should make a nice screenshot to keep.

### 8.8 Settings (`#/settings`)

- Calm mode
- Reduced motion, defaulting to the system setting
- Text size
- Human or kubectl mode
- Delete my card and data
- A short plain-language privacy note

### 8.9 Board (`#/board`)

This is the demo centerpiece, built for a projector.

**Layout:**

- **Center: the constellation canvas.**
  - Each room is a soft, softly lit region with its name and status written next to it.
  - Each attendee is a star in their own color, gently breathing (opacity or scale pulsing over 3 to 4 seconds, with random offsets).
  - A room's region fills up from the bottom like water as seats are taken.
  - When someone is moved, their star glides to the new room over `--move` with `--ease`.
  - When a break group forms, the stars drift together and faint lines connect them, with a soft glow pulse.
- **Top right: the hero number,** a huge *"0 people alone"* with a small label: "at this break."
- **Right column: room status cards,** styled like a service status page:
  - `Room 151 · FULL · 120 of 120`
  - `Room 251 · OPEN · 84 of 120`
  - `Room 155 · INCIDENT · Captions down · reported 10:41 · staff on it`
  - Resolved incidents show `Fixed 10:46` and fade out after a minute.
- **Bottom: event ticker,** styled like `kubectl get events -w`, using `--font-code`:
  - `10:42  Scheduled  attendee-7f3k → room-251`
  - `10:43  Evicted    room-151 closed`
  - `10:44  Grouped    g-91ab → table-6 (3 people)`
- **Corner: QR code to join** with *"Scan to join. Then look for your star."*

**Closing moment:** a "finale" action, available only in demo mode, forms groups for everyone. All stars glow and connect into constellations, then *"0 people alone"* fades in, large and centered.

**Demo mode:** enabled only with `#/board?demo=1`.
- `C` closes the busiest room
- `G` forms break groups
- `I` opens a captions incident
- `F` plays the finale
- `K` toggles kubectl mode
- `R` resets

Show a small, discreet hint listing these keys only in demo mode.

**Fallbacks:** if animation is off, show the same information as a clean grid of rooms with counts. If the stream disconnects, show a small "Reconnecting" pill and keep the last known state.

### 8.10 Staff (`#/staff`)

- A list of open incidents with room, type, time reported and number of reports
- Buttons: "On it" and "Fixed"
- Plain and fast, without the decorative styling

## 9. Motion and sound

- Default move duration is 500ms with `--ease`. Nothing flashes, shakes or bounces.
- Card flip: 3D rotate around the Y axis over 400ms, or a crossfade with reduced motion.
- Banners slide in over 250ms and stay until dismissed or the state changes.
- Stars breathe slowly. Never use fast blinking.
- No sound by default. Haptics only for the group reveal and reroute, and only where the Vibration API is supported.
- All motion turns off with reduced motion or calm mode.

## 10. Data layer

Build the frontend against a small API client module so it can run with real or fake data.

- `frontend/static/js/api.js` exports one object with the methods below.
- `frontend/static/js/mock-api.js` implements the same methods with synthetic data and timers.
- Use the mock automatically when the page URL includes `mock=1`, or when the real endpoint returns 404. Show a small "Demo data" badge whenever the mock is active.

### Expected endpoints

Agree these with whoever builds the backend. Paths match `docs/AFFINITY.md`.

| Method | Path | Returns |
|---|---|---|
| `POST` | `/api/attendees` | `{ attendeeId, displayId }` and sets a session cookie |
| `GET` | `/api/card` | Your card |
| `PUT` | `/api/card` | Saved card |
| `DELETE` | `/api/card` | `204` |
| `POST` | `/api/card/share` | `{ url, expiresAt }` |
| `GET` | `/api/talks/search?q=` | `{ hits: [...] }` |
| `GET` | `/api/placements/current` | Placement |
| `POST` | `/api/breaks/:id/rsvp` | `{ status }` |
| `POST` | `/api/groups/:id/check-in` | `{ status }` |
| `POST` | `/api/rooms/:id/reports` | `{ agreeing, staffAlerted }` |
| `POST` | `/api/connections` | `{ status: "pending" | "saved" }` |
| `GET` | `/api/board` | Board snapshot |
| `GET` | `/api/staff/incidents` | Incidents |
| `PATCH` | `/api/staff/incidents/:id` | Updated incident |
| `GET` | `/api/stream` | Server-Sent Events |

Until `/api/talks/search` exists, fall back to the existing `/api/search?q=`.

### Example shapes

```json
{
  "placement": {
    "status": "Scheduled",
    "talk": { "id": "t-42", "title": "Faster app startup", "startsAt": "2026-11-10T14:30:00-07:00" },
    "room": { "id": "room-251", "name": "Room 251", "seatsLeft": 36, "badges": ["seats", "captions"] },
    "reason": null,
    "kubectl": "attendee-7f3k   Running   room-251",
    "reportedMinutesAgo": 2
  }
}
```

```json
{
  "board": {
    "rooms": [
      { "id": "room-151", "name": "Room 151", "seats": 120, "taken": 120, "status": "FULL" },
      { "id": "room-155", "name": "Room 155", "seats": 80, "taken": 41, "status": "INCIDENT", "incident": { "type": "captions", "reportedAt": "10:41", "state": "acknowledged" } }
    ],
    "attendees": [ { "displayId": "attendee-7f3k", "roomId": "room-251", "groupId": null } ],
    "groups": [ { "id": "g-91ab", "tableId": "table-6", "members": ["attendee-7f3k", "attendee-2m9q"] } ],
    "alone": 0
  }
}
```

### Live updates

- Subscribe with `EventSource('/api/stream')`.
- Event types: `placement`, `reroute`, `group`, `room`, `incident`, `board`.
- If the stream fails, retry with backoff and fall back to polling every 10 seconds.
- Make all handlers safe to receive the same event twice.

### Mock data

- 200 synthetic attendees with random IDs, 8 rooms with different capacities, and 20 break tables.
- Timers that occasionally fill a room, open and fix a captions incident, and move people.
- Demo keyboard shortcuts from section 8.9 drive the mock directly.
- Never use real people's names. Use clearly fake first names on phone screens in mock mode.

All times display in America/Denver, regardless of the device's time zone, using `Intl.DateTimeFormat` with `timeZone: "America/Denver"`.

## 11. Suggested file structure

```text
frontend/
├── index.html                 # shell, fonts, /rum.js, {{VERSION}} footer
└── static/
    ├── css/
    │   ├── tokens.css         # design tokens from section 4
    │   ├── base.css           # reset, typography, focus, calm mode
    │   ├── phone.css          # warm paper screens
    │   └── board.css          # constellation board and status cards
    └── js/
        ├── main.js            # router, app state, live region
        ├── api.js             # real API client
        ├── mock-api.js        # synthetic data
        ├── stream.js          # SSE with fallback
        ├── a11y.js            # announcements, reduced motion, text size
        ├── color.js           # personHue
        ├── screens/
        │   ├── welcome.js
        │   ├── now.js
        │   ├── card.js
        │   ├── show.js
        │   ├── group.js
        │   ├── report.js
        │   ├── met.js
        │   ├── settings.js
        │   ├── shared-card.js
        │   └── staff.js
        └── board/
            ├── board.js       # layout, status cards, ticker, hero number
            ├── sky.js         # canvas, stars, rooms, constellations
            └── demo.js        # demo-mode shortcuts and finale
```

If you can't add a static mount, put everything in `frontend/index.html` with clear section comments, and split later.

## 12. Build order

Ship each step as its own pull request so Gitar reviews every feature. Keep PRs small and describe what changed.

1. **Foundation:** tokens, base styles, router, tab bar, API client, mock API, "Demo data" badge, rename to Affinity.
2. **Onboarding and card:** templates, form with live preview, flip card, done moment.
3. **Now:** placement card, status pill, reroute banner, live region announcements.
4. **Board, part 1:** canvas, rooms, breathing stars, gliding moves, status cards, ticker, hero number, accessible summary.
5. **Group:** countdown, reveal animation, member cards, opener, check-in.
6. **Report and staff:** one-thumb reports, incidents, staff screen.
7. **Board, part 2:** group constellations, demo mode, finale.
8. **Modes:** kubectl mode, calm mode, text size, reduced motion everywhere.
9. **Extras:** show across the table, QR sharing, people you've met and your constellation.
10. **Polish:** accessibility audit fixes, empty states, error states, loading states.

If time runs short, cut from the bottom of this list, but never cut accessibility basics from steps 1 to 4.

## 13. Copy guidelines

- Sentence case everywhere: "Make my card," not "Make My Card."
- Warm, short and plain. No jargon in human mode.
- Errors say what happened and what to do: *"We couldn't reach the server. We'll keep trying."*
- Empty states invite action: *"No group yet. Turn on 'Find me a group' to join the next break."*
- Never use the words "disabled," "special needs" or diagnosis names in the interface. Describe what helps instead.

## 14. Acceptance checklist

The frontend is done when:

- [ ] A new attendee can make a card from a template in under 30 seconds on a phone.
- [ ] Now, Card, Group, Report and Met screens work with mock data at 375px wide.
- [ ] The board runs smoothly on a laptop driving a projector with 1,000 stars.
- [ ] Demo shortcuts C, G, I, F, K and R all work in `#/board?demo=1`.
- [ ] "0 people alone" updates live, and the finale plays cleanly.
- [ ] kubectl mode works on Now and the board, without revealing access needs.
- [ ] Every status is readable without color.
- [ ] Reduced motion and calm mode remove all animation.
- [ ] Everything works by keyboard, and VoiceOver can complete onboarding and read the Now screen.
- [ ] axe reports no serious or critical issues.
- [ ] No card text, names or access needs appear in URLs, console logs or the board.
- [ ] `/rum.js` still loads, and card inputs are masked in Dash0.
- [ ] `{{VERSION}}` still appears in the footer.
- [ ] The page works with the real API where endpoints exist and falls back to mock data where they don't.
- [ ] Times display in Mountain Time.

## 15. Don'ts

- Don't add a frontend build step or framework.
- Don't use flashing, fast blinking or auto-playing sound.
- Don't show names, card text or access needs on the board.
- Don't invent room accessibility facts. Only show what's reported or confirmed.
- Don't commit straight to `main`. Open a pull request for each step.
- Don't spend more than about 30 minutes on any single animation. If it isn't working, ship the simple version.

When you finish each step, summarize what you built, what you tested, what you skipped, and anything the backend needs to provide.
