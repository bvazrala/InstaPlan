import { expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { PlanWidget } from "@/components/planner/widgets/PlanWidget";
import { selectWidgetDeck } from "@/components/planner/widgets/widget-rules";
import { venueDeck, stayDeck } from "@/components/planner/widgets/adapters";
import type { SpecialCardData } from "@/components/planner/widgets/widget-types";
import { option } from "./fixtures";
const fallback={id:'place',kind:'venue' as const,image:{src:'https://images.example/place.jpg',alt:'Place'},title:'Venue',metadata:['Austin'],actions:[{label:'View venue',url:'https://booking.example/venue'}]};
const special:SpecialCardData={id:'flight',kind:'flight',image:{src:'https://images.example/destination.jpg',alt:'Destination'},title:'AUS → JFK',subtitle:'Your route',dateLabel:'2030-11-05 – 2030-11-09',booking:{label:'View flight',url:'https://airline.example/book'},forViewerId:'alice',originCode:'AUS',destinationCode:'JFK',provider:'SerpApi Google Flights',retrievedAt:'2026-10-25T12:00:00Z'};
it('gates flight and train slides on the actual viewer, permission and confirmed origin',()=>{
  const viewer={viewerId:'alice',locationPermission:'granted' as const,confirmedOrigin:'AUS'};
  expect(selectWidgetDeck({fallback,special,viewer}).slides).toHaveLength(2);
  for(const locationPermission of ['denied','unavailable'] as const)expect(selectWidgetDeck({fallback,special,viewer:{...viewer,locationPermission}}).slides).toHaveLength(1);
  expect(selectWidgetDeck({fallback,special,viewer:{...viewer,viewerId:'bob'}}).slides).toHaveLength(1);
  expect(selectWidgetDeck({fallback,special,viewer:{...viewer,confirmedOrigin:null}}).slides).toHaveLength(1);
  expect(selectWidgetDeck({fallback,special:{...special,kind:'train'},viewer}).slides).toHaveLength(2);
});
it('keeps unsupported, unsafe or incomplete special results on the fallback',()=>{
  const viewer={viewerId:'alice',locationPermission:'granted' as const,confirmedOrigin:'AUS'};
  expect(selectWidgetDeck({fallback,special:{...special,booking:{label:'Book',url:'javascript:bad'}},viewer}).slides).toHaveLength(1);
  expect(selectWidgetDeck({fallback,special:{...special,kind:'drive' as never},viewer}).slides).toHaveLength(1);
  expect(selectWidgetDeck({fallback:null,special,viewer}).slides).toHaveLength(0);
});
it('renders a real place without inventing a photo, dollars or opening status',()=>{
  const deck=venueDeck({id:'v',title:'Cafe',address:'Austin',rating:4.8,priceLevel:'$$',url:'https://cafe.example',provider:'SerpApi',retrievedAt:'2026-10-25T12:00:00Z',fit:null,evidence:[],warnings:[],pickEligible:true},'Dining');
  render(<PlanWidget deck={deck}/>);
  expect(screen.getByText(/Price level \$\$/)).toBeInTheDocument();
  expect(screen.queryByText(/Open until/)).not.toBeInTheDocument();
  expect(screen.queryByRole('img',{name:'Cafe'})).not.toBeInTheDocument();
});
it('supports sourced concert and football slides, keyboard navigation and no fabricated ticket tiers',()=>{
  const deck=selectWidgetDeck({fallback,special:{...special,kind:'concert',title:'Concert'},viewer:{viewerId:'alice',locationPermission:'denied',confirmedOrigin:null}});
  render(<PlanWidget deck={deck}/>);
  expect(screen.getByText('Compare current availability on the booking site')).toBeInTheDocument();
  fireEvent.keyDown(screen.getByRole('region'),{key:'ArrowDown'});
  expect(screen.getByRole('heading',{name:'Venue'})).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Show slide 1 of 2'}));
  expect(screen.getByRole('heading',{name:'Concert'})).toBeInTheDocument();
  expect(selectWidgetDeck({fallback,special:{...special,kind:'college_football'},viewer:{viewerId:'alice',locationPermission:'denied',confirmedOrigin:null}}).slides).toHaveLength(2);
});
it('does not invent amenities or reviews for older travel fixtures',()=>{
  const data=stayDeck(option()).slides[0];expect(data.kind).toBe('fallback');if(data.kind==='fallback'){expect(data.data.reviewCount).toBeUndefined();expect(data.data.image.src).toBe('');}
});
it('hides stale, unsupported opening hours even if a result has a fresh retrieval time',()=>{
  render(<PlanWidget deck={{slides:[{kind:'fallback',data:{...fallback,status:{label:'Open until 10 PM',source:'provider',verified:false,retrievedAt:new Date().toISOString()}}}],reason:'fallback_only'}}/>);
  expect(screen.queryByText('Open until 10 PM')).not.toBeInTheDocument();
});
