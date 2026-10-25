import type { Option, Venue } from "@/lib/types";
import { selectWidgetDeck, safeExternalUrl } from "./widget-rules";
import type { FallbackCardData, ViewerContext } from "./widget-types";
export const noViewer: ViewerContext={viewerId:"",locationPermission:"unavailable",confirmedOrigin:null};
export function venueDeck(venue:Venue,topic:string){
  const fallback:FallbackCardData={id:venue.id,kind:venue.kind??(topic==="Dining"?"restaurant":topic==="Travel"?"stay":"venue"),
    image:{src:safeExternalUrl(venue.imageUrl)??"",alt:venue.title},title:venue.title,
    rating:venue.rating,reviewCount:venue.reviewCount,
    metadata:[venue.address??"Address unavailable",venue.priceLevel?`Price level ${venue.priceLevel}`:"Price unknown"],
    chips:venue.category?[venue.category]:[],actions:venue.url?[{label:"View place",url:venue.url}]:[]};
  const special=venue.special?{...venue.special,forViewerId:venue.special.forViewerId??undefined,originCode:venue.special.originCode??undefined,destinationCode:venue.special.destinationCode??undefined}:null;
  return selectWidgetDeck({fallback,special,viewer:noViewer});
}
export function stayDeck(option:Option){
  return selectWidgetDeck({fallback:{id:option.id,kind:"stay",image:{src:safeExternalUrl(option.imageUrl)??"",alt:option.lodging},title:option.lodging,
    rating:option.lodgingRating,reviewCount:option.lodgingReviewCount,metadata:[option.place,`${option.nights} nights · ${option.dates}`],
    chips:option.lodgingAmenities?.slice(0,3),actions:option.listingUrl?[{label:"View stay",url:option.listingUrl}]:[]},viewer:noViewer});
}
