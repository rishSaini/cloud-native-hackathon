// Placeholder until its build step lands (see docs/FRONTEND_PROMPT.md, section 12).
import { placeholder } from "./placeholder.js";

export default {
  ...placeholder({
    title: "Your card",
    heading: "Your card",
    body: "Soon you'll see your card here and flip it to show how people should talk to you.",
    action: { label: "Find a talk", href: "#/talks" },
  }),
};
