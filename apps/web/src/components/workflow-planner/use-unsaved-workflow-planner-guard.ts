"use client";

import { useEffect } from "react";

const leaveMessage = "当前 Workflow Planner 有未保存变更，确定离开吗？";

function isOrdinaryPrimaryClick(event: MouseEvent): boolean {
  return (
    !event.defaultPrevented &&
    event.button === 0 &&
    !event.metaKey &&
    !event.ctrlKey &&
    !event.shiftKey &&
    !event.altKey
  );
}

function clickedAnchor(event: MouseEvent): HTMLAnchorElement | null {
  if (!(event.target instanceof Element)) {
    return null;
  }
  const anchor = event.target.closest("a[href]");
  return anchor instanceof HTMLAnchorElement ? anchor : null;
}

function isGuardedSameOriginNavigation(anchor: HTMLAnchorElement): boolean {
  const target = anchor.getAttribute("target")?.trim().toLowerCase();
  if ((target && target !== "_self") || anchor.hasAttribute("download")) {
    return false;
  }
  let destination: URL;
  try {
    destination = new URL(anchor.href, window.location.href);
  } catch {
    return false;
  }
  if (destination.origin !== window.location.origin) {
    return false;
  }
  const current = new URL(window.location.href);
  return !(
    destination.pathname === current.pathname &&
    destination.search === current.search &&
    destination.hash.length > 0
  );
}

export function useUnsavedWorkflowPlannerGuard(dirty: boolean): void {
  useEffect(() => {
    if (!dirty) {
      return;
    }

    function onBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
      event.returnValue = "";
    }

    function onDocumentClick(event: MouseEvent) {
      if (!isOrdinaryPrimaryClick(event)) {
        return;
      }
      const anchor = clickedAnchor(event);
      if (
        !anchor ||
        !isGuardedSameOriginNavigation(anchor) ||
        window.confirm(leaveMessage)
      ) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
    }

    window.addEventListener("beforeunload", onBeforeUnload);
    document.addEventListener("click", onDocumentClick, true);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      document.removeEventListener("click", onDocumentClick, true);
    };
  }, [dirty]);
}
