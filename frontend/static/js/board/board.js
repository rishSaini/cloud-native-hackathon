// Big-screen board. The constellation canvas, status cards and ticker land in build step 4.
// Until then this shows a plain, accessible room list from the board snapshot.

import { api } from "../api.js";
import { h } from "../format.js";

function ensureStyles() {
  if (document.getElementById("board-css")) return;
  document.head.append(h("link", { id: "board-css", rel: "stylesheet", href: "/static/css/board.css" }));
}

export default {
  title: "Board",
  chrome: false,
  sky: true,
  async render(main) {
    ensureStyles();
    const list = h("ul", { class: "board-rooms" });
    const alone = h("p", { class: "board-hero" });
    main.append(
      h("section", { class: "board", "aria-labelledby": "board-h" },
        h("h1", { id: "board-h" }, "Affinity"),
        alone,
        h("h2", { class: "visually-hidden" }, "Rooms"),
        list,
      ),
    );

    let stopped = false;
    async function refresh() {
      try {
        const board = await api.board();
        if (stopped || !board) return;
        alone.textContent = `${board.alone ?? 0} people alone`;
        list.replaceChildren(...(board.rooms || []).map((r) =>
          h("li", { class: "board-room" }, `${r.name} · ${r.status} · ${r.taken} of ${r.seats}`)));
      } catch {
        /* keep the last known state */
      }
    }
    await refresh();
    const timer = setInterval(refresh, 5000);
    return () => { stopped = true; clearInterval(timer); };
  },
};
