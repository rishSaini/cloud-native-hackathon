// Every attendee gets a soft color from their random display ID, so their star,
// card accent and group lines all match. Color is never the only way to tell people apart.

export function personHue(id) {
  let h = 0;
  for (const ch of String(id)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return h % 360;
}

export const starColor = (id) => `hsl(${personHue(id)} 70% 78%)`;
export const accentColor = (id) => `hsl(${personHue(id)} 55% 45%)`;
// Behind white initials: white text is at least 4.75:1 on this for every hue.
export const avatarColor = (id) => `hsl(${personHue(id)} 45% 32%)`;
