"use client";

import { useState } from "react";
import { Check, ChevronDown, Lock, Pencil } from "lucide-react";
import { displayName, personFilled, PERSON_FIELDS, type Entry, type FieldSpec, type PersonField, type Profile } from "@/lib/trip-model";
import { Avatar } from "@/components/chat/Avatar";
import { Badge, Button, Chip, inputCls, Segmented } from "@/components/ui/primitives";

/** One line saying where a value came from: the chat message it was read from, or who typed it in. */
function SourceLine({ entry }: { entry: Entry }) {
  const text = entry.source.kind === "chat" ? `“${entry.source.quote}” · ${displayName(entry.by)}` : `Added by ${displayName(entry.by)}`;
  return <p className="truncate text-xs text-muted">{text}</p>;
}

function Editor({ spec, initial, onSave, onCancel }: { spec: FieldSpec; initial: string; onSave: (v: string) => void; onCancel: () => void }) {
  const [value, setValue] = useState(initial);
  const picked = value ? value.split(", ").filter(Boolean) : [];
  const toggle = (c: string) => setValue((picked.includes(c) ? picked.filter((x) => x !== c) : [...picked, c]).join(", "));

  return (
    <div className="animate-in-fade py-3">
      <p className="mb-1.5 text-xs text-muted">{spec.label}</p>
      {spec.kind === "text" && (
        <input
          autoFocus
          value={value}
          placeholder={spec.placeholder}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") onSave(value.trim()); if (e.key === "Escape") onCancel(); }}
          className={inputCls}
        />
      )}
      {spec.kind === "choice" && (
        <Segmented value={value || null} onChange={setValue} options={(spec.choices ?? []).map((c) => ({ id: c, label: c }))} />
      )}
      {spec.kind === "multi" && (
        <div className="flex flex-wrap gap-1.5">{(spec.choices ?? []).map((c) => <Chip key={c} on={picked.includes(c)} onClick={() => toggle(c)}>{c}</Chip>)}</div>
      )}
      <div className="mt-2.5 flex items-center gap-2">
        <Button size="sm" onClick={() => onSave(value.trim())}><Check size={14} /> Save</Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>Cancel</Button>
        {initial && <Button size="sm" variant="ghost" className="ml-auto text-red-600 hover:bg-red-50 hover:text-red-700" onClick={() => onSave("")}>Clear</Button>}
      </div>
    </div>
  );
}

/** A single criterion: its value and where it came from. Read-only rows (other people's) can't be edited or filled. */
export function FieldRow({ spec, entry, onSave, readOnly = false }: { spec: FieldSpec; entry?: Entry; onSave?: (v: string) => void; readOnly?: boolean }) {
  const [editing, setEditing] = useState(false);
  if (editing && onSave && !readOnly) return <Editor spec={spec} initial={entry?.value ?? ""} onSave={(v) => { onSave(v); setEditing(false); }} onCancel={() => setEditing(false)} />;
  return (
    <div className="flex items-center gap-3 py-2.5">
      <div className="min-w-0 flex-1 leading-snug">
        <p className="text-xs text-muted">{spec.label}</p>
        {entry ? <p className="text-sm font-medium">{entry.value}</p> : <p className="text-sm text-neutral-400">Not shared yet</p>}
        {entry && <SourceLine entry={entry} />}
      </div>
      {!readOnly && onSave && (entry ? (
        <Button size="icon" variant="ghost" className="size-8 text-muted" onClick={() => setEditing(true)} aria-label={`Edit ${spec.label}`}><Pencil size={15} /></Button>
      ) : (
        <Button size="sm" variant="outline" onClick={() => setEditing(true)}>Add</Button>
      ))}
    </div>
  );
}

/** Collapsible card with one member's criteria. Only your own card is editable. */
export function PersonCard({ id, profile, defaultOpen = false, onEdit }: {
  id: string; profile: Profile; defaultOpen?: boolean; onEdit: (field: PersonField, value: string) => void;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const mine = id === "me";
  const filled = personFilled(profile, id);
  return (
    <li>
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-center gap-3 py-3 text-left">
        <Avatar id={id} size={36} />
        <span className="min-w-0 flex-1 leading-tight">
          <span className="flex items-center gap-1.5 text-sm font-medium">{displayName(id)}{!mine && <Lock size={11} className="text-neutral-400" aria-label="View only" />}</span>
          <span className="block text-xs text-muted">{filled} of {PERSON_FIELDS.length} filled</span>
        </span>
        <span className="flex gap-0.5" aria-hidden>{PERSON_FIELDS.map((f) => <span key={f.id} className={`size-1.5 rounded-full ${profile.people[id]?.[f.id] ? "bg-neutral-900" : "bg-neutral-200"}`} />)}</span>
        <ChevronDown size={16} className={`text-muted transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="animate-in-fade -mt-1 mb-2 divide-y divide-line border-l-2 border-line pl-4">
          {!mine && <p className="pb-2 text-xs text-muted">Only {displayName(id)} can change these.</p>}
          {PERSON_FIELDS.map((f) => (
            <FieldRow key={f.id} spec={f.spec} entry={profile.people[id]?.[f.id]} readOnly={!mine} onSave={mine ? (v) => onEdit(f.id, v) : undefined} />
          ))}
        </div>
      )}
    </li>
  );
}

/** People who aren't part of the plan, collapsed so they don't crowd the lists. */
export function NotIncluded({ people }: { people: { id: string; reason: string }[] }) {
  const [open, setOpen] = useState(false);
  if (people.length === 0) return null;
  return (
    <div className="mt-4 rounded-lg border border-line">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-center justify-between px-3 py-2.5 text-[13px] font-medium text-neutral-600">
        Not included ({people.length})
        <ChevronDown size={15} className={`transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <ul className="animate-in-fade divide-y divide-line border-t border-line">
          {people.map((p) => (
            <li key={p.id} className="flex items-center gap-2.5 px-3 py-2">
              <Avatar id={p.id} size={24} />
              <span className="flex-1 text-[13px] font-medium">{displayName(p.id)}</span>
              <Badge variant="outline">{p.reason}</Badge>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
