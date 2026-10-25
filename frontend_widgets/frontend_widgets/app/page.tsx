"use client";

import { useState } from "react";
import { PlanWidget } from "../src/PlanWidget";
import { sampleFallbacks, sampleInputs } from "../src/demo-data";
import { selectWidgetDeck } from "../src/widget-rules";

const readyDecks = sampleInputs.map(selectWidgetDeck);
const fallbackDecks = sampleFallbacks.map((fallback) => selectWidgetDeck({
  fallback, viewer: { viewerId: "demo-you", locationPermission: "unavailable", confirmedOrigin: null },
}));
const noLocationDeck = selectWidgetDeck({
  ...sampleInputs[0], viewer: { viewerId: "demo-you", locationPermission: "denied", confirmedOrigin: null },
});

export default function Page() {
  const [loading, setLoading] = useState(false);
  const [animationKey, setAnimationKey] = useState(0);
  function play() {
    setLoading(true);
    window.setTimeout(() => { setAnimationKey((key) => key + 1); setLoading(false); }, 950);
  }
  return <main className="handoff-page">
    <header className="handoff-header">
      <div><p className="handoff-kicker">INSTAPLAN · WIDGET HANDOFF</p><h1>A little magic. Then your plan.</h1><p>One widget per plan. An elegant reveal when a sourced recommendation arrives.</p></div>
      <button type="button" className="handoff-play" onClick={play}>Replay formation</button>
    </header>
    <div className="handoff-disclaimer">PRESENTATION SAMPLE — names, dates, fares, event matchups and opening hours here are fictional layout data. Production cards require provider evidence.</div>
    <section className="handoff-section"><h2>Four special cards</h2><p>Flight and train use the current viewer’s confirmed origin. Concert and college football use supported event listings.</p>
      <div className="handoff-grid">{readyDecks.map((deck, i) => <div className="handoff-item" key={i}><span className="handoff-item-label">{["01 / FLIGHT", "02 / TRAIN", "03 / CONCERT", "04 / COLLEGE FOOTBALL"][i]}</span><PlanWidget deck={deck} loading={loading} animationKey={animationKey} demo /></div>)}</div>
    </section>
    <section className="handoff-section"><h2>One shared fallback</h2><p>The same photo, category, title, rating, metadata, verified green status and action pattern serves restaurant, stay and venue. Status is shown in this sample to demonstrate placement.</p>
      <div className="handoff-grid">{fallbackDecks.map((deck, i) => <div className="handoff-item" key={i}><span className="handoff-item-label">{["RESTAURANT", "STAY", "VENUE"][i]}</span><PlanWidget deck={deck} loading={loading} animationKey={animationKey} demo /></div>)}</div>
    </section>
    <section className="handoff-section"><h2>No location → fallback</h2><p>The flight card is suppressed when location permission is denied, even if a sample flight is available. No other member’s route appears.</p><PlanWidget deck={noLocationDeck} loading={loading} animationKey={animationKey} demo /></section>
  </main>;
}
