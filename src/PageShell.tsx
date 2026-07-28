/** Height of Steam's top bar in Big Picture; routes render underneath it. */
export const TOP_BAR = "40px";

/**
 * Route wrapper.
 *
 * Deliberately does no scrolling of its own. Three attempts at hand-rolling a
 * scroll container — plain div, then Focusable with flow-children, then
 * page-native sections — all left the D-pad unable to reach the bottom of a
 * long page, because Steam's gamepad navigation drives scrolling through its
 * own page components and cannot be told about an arbitrary overflow div.
 * SidebarNavigation owns that; this only reserves space below the top bar.
 */
import { Focusable, ProgressBar } from "@decky/ui";
import { ReactNode } from "react";

export function PageShell({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        marginTop: TOP_BAR,
        height: `calc(100% - ${TOP_BAR})`,
        color: "#dcdedf",
      }}
    >
      {children}
    </div>
  );
}

/** Column of content for one SidebarNavigation page. */
export function PageBody({ children }: { children: ReactNode }) {
  return (
    <Focusable
      flow-children="column"
      noFocusRing
      style={{ display: "flex", flexDirection: "column", paddingBottom: "40px" }}
    >
      {children}
    </Focusable>
  );
}

/** A row of compact actions, so buttons stop eating a line each. */
export function ActionRow({ children }: { children: ReactNode }) {
  return (
    <Focusable
      flow-children="row"
      style={{
        display: "flex",
        gap: "10px",
        marginTop: "12px",
        marginBottom: "4px",
        width: "100%",
        minWidth: 0,
      }}
    >
      {children}
    </Focusable>
  );
}

/**
 * Progress with a one-line status.
 *
 * ProgressBarWithInfo renders the status inside its own markup, where a long
 * game title has nothing to truncate against and pushes the bar off the panel.
 * Splitting them means the text can be clipped with an ellipsis and the bar can
 * be pinned to the row width.
 */
export function Progress({
  progress,
  status,
}: {
  progress: number;
  status: string;
}) {
  return (
    <div style={{ width: "100%", minWidth: 0, padding: "4px 0" }}>
      <div
        style={{
          ...ui.small,
          opacity: ui.dim,
          marginBottom: "6px",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
        title={status}
      >
        {status}
      </div>
      <div style={{ width: "100%", minWidth: 0, overflow: "hidden" }}>
        <ProgressBar nProgress={progress} />
      </div>
    </div>
  );
}

/** One line of content within a page. */
export function Row({ children }: { children: ReactNode }) {
  return (
    <div style={{ width: "100%", minWidth: 0, marginBottom: "10px" }}>
      {children}
    </div>
  );
}

/** Long paths and notes wrap instead of trailing off the panel edge. */
export const wrapText = {
  overflowWrap: "anywhere" as const,
  wordBreak: "break-word" as const,
};

/**
 * Shared visual scale.
 *
 * Two type sizes and two secondary opacities; the shared button height lives
 * just below in `compactButton`. Every value used to be picked locally, which
 * produced four font sizes and five button heights across two screens — small
 * differences, but collectively the thing that makes an interface look
 * assembled rather than designed.
 */
export const ui = {
  /** Body copy: statuses, messages, list rows. */
  text: { fontSize: "0.8em" } as const,
  /** Supporting copy: hints, paths, counts. */
  small: { fontSize: "0.72em" } as const,
  /** Present but recessive. */
  dim: 0.65,
  /** Background information — paths, file locations. */
  faint: 0.45,
} as const;

export const compactButton = {
  flex: "1 1 0",
  minWidth: 0,
  height: "36px",
  padding: "0 10px",
  fontSize: "0.8em",
};

