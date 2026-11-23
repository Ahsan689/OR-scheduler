import type { CSSProperties, SVGProps } from "react";

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

// Recharts `tick` takes SVG text props, not CSS properties.
export const axisTick: SVGProps<SVGTextElement> = {
  fill: "var(--viz-muted)",
  fontSize: 12,
};
