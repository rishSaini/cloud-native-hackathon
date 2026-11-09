// Placeholder until its build step lands (see docs/FRONTEND_PROMPT.md, section 12).
import { placeholder } from "./placeholder.js";

export default {
  ...placeholder({
    title: "Settings",
    heading: "Settings",
    body: "Calm mode, text size and more are coming here soon.",
    action: { label: "Back to now", href: "#/now" },
  }),
};
