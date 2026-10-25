/* eslint-disable @next/next/no-img-element -- Provider images are already optimized; preserve their source URLs. */
"use client";

import { useEffect, useRef, useState } from "react";
import "./PlanWidget.css";
import { safeAction } from "./widget-rules";
import type { FallbackCardData, SpecialCardData, VerifiedStatus, WidgetDeck, WidgetSlide } from "./widget-types";

const CARD_LABEL: Record<SpecialCardData["kind"], string> = {
  flight: "Flight", train: "Train", concert: "Concert", college_football: "College football",
};
const FALLBACK_LABEL: Record<FallbackCardData["kind"], string> = {
  restaurant: "Restaurant", stay: "Stay", venue: "Venue",
};

function showStatus(status: VerifiedStatus | null | undefined, demo: boolean): boolean {
  if (!status?.label.trim()) return false;
  if (demo) return true;
  if (!status.verified || !status.source.trim()) return false;
  const age = Date.now() - Date.parse(status.retrievedAt);
  return Number.isFinite(age) && age >= 0 && age <= 15 * 60 * 1000;
}

function LinkAction({ label, url, primary }: { label: string; url: string; primary?: boolean }) {
  const action = safeAction({ label, url });
  if (!action) return null;
  return <a className={`ipw-action${primary ? " ipw-action--primary" : ""}`} href={action.url} target="_blank" rel="noopener noreferrer">{action.label}</a>;
}

function Rating({ score, count }: { score?: number | null; count?: number | null }) {
  if (score == null || !Number.isFinite(score)) return null;
  return <div className="ipw-rating" aria-label={`Rated ${score.toFixed(1)} out of 5${count == null ? "" : `, ${count.toLocaleString()} reviews`}`}>
    <span className="ipw-stars" aria-hidden="true">{Array.from({ length: 5 }, (_, i) => <img key={i} src="/planner/star.svg" width="12" height="12" alt="" style={{opacity:i<Math.round(score)?1:.22}} />)}</span>
    <strong>{score.toFixed(1)}</strong>{count != null && <span className="ipw-muted">({count >= 1000 ? `${(count / 1000).toFixed(1)}k` : count})</span>}
  </div>;
}

function SpecialCard({ data, slideCount }: { data: SpecialCardData; slideCount: number }) {
  const choices = data.choices?.filter((choice) => choice.label.trim() && choice.price?.trim()).slice(0, 2) ?? [];
  return <>
    <div className="ipw-photo ipw-photo--hero"><img src={data.image.src} alt={data.image.alt} /></div>
    <div className="ipw-hero-shade" aria-hidden="true" />
    <span className="ipw-category ipw-category--hero">{CARD_LABEL[data.kind]}</span>
    <div className="ipw-hero-copy"><h3>{data.title}</h3><p>{data.subtitle}</p></div>
    <div className="ipw-special-body">
      <p className="ipw-meta ipw-reveal ipw-reveal--one">{data.dateLabel}</p>
      {choices.length > 0 ? <div className="ipw-choices ipw-reveal ipw-reveal--two">{choices.map((choice) => <div className="ipw-choice" key={choice.label}><span>{choice.label}</span><strong>{choice.price}</strong></div>)}</div> : <p className="ipw-price-unknown ipw-reveal ipw-reveal--two">Compare current availability on the booking site</p>}
      <div className="ipw-special-action ipw-reveal ipw-reveal--three"><LinkAction {...data.booking} primary /></div>
      <p className="ipw-footnote ipw-reveal ipw-reveal--four">{data.kind === "flight" || data.kind === "train" ? "Your route · 1 traveler" : "Per ticket · Compare availability"}</p>
    </div>
    {slideCount === 2 && <span className="ipw-stack-dots" aria-hidden="true"><img src="/planner/stack-dots.svg" width="18" height="5" alt="" /></span>}
  </>;
}

function FallbackCard({ data, demo }: { data: FallbackCardData; demo: boolean }) {
  const actions = data.actions.filter((action) => safeAction(action)).slice(0, 2);
  return <>
    <div className={`ipw-photo ipw-photo--place${data.image.src ? "" : " ipw-photo--empty"}`}>{data.image.src && <img src={data.image.src} alt={data.image.alt} referrerPolicy="no-referrer" onError={event => {event.currentTarget.style.display="none";event.currentTarget.parentElement?.classList.add("ipw-photo--empty");}}/>}</div>
    <span className="ipw-category ipw-category--place">{FALLBACK_LABEL[data.kind]}</span>
    <div className="ipw-place-body">
      <h3 className="ipw-reveal ipw-reveal--one">{data.title}</h3>
      <div className="ipw-reveal ipw-reveal--two"><Rating score={data.rating} count={data.reviewCount} /></div>
      <p className="ipw-meta ipw-reveal ipw-reveal--two">{data.metadata.filter(Boolean).join(" · ")}</p>
      {showStatus(data.status, demo) && <p className="ipw-open ipw-reveal ipw-reveal--three">{data.status!.label}</p>}
      {!!data.chips?.length && <div className="ipw-chips ipw-reveal ipw-reveal--three">{data.chips.slice(0, 3).map((chip) => <span key={chip}>{chip}</span>)}</div>}
      {actions.length > 0 && <div className="ipw-place-actions ipw-reveal ipw-reveal--four">{actions.map((action, i) => <LinkAction key={`${action.label}-${i}`} {...action} primary={i === actions.length - 1} />)}</div>}
    </div>
  </>;
}

function FormationSkeleton() {
  return <div className="ipw-skeleton" aria-hidden="true">
    <div className="ipw-skeleton-photo" /><span className="ipw-skeleton-tag" /><span className="ipw-skeleton-title" />
    <span className="ipw-skeleton-meta" /><span className="ipw-skeleton-price ipw-skeleton-price--left" /><span className="ipw-skeleton-price ipw-skeleton-price--right" />
    <span className="ipw-skeleton-button" /><span className="ipw-shimmer" />
  </div>;
}

/** Fixed 338×354 design slot. `loading` can remain true until a provider result arrives. */
export function PlanWidget({ deck, loading = false, animationKey = "", demo = false }: {
  deck: WidgetDeck;
  loading?: boolean;
  animationKey?: string | number;
  /** Presentation only: reveals explicitly fictional sample status copy. */
  demo?: boolean;
}) {
  const [active, setActive] = useState(0);
  const [phase, setPhase] = useState<"loading" | "revealing" | "ready">(loading ? "loading" : "revealing");
  const pointerY = useRef<number | null>(null);
  const slides = deck.slides.slice(0, 2);
  const slide: WidgetSlide | undefined = slides[Math.min(active, slides.length - 1)];
  const slideIds = slides.map((item) => item.data.id).join("|");

  useEffect(() => { const id = window.setTimeout(() => setActive(0), 0); return () => window.clearTimeout(id); }, [slideIds, animationKey]);
  useEffect(() => {
    const start = window.setTimeout(() => setPhase(loading ? "loading" : "revealing"), 0);
    const id = loading ? undefined : window.setTimeout(() => setPhase("ready"), 2200);
    return () => { window.clearTimeout(start); window.clearTimeout(id); };
  }, [loading, animationKey, slideIds]);

  if (!loading && !slide) return null;
  const go = (index: number) => setActive(Math.max(0, Math.min(index, slides.length - 1)));
  return <section
    className="ipw-widget" data-phase={loading ? "loading" : phase} data-card-kind={slide?.kind === "special" ? slide.data.kind : slide?.data.kind ?? "loading"}
    role="region" aria-roledescription="plan widget" aria-label="Plan recommendation"
    tabIndex={slides.length > 1 ? 0 : -1}
    onKeyDown={(event) => { if (event.key === "ArrowDown" || event.key === "ArrowRight") { event.preventDefault(); go(active + 1); } else if (event.key === "ArrowUp" || event.key === "ArrowLeft") { event.preventDefault(); go(active - 1); } }}
    onPointerDown={(event) => { pointerY.current = event.clientY; }}
    onPointerUp={(event) => { if (pointerY.current == null || slides.length < 2) return; const delta = event.clientY - pointerY.current; pointerY.current = null; if (Math.abs(delta) > 36) go(active + (delta < 0 ? 1 : -1)); }}
  >
    {slide && <div className="ipw-content" key={slide.data.id}>{slide.kind === "special" ? <SpecialCard data={slide.data} slideCount={slides.length} /> : <FallbackCard data={slide.data} demo={demo} />}</div>}
    {(phase === "loading" || phase === "revealing") && <FormationSkeleton />}
    {slides.length > 1 && <div className="ipw-pagination" aria-label="Widget slides">{slides.map((item, i) => <button key={item.data.id} type="button" className={i === active ? "is-active" : ""} aria-label={`Show slide ${i + 1} of ${slides.length}`} aria-current={i === active ? "true" : undefined} onClick={() => go(i)} />)}</div>}
  </section>;
}
