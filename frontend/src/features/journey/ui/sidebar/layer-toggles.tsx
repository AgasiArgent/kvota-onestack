"use client";

/**
 * Eight-layer toggle list (Req 4.1).
 *
 * Pure UI: parent owns state and localStorage persistence; this component
 * only renders checkboxes + fires `onToggle(layer)`.
 */

import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ALL_LAYER_IDS, type LayerId } from "../../lib/use-journey-url-state";

// Human labels per Req 4.1 (Russian UI).
const LAYER_LABELS_RU: Record<LayerId, string> = {
  roles: "Роли",
  stories: "Истории",
  impl: "Impl-статус",
  qa: "QA-статус",
  feedback: "Фидбэк",
  training: "Обучение",
  ghost: "Ghost-узлы",
  screenshots: "Скриншоты",
};

interface Props {
  readonly activeLayers: readonly LayerId[];
  readonly onToggle: (layer: LayerId) => void;
}

export function LayerToggles({ activeLayers, onToggle }: Props) {
  const active = new Set<LayerId>(activeLayers);
  return (
    <div className="flex flex-col gap-2" data-testid="journey-layer-toggles">
      {ALL_LAYER_IDS.map((layer) => {
        const id = `journey-layer-${layer}`;
        const checked = active.has(layer);
        return (
          <div key={layer} className="flex items-center gap-2">
            <Checkbox
              id={id}
              checked={checked}
              onCheckedChange={() => onToggle(layer)}
              data-testid={`journey-layer-toggle-${layer}`}
            />
            <Label htmlFor={id} className="text-sm text-text cursor-pointer">
              {LAYER_LABELS_RU[layer]}
            </Label>
          </div>
        );
      })}
    </div>
  );
}
