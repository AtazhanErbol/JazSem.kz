import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Modal, ErrorState } from "../../components/UI";
import { useAction } from "../../hooks/useAction";
import type { Row } from "../../entities/types";
const kinds = ["ASSIGNMENTS", "TESTS", "FINAL"] as const;
export function GradingWeights({
  course,
  version,
  components,
  onClose,
}: {
  course: string;
  version: string;
  components: Row[];
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const action = useAction();
  const [weights, setWeights] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      kinds.map((kind) => [
        kind,
        String(components.find((c) => c.kind === kind)?.weight ?? 0),
      ]),
    ),
  );
  const values = kinds.map((kind) => Number(weights[kind]));
  const total = values.reduce(
    (sum, v) => sum + (Number.isFinite(v) ? v : 0),
    0,
  );
  const valid =
    values.every((v) => Number.isInteger(v) && v >= 0 && v <= 100) &&
    total === 100;
  const balance = () => {
    const active = kinds.filter((kind) => Number(weights[kind]) > 0);
    if (!active.length) active.push("ASSIGNMENTS");
    const last = active[active.length - 1];
    const rest = active
      .slice(0, -1)
      .reduce((sum, kind) => sum + Number(weights[kind]), 0);
    if (rest < 100 && Number.isInteger(rest))
      setWeights({ ...weights, [last]: String(100 - rest) });
    else
      setWeights(
        Object.fromEntries(
          kinds.map((kind) => [
            kind,
            active.includes(kind)
              ? String(
                  Math.floor(100 / active.length) +
                    (kind === active[0] ? 100 % active.length : 0),
                )
              : "0",
          ]),
        ),
      );
  };
  return (
    <Modal
      title={t("configureWeights")}
      onClose={() => {
        if (!action.pending) onClose();
      }}
    >
      <p className="muted">{t("weightsEditorHint")}</p>
      <div className="record-form">
        {kinds.map((kind) => (
          <label key={kind}>
            {t(kind)} (%)
            <input
              type="number"
              min="0"
              max="100"
              step="1"
              value={weights[kind]}
              disabled={action.pending}
              onChange={(e) =>
                setWeights({ ...weights, [kind]: e.target.value })
              }
            />
          </label>
        ))}
      </div>
      <p role="status" className={valid ? "grading-total complete" : "notice"}>
        {t("workspace.gradingTotal", { total })}
        {!valid && <> · {t("weightsNeed100")}</>}
      </p>
      <button disabled={action.pending} onClick={balance}>
        {t("balanceWeights")}
      </button>
      {action.error != null && <ErrorState error={action.error} />}
      <div className="form-actions">
        <button disabled={action.pending} onClick={onClose}>
          {t("cancel")}
        </button>
        <button
          className="primary"
          disabled={!valid || action.pending}
          onClick={async () => {
            const result = await action.run(
              `courses/${course}/grading-weights/`,
              {
                version,
                weights: Object.fromEntries(
                  kinds.map((kind) => [kind, Number(weights[kind])]),
                ),
              },
            );
            if (result.ok) onClose();
          }}
        >
          {t("save")}
        </button>
      </div>
    </Modal>
  );
}
