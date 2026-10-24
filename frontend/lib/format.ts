// Presentation helpers.

export const money = (n: number) => `$${Math.round(n).toLocaleString()}`;

/** Group fit color: 0 → red, 50 → yellow, 100 → green. */
export const fitColor = (fit: number, a = 1) => `hsl(${Math.round((fit / 100) * 125)} 72% 46% / ${a})`;

/** Light background tint for the same fit value. */
export const fitTint = (fit: number) => `hsl(${Math.round((fit / 100) * 125)} 80% 94%)`;
