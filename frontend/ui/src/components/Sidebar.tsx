/**
 * Collapsible workstation sidebar rail with hard-edged boxy styling.
 * Exports `Sidebar` and `SidebarProps` (`collapsed`, `onToggle`) rendering VIA logo, Expand/Collapse button (`aria-label`, `title="Library"` tooltip), Library nav (`aria-label="Library nav"`), and bottom Profile slot with `data-collapsed` and `60px`/`240px` widths.
 * Styled by `Sidebar.css` (`border-right:1px solid var(--border)`) and owned by `Shell`; pure presentational, no storage access.
 */

"use client";

import React from "react";
import "./Sidebar.css";

/**
 * Props for the collapsible sidebar rail; `collapsed` drives 60/240px width and `onToggle` is wired to the Expand/Collapse button.
 */
export interface SidebarProps {
  /** Whether the sidebar is in collapsed (icon-only) state. */
  collapsed: boolean;
  /** Toggle handler invoked when the collapse button is clicked. */
  onToggle: () => void;
}

/**
 * Collapsible sidebar with hard-edged workstation styling.
 *
 * Renders a 240px expanded / 60px collapsed rail with a bottom profile
 * slot, a collapse toggle, and a Library nav item that exposes a `title`
 * tooltip in collapsed mode. Border and layout are handled in
 * `Sidebar.css` via `border-right: 1px solid var(--border)`.
 *
 * @param root0 - Component props.
 * @param root0.collapsed - Collapsed flag.
 * @param root0.onToggle - Toggle callback.
 * @returns The sidebar aside element.
 */
export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
  return (
    <aside
      className="sidebar"
      data-collapsed={collapsed}
      style={{ width: collapsed ? "60px" : "240px" }}
    >
      <div className="sidebar-top">
        <span className="logo">VIA</span>
        <button
          type="button"
          aria-label={collapsed ? "Expand" : "Collapse"}
          onClick={onToggle}
        >
          {collapsed ? "›" : "‹"}
        </button>
      </div>
      <nav aria-label="Library nav">
        <button
          type="button"
          className="nav-active"
          title="Library"
          aria-current="page"
        >
          {collapsed ? (
            <span aria-hidden="true">◧</span>
          ) : (
            <>
              <span aria-hidden="true">◧</span> <span>Library</span>
            </>
          )}
        </button>
      </nav>
      <div className="sidebar-bottom">
        <span>{collapsed ? "•" : "Profile"}</span>
      </div>
    </aside>
  );
}
