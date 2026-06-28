"use client";

import { useEffect, useState } from "react";

import { getToolkitOverview } from "@/lib/api/toolkit";
import type { ToolkitOverview } from "@/types/toolkit";

type TrainingOverviewState = {
  overview: ToolkitOverview | null;
  loading: boolean;
  error: string | null;
};

export function useTrainingOverview(): TrainingOverviewState {
  const [state, setState] = useState<TrainingOverviewState>({
    overview: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    let mounted = true;
    getToolkitOverview()
      .then((overview) => {
        if (mounted) {
          setState({ overview, loading: false, error: null });
        }
      })
      .catch((caught) => {
        if (mounted) {
          setState({
            overview: null,
            loading: false,
            error: caught instanceof Error ? caught.message : "采集工具概览暂不可用",
          });
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  return state;
}
