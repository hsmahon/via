/**
 * 3-pane workstation shell that owns the collapsible sidebar state and grid layout.
 * Exports `Shell` and `ShellProps` (`left`/`center`/`right`/`children` slots) and toggles `60px`↔`240px` via `gridTemplateColumns` while persisting `via:sidebar-collapsed` in `localStorage` (controlled vs uncontrolled).
 * Depends on `Sidebar` for the left rail and `globals.css` `.shell` tokens; composed by `page.tsx` to host `Library` / `VideoWorkspace` / `AgentPane`.
 */

"use client";

import React, { useEffect, useState } from "react";
import Sidebar from "./Sidebar";

/**
 * Props for the 3-pane workstation shell.
 */
export interface ShellProps {
  /** Optional controlled collapsed flag; when omitted the shell manages state via localStorage. */
  collapsed?: boolean;
  /** Callback when collapsed state changes (controlled or uncontrolled). */
  onCollapsedChange?: (collapsed: boolean) => void;
  /** Left pane content. When omitted the built-in {@link Sidebar} is rendered. */
  left?: React.ReactNode;
  /** Center pane content (e.g. Library + VideoWorkspace). */
  center?: React.ReactNode;
  /** Right pane content (e.g. AgentPane). */
  right?: React.ReactNode;
  /** Fallback children rendered when explicit `left`/`center`/`right` slots are not used. */
  children?: React.ReactNode;
}

const STORAGE_KEY = "via:sidebar-collapsed";

/**
 * Workstation shell that wraps the standard CSS grid and persists the
 * sidebar collapsed state in `localStorage`.
 *
 * Layout mirrors `.shell` in `globals.css` (`var(--sidebar-width) 1fr var(--agent-width)`),
 * but overrides the sidebar width inline so toggling from 240px ↔ 60px does
 * not require a full stylesheet mutation. When `collapsed` is supplied the
 * component is controlled; otherwise it hydrates from `localStorage` and
 * writes back on every toggle.
 *
 * @param root0 - Component props.
 * @param root0.collapsed - Optional controlled collapsed value.
 * @param root0.onCollapsedChange - Change notifier.
 * @param root0.left - Left slot; defaults to {@link Sidebar}.
 * @param root0.center - Center slot.
 * @param root0.right - Right slot.
 * @param root0.children - Fallback children slot.
 * @returns The grid shell element containing the 3 panes.
 */
export default function Shell({
  collapsed: controlledCollapsed,
  onCollapsedChange,
  left,
  center,
  right,
  children,
}: ShellProps) {
  const [internalCollapsed, setInternalCollapsed] = useState(false);

  // Hydrate from localStorage on mount (uncontrolled mode only).
  useEffect(() => {
    if (controlledCollapsed !== undefined) return;
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw !== null) setInternalCollapsed(raw === "true");
    } catch {
      // ignore storage errors (e.g. SSR, privacy mode)
    }
  }, [controlledCollapsed]);

  const collapsed = controlledCollapsed ?? internalCollapsed;

  /**
   * Toggle collapsed state and persist to localStorage.
   */
  function handleToggle(): void {
    const next = !collapsed;
    if (controlledCollapsed === undefined) {
      setInternalCollapsed(next);
      try {
        window.localStorage.setItem(STORAGE_KEY, String(next));
      } catch {
        // ignore
      }
    }
    onCollapsedChange?.(next);
  }

  // Persist controlled value as well so a reload restores it.
  useEffect(() => {
    if (controlledCollapsed === undefined) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, String(controlledCollapsed));
    } catch {
      // ignore
    }
  }, [controlledCollapsed]);

  const hasSlots = left !== undefined || center !== undefined || right !== undefined;
  const sidebarNode = left ?? <Sidebar collapsed={collapsed} onToggle={handleToggle} />;

  return (
    <div
      className="shell"
      style={
        {
          gridTemplateColumns: `${collapsed ? "60px" : "240px"} 1fr var(--agent-width)`,
        } as React.CSSProperties
      }
    >
      {hasSlots ? (
        <>
          {sidebarNode}
          {center ? <div className="shell-center">{center}</div> : null}
          {right ? <div className="shell-right">{right}</div> : null}
        </>
      ) : children ? (
        <>{children}</>
      ) : (
        sidebarNode
      )}
    </div>
  );
}
