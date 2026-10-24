"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { OPTIONS } from "@/mocks/demo-data";
import type { SortKey, Stage } from "./types";

type Ctx = {
  stage: Stage;
  setStage: (s: Stage) => void;
  offerDismissed: boolean;
  dismissOffer: () => void;
  sort: SortKey;
  setSort: (s: SortKey) => void;
  pickedId: string | null;
  pick: (id: string | null) => void;
  panelOpen: boolean; // mobile bottom sheet
  setPanelOpen: (b: boolean) => void;
  ceiling: number;
  setCeiling: (n: number) => void;
};

const TripCtx = createContext<Ctx | null>(null);

export function TripProvider({ children }: { children: ReactNode }) {
  const [stage, setStage] = useState<Stage>("idle");
  const [offerDismissed, setOfferDismissed] = useState(false);
  const [sort, setSort] = useState<SortKey>("balanced");
  const [pickedId, pick] = useState<string | null>(OPTIONS[0].id);
  const [panelOpen, setPanelOpen] = useState(false);
  const [ceiling, setCeiling] = useState(620);

  const value = useMemo<Ctx>(
    () => ({ stage, setStage, offerDismissed, dismissOffer: () => setOfferDismissed(true), sort, setSort, pickedId, pick, panelOpen, setPanelOpen, ceiling, setCeiling }),
    [stage, offerDismissed, sort, pickedId, panelOpen, ceiling],
  );
  return <TripCtx.Provider value={value}>{children}</TripCtx.Provider>;
}

export function useTrip() {
  const c = useContext(TripCtx);
  if (!c) throw new Error("useTrip must be used inside TripProvider");
  return c;
}
