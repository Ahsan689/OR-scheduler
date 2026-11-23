"use client";

import { useEffect, useState } from "react";

// var() does not resolve inside SVG presentation attributes, so Recharts needs
// concrete hex values. We read the CSS tokens at runtime (theme-aware) and fall
// back to the light palette for the first paint / SSR.
export type ChartColors = {
  series1: string;
  series2: string;
  grid: string;
  axis: string;
  muted: string;
};

const LIGHT: ChartColors = {
  series1: "#2a78d6",
  series2: "#eb6834",
  grid: "#e1e0d9",
  axis: "#c3c2b7",
  muted: "#898781",
};

export function useChartColors(): ChartColors {
  const [colors, setColors] = useState<ChartColors>(LIGHT);

  useEffect(() => {
    const style = getComputedStyle(document.documentElement);
    const read = (name: string, fallback: string): string =>
      style.getPropertyValue(name).trim() || fallback;
    setColors({
      series1: read("--series-1", LIGHT.series1),
      series2: read("--series-2", LIGHT.series2),
      grid: read("--viz-grid", LIGHT.grid),
      axis: read("--viz-axis", LIGHT.axis),
      muted: read("--viz-muted", LIGHT.muted),
    });
  }, []);

  return colors;
}
