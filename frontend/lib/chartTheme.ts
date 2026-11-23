import type { CSSProperties } from "react";

// The tooltip is an HTML element, so CSS var() resolves here (unlike SVG attrs).
export const tooltipContentStyle: CSSProperties = {
  background: "var(--viz-surface)",
  border: "1px solid var(--viz-axis)",
  borderRadius: 8,
  color: "var(--viz-text)",
  fontSize: 12,
};

export const tooltipLabelStyle: CSSProperties = {
  color: "var(--viz-secondary)",
};
