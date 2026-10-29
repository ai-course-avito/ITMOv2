"use client";

import { Icon, IconButton } from "@/components/ui";
import { ADD_BUILDING_EVENT, BUILDING_MIME, type BuildingType } from "@/lib/buildings";
import { Inspector } from "./Inspectors";

function Building({ type, label, hint, icon, cls }: { type: BuildingType; label: string; hint: string; icon: string; cls: string }) {
  return (
    <div
      className={`building stateful ${cls}`}
      draggable
      role="button"
      tabIndex={0}
      aria-label={`${label}: перетащите на карту`}
      onDragStart={(e) => {
        e.dataTransfer.setData(BUILDING_MIME, type);
        e.dataTransfer.effectAllowed = "copy";
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") window.dispatchEvent(new CustomEvent(ADD_BUILDING_EVENT, { detail: { type } }));
      }}
    >
      <div className="glyph">
        <Icon name={icon} size={32} fill />
      </div>
      <div className="t-title-s">{label}</div>
      <div className="t-body-s" style={{ opacity: 0.8 }}>{hint}</div>
      <IconButton
        small
        className="add"
        icon="add"
        label={`Добавить: ${label}`}
        onClick={() => window.dispatchEvent(new CustomEvent(ADD_BUILDING_EVENT, { detail: { type } }))}
      />
    </div>
  );
}

export function LeftPanel() {
  return (
    <aside className="panel left">
      <div className="panel-head">
        <h2 className="t-title-l">Строения</h2>
      </div>
      <div className="panel-body">
        <div className="palette">
          <Building type="warehouse" label="Склад" hint="хранит товары" icon="warehouse" cls="wh" />
          <Building type="pickupPoint" label="ПВЗ" hint="выдаёт заказы" icon="storefront" cls="pv" />
        </div>
        <div className="t-body-s muted" style={{ padding: "0 8px" }}>
          Перетащите строение на карту или нажмите «+».
        </div>
        <hr className="divider" style={{ margin: "4px 0" }} />
        <Inspector />
      </div>
    </aside>
  );
}
