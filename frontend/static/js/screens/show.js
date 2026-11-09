// Placeholder until its build step lands (see docs/FRONTEND_PROMPT.md, section 12).
import { placeholder } from "./placeholder.js";

export default {
  ...placeholder({
    title: "Show across the table",
    heading: "Show across the table",
    body: "Soon this shows your card in big, clear text for the person across from you.",
    action: { label: "Back to your card", href: "#/card" },
  }),
};
