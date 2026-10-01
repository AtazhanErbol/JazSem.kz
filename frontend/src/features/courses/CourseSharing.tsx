import { useState } from "react";
import { useTranslation } from "react-i18next";
import { RemoteSelect } from "../../components/RemoteSelect";
import { useAction } from "../../hooks/useAction";

export function CourseSharing({
  id,
  teacher,
  published,
}: {
  id: string;
  teacher: string;
  published: boolean;
}) {
  const { t } = useTranslation();
  const action = useAction();
  const [student, setStudent] = useState("");
  const [group, setGroup] = useState("");
  return (
    <section className="panel" id="course-sharing">
      <h2>{t("workspace.assignTitle")}</h2>
      <p className="muted">{t("workspace.assignHint")}</p>
      {!published && (
        <p className="notice">{t("workspace.publishBeforeAssign")}</p>
      )}
      <h3>{t("student")}</h3>
      <RemoteSelect
        source={`users/?role=STUDENT&is_active=true&owner_teacher=${teacher}`}
        label={t("student")}
        value={student}
        onChange={(value) => setStudent(String(value))}
      />
      <button
        className="primary contextual-action"
        disabled={!published || !student || action.pending}
        onClick={() =>
          void action.run(
            `courses/${id}/assign/`,
            { student },
            "POST",
            t("workspace.assigned"),
          )
        }
      >
        {t("assign")}
      </button>
      {published && !student && (
        <p className="field-hint">{t("learningDisplay.chooseRecipient")}</p>
      )}
      <h3>{t("groups")}</h3>
      <RemoteSelect
        source={`groups/?status=ACTIVE&teacher=${teacher}`}
        label={t("groups")}
        value={group}
        onChange={(value) => setGroup(String(value))}
      />
      <button
        className="primary contextual-action"
        disabled={!published || !group || action.pending}
        onClick={() =>
          void action.run(
            `groups/${group}/assign/`,
            { course: id },
            "POST",
            t("workspace.groupAssigned"),
          )
        }
      >
        {t("assign")}
      </button>
      {published && !group && (
        <p className="field-hint">{t("learningDisplay.chooseRecipient")}</p>
      )}
      {action.feedback}
    </section>
  );
}
