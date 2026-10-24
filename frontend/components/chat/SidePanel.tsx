import PanelBody from "./PanelBody";

export default function SidePanel() {
  return (
    <div className="no-scrollbar h-full overflow-y-auto rounded-3xl border border-line bg-white">
      <PanelBody />
    </div>
  );
}
