// Placeholder until its build step lands (see docs/FRONTEND_PROMPT.md, section 12).
import { placeholder } from "./placeholder.js";

export default {
  ...placeholder({
    title: "Shared card",
    heading: "Shared card",
    body: "Shared cards are coming soon.",
    action: { label: "Open Affinity", href: "/#/" },
  }),
};
