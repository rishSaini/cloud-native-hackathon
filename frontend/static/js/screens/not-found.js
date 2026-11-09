// Placeholder until its build step lands (see docs/FRONTEND_PROMPT.md, section 12).
import { placeholder } from "./placeholder.js";

export default {
  ...placeholder({
    title: "Not found",
    heading: "We couldn't find that page",
    body: "The link may be old. Here's a way back.",
    action: { label: "Go to now", href: "#/now" },
  }),
};
