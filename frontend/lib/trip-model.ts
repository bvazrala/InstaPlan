// Trip data model: shared criteria (filled from chat, then by hand) and per-person profiles.
// Pure functions only. Where a value came from is part of the data, so the UI can always show why it is there.
import type { Message } from "./types";
import { memberById } from "@/mocks/demo-data";

export type GroupField = "destination" | "dates";
export type PersonField = "from" | "mode" | "distance" | "diet" | "notes";

/** Where a value came from: a chat message the assistant read, or someone typing it in. */
export type Source = { kind: "chat"; messageId: string; quote: string } | { kind: "manual" };
export type Entry = { value: string; by: string; source: Source };

/** What the group assistant pulled out of one message. `scope` is "group" or the member the fact is about. */
export type Extraction = { scope: string; field: GroupField | PersonField; value: string };

/** Values typed in by hand. An empty string clears a value the assistant picked up. */
export type Edits = {
  group: Partial<Record<GroupField, string>>;
  people: Record<string, Partial<Record<PersonField, string>>>;
};
export const noEdits = (): Edits => ({ group: {}, people: {} });

export type Profile = {
  group: Partial<Record<GroupField, Entry>>;
  people: Record<string, Partial<Record<PersonField, Entry>>>;
};

export type FieldSpec = { label: string; kind: "text" | "choice" | "multi"; choices?: string[]; placeholder?: string };

export const GROUP_FIELDS: { id: GroupField; spec: FieldSpec }[] = [
  { id: "destination", spec: { label: "Destination", kind: "text", placeholder: "City or region" } },
  { id: "dates", spec: { label: "Dates", kind: "text", placeholder: "e.g. Dec 18 – 21" } },
];

export const DIETS = ["Vegetarian", "Vegan", "Halal", "Kosher", "Gluten-free", "Nut allergy", "No seafood", "No restrictions"];

export const PERSON_FIELDS: { id: PersonField; spec: FieldSpec }[] = [
  { id: "from", spec: { label: "Travelling from", kind: "text", placeholder: "City or airport" } },
  { id: "mode", spec: { label: "Travel mode", kind: "choice", choices: ["Fly", "Drive"] } },
  { id: "distance", spec: { label: "Max travel time", kind: "text", placeholder: "e.g. 5 hours" } },
  { id: "diet", spec: { label: "Diet", kind: "multi", choices: DIETS } },
  { id: "notes", spec: { label: "Comments", kind: "text", placeholder: "Anything else the group should know" } },
];

export const displayName = (id: string) => (id === "me" ? "You" : memberById(id).name);

export function deriveProfile(
  messages: Message[],
  extractions: Record<string, Extraction[]>,
  edits: Edits,
  members: string[],
): Profile {
  const p: Profile = { group: {}, people: Object.fromEntries(members.map((m) => [m, {}])) };

  for (const m of messages) {
    if (m.kind !== "text") continue;
    for (const ex of extractions[m.id] ?? []) {
      const entry: Entry = { value: ex.value, by: m.from, source: { kind: "chat", messageId: m.id, quote: m.text } };
      if (ex.scope === "group") p.group[ex.field as GroupField] = entry;
      else if (p.people[ex.scope]) p.people[ex.scope][ex.field as PersonField] = entry;
    }
  }

  const manual = (value: string): Entry => ({ value, by: "me", source: { kind: "manual" } });
  for (const [f, v] of Object.entries(edits.group) as [GroupField, string][]) {
    if (v) p.group[f] = manual(v); else delete p.group[f];
  }
  for (const [id, fields] of Object.entries(edits.people)) {
    for (const [f, v] of Object.entries(fields) as [PersonField, string][]) {
      if (!p.people[id]) continue;
      if (v) p.people[id][f] = manual(v); else delete p.people[id][f];
    }
  }
  return p;
}

export const personFilled = (p: Profile, id: string) => PERSON_FIELDS.filter((f) => p.people[id]?.[f.id]).length;
export const totalFields = (members: string[]) => GROUP_FIELDS.length + members.length * PERSON_FIELDS.length;
export const filledFields = (p: Profile, members: string[]) =>
  GROUP_FIELDS.filter((f) => p.group[f.id]).length + members.reduce((n, id) => n + personFilled(p, id), 0);
