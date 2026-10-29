"use client";

import { useState } from "react";
import { Button, Chip, Dialog, Switch, TextField } from "@/components/ui";
import type { NodeModel } from "./model";

const QUICK = [15, 30, 60, 90, 120];

type Props = {
  from: NodeModel;
  to: NodeModel;
  onClose: () => void;
  onSubmit: (minutes: number, bidirectional: boolean) => Promise<void>;
};

export function LinkDialog({ from, to, onClose, onSubmit }: Props) {
  const [minutes, setMinutes] = useState("30");
  const [bidirectional, setBidirectional] = useState(false);
  const [busy, setBusy] = useState(false);

  const value = Number(minutes);
  const valid = Number.isInteger(value) && value >= 1 && value <= 10080;
  const bothWarehouses = from.kind === "warehouse" && to.kind === "warehouse";

  const submit = async () => {
    if (!valid || busy) return;
    setBusy(true);
    try {
      await onSubmit(value, bothWarehouses && bidirectional);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      title="Новая связь"
      onClose={onClose}
      actions={
        <>
          <Button variant="text" onClick={onClose}>
            Отмена
          </Button>
          <Button onClick={submit} disabled={!valid || busy} icon="add_road">
            Создать
          </Button>
        </>
      }
    >
      <div className="stack">
        <div className="row t-title-m">
          <span>{from.name}</span>
          <span className="ms" aria-hidden>{bidirectional && bothWarehouses ? "swap_horiz" : "arrow_right_alt"}</span>
          <span>{to.name}</span>
        </div>
        <TextField
          label="Время в пути, минут"
          type="number"
          min={1}
          max={10080}
          value={minutes}
          autoFocus
          onChange={(e) => setMinutes(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          error={valid ? undefined : "Целое число от 1 до 10080"}
        />
        <div className="row wrap">
          {QUICK.map((q) => (
            <Chip key={q} selected={value === q} onClick={() => setMinutes(String(q))}>
              {q} мин
            </Chip>
          ))}
        </div>
        {bothWarehouses && <Switch checked={bidirectional} onChange={setBidirectional} label="В обе стороны" />}
        {!bothWarehouses && (
          <div className="t-body-s muted">Путь «склад → ПВЗ»: товары поедут со склада в пункт выдачи.</div>
        )}
      </div>
    </Dialog>
  );
}
