"use client";

import PanelBody from "./PanelBody";

export default function SidePanel() {
  return (
    <div className="no-scrollbar h-full overflow-y-auto bg-white">
      <PanelBody />
    </div>
  );
}
