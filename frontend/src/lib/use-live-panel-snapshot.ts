"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { PanelSnapshot } from "@/lib/panel-types";

const POLL_INTERVAL_MS = 5000;

type SnapshotResponse = {
  snapshot: PanelSnapshot;
  warning?: string;
};

export function useLivePanelSnapshot(initialSnapshot: PanelSnapshot, initialWarning?: string) {
  const [snapshot, setSnapshot] = useState(initialSnapshot);
  const [warning, setWarning] = useState(initialWarning);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const inFlightRef = useRef(false);

  useEffect(() => {
    setSnapshot(initialSnapshot);
    setWarning(initialWarning);
  }, [initialSnapshot, initialWarning]);

  const refreshSnapshot = useCallback(async () => {
    if (inFlightRef.current || document.visibilityState === "hidden") {
      return;
    }

    inFlightRef.current = true;
    setIsRefreshing(true);
    try {
      const response = await fetch("/api/panel/snapshot", {
        cache: "no-store",
        headers: {
          "Cache-Control": "no-store",
        },
      });
      const payload = (await response.json().catch(() => null)) as SnapshotResponse | null;
      if (!payload) {
        return;
      }
      setWarning(payload.warning);
      if (!response.ok || !payload.snapshot) {
        return;
      }
      setSnapshot(payload.snapshot);
    } finally {
      inFlightRef.current = false;
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      void refreshSnapshot();
    }, POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [refreshSnapshot]);

  return {
    snapshot,
    warning,
    isRefreshing,
    refreshSnapshot,
  };
}
