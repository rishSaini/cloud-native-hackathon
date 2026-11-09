// Placeholder until its build step lands (see docs/FRONTEND_PROMPT.md, section 12).
import { placeholder } from "./placeholder.js";

export default {
  ...placeholder({
    title: "Staff incidents",
    heading: "Staff incidents",
    body: "Open incidents will be listed here.",
    action: null,
  }),
  chrome: false,
};
