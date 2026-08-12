"use client";

import { useSyncExternalStore } from "react";
import { getStoredTheme, subscribeToThemeChanges, type Theme } from "@/lib/theme";

function getServerSnapshot(): Theme {
  return "system";
}

export function useTheme(): Theme {
  return useSyncExternalStore(subscribeToThemeChanges, getStoredTheme, getServerSnapshot);
}
