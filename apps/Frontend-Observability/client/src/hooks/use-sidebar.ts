import { useState, useEffect } from "react";

// Global listener pattern since we don't have a heavier store library like Zustand.
let isCollapsed = localStorage.getItem("sidebar-collapsed") === "true";
const listeners = new Set<(val: boolean) => void>();

export function toggleSidebar() {
  isSidebarCollapsed(!isCollapsed);
}

export function isSidebarCollapsed(collapsed: boolean) {
  isCollapsed = collapsed;
  localStorage.setItem("sidebar-collapsed", isCollapsed ? "true" : "false");
  listeners.forEach((listener) => listener(isCollapsed));
}

export function useSidebar() {
  const [collapsed, setCollapsed] = useState(isCollapsed);

  useEffect(() => {
    listeners.add(setCollapsed);
    return () => {
      listeners.delete(setCollapsed);
    };
  }, []);

  return { isCollapsed: collapsed, toggleSidebar };
}
