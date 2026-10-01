import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { ErrorState, Loading, Modal } from "../../components/UI";
import { Pagination } from "../../components/Pagination";
import type { Page } from "../../entities/types";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { RemoteSelect } from "../../components/RemoteSelect";
import { useAction } from "../../hooks/useAction";

interface Recipient {
  id: string;
  recipient_id: string;
  name: string;
  status: string;
  version_number: number;
  access_revoked: boolean;
}
type Recipients = Page<Recipient> & { selected_assigned: boolean };
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
  const [accessTarget, setAccessTarget] = useState<Recipient>();
  const [removing, setRemoving] = useState<Recipient>();
  const [student, setStudent] = useState("");
  const [group, setGroup] = useState("");
  const [assigned, setAssigned] = useState<Set<string>>(() => new Set());
  const [studentPage, setStudentPage] = useState(1);
  const [groupPage, setGroupPage] = useState(1);
  const students = useQuery({
    queryKey: ["course-recipients", id, "students", studentPage, student],
    queryFn: ({ signal }) =>
      api<Recipients>(
        `courses/${id}/recipients/?kind=students&page=${studentPage}&selected=${student}`,
        "GET",
        undefined,
        signal,
      ),
  });
  const groups = useQuery({
    queryKey: ["course-recipients", id, "groups", groupPage, group],
    queryFn: ({ signal }) =>
      api<Recipients>(
        `courses/${id}/recipients/?kind=groups&page=${groupPage}&selected=${group}`,
        "GET",
        undefined,
        signal,
      ),
  });
  const studentKey = `${id}:student:${student}`;
  const groupKey = `${id}:group:${group}`;
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
        disabled={
          !published ||
          !student ||
          action.pending ||
          assigned.has(studentKey) ||
          students.isPending ||
          !!students.error ||
          students.data?.selected_assigned
        }
        onClick={async () => {
          const result = await action.run(
            `courses/${id}/assign/`,
            { student },
            "POST",
            t("workspace.assigned"),
          );
          if (result.ok)
            setAssigned((previous) => new Set(previous).add(studentKey));
        }}
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
        disabled={
          !published ||
          !group ||
          action.pending ||
          assigned.has(groupKey) ||
          groups.isPending ||
          !!groups.error ||
          groups.data?.selected_assigned
        }
        onClick={async () => {
          const result = await action.run(
            `groups/${group}/assign/`,
            { course: id },
            "POST",
            t("workspace.groupAssigned"),
          );
          if (result.ok)
            setAssigned((previous) => new Set(previous).add(groupKey));
        }}
      >
        {t("assign")}
      </button>
      {published && !group && (
        <p className="field-hint">{t("learningDisplay.chooseRecipient")}</p>
      )}
      {action.feedback}
      {accessTarget && (
        <Modal
          title={t(
            accessTarget.access_revoked ? "restoreAccess" : "closeAccess",
          )}
          onClose={() => {
            if (!action.pending) setAccessTarget(undefined);
          }}
        >
          <p>
            <strong>{accessTarget.name}</strong>
          </p>
          <p>
            {t(
              accessTarget.access_revoked
                ? "restoreAccessHint"
                : "closeAccessHint",
            )}
          </p>
          {action.error != null && <ErrorState error={action.error} />}
          <div className="form-actions">
            <button
              disabled={action.pending}
              onClick={() => setAccessTarget(undefined)}
            >
              {t("cancel")}
            </button>
            <button
              className={accessTarget.access_revoked ? "primary" : "danger"}
              disabled={action.pending}
              onClick={async () => {
                const result = await action.run(
                  `enrollments/${accessTarget.id}/${accessTarget.access_revoked ? "restore-access" : "close-access"}/`,
                  {},
                );
                if (result.ok) setAccessTarget(undefined);
              }}
            >
              {t(accessTarget.access_revoked ? "restoreAccess" : "closeAccess")}
            </button>
          </div>
        </Modal>
      )}
      {removing && (
        <Modal
          title={t("unassignGroup")}
          onClose={() => {
            if (!action.pending) setRemoving(undefined);
          }}
        >
          <p>
            <strong>{removing.name}</strong>
          </p>
          <p>{t("unassignGroupHint")}</p>
          {action.error != null && <ErrorState error={action.error} />}
          <div className="form-actions">
            <button
              disabled={action.pending}
              onClick={() => setRemoving(undefined)}
            >
              {t("cancel")}
            </button>
            <button
              className="danger"
              disabled={action.pending}
              onClick={async () => {
                const result = await action.run(
                  `groups/${removing.recipient_id}/unassign-course/`,
                  { course: id },
                );
                if (result.ok) {
                  setAssigned((previous) => {
                    const next = new Set(previous);
                    next.delete(`${id}:group:${removing.recipient_id}`);
                    return next;
                  });
                  setGroupPage(1);
                  setRemoving(undefined);
                }
              }}
            >
              {t("unassignGroup")}
            </button>
          </div>
        </Modal>
      )}
      <div className="assigned-recipients">
        <h3>{t("assignedStudents")}</h3>
        {students.isPending ? (
          <Loading />
        ) : students.error ? (
          <ErrorState
            error={students.error}
            retry={() => void students.refetch()}
          />
        ) : (
          <>
            {!students.data?.count && (
              <p className="muted">{t("noAssignedStudents")}</p>
            )}
            {students.data?.results.map((row) => (
              <div className="record-row" key={row.id}>
                <div className="recipient-details">
                  <strong>{row.name}</strong>
                  <small>
                    {t(row.access_revoked ? "accessClosed" : row.status)} · v
                    {row.version_number}
                  </small>
                </div>
                <button
                  className={row.access_revoked ? "" : "danger-text"}
                  disabled={action.pending}
                  onClick={() => setAccessTarget(row)}
                >
                  {t(row.access_revoked ? "restoreAccess" : "closeAccess")}
                </button>
              </div>
            ))}
            <Pagination
              page={studentPage}
              count={students.data?.count || 0}
              onChange={setStudentPage}
            />
          </>
        )}
        <h3>{t("assignedGroups")}</h3>
        {groups.isPending ? (
          <Loading />
        ) : groups.error ? (
          <ErrorState
            error={groups.error}
            retry={() => void groups.refetch()}
          />
        ) : (
          <>
            {!groups.data?.count && (
              <p className="muted">{t("noAssignedGroups")}</p>
            )}
            {groups.data?.results.map((row) => (
              <div className="record-row" key={row.id}>
                <div className="recipient-details">
                  <strong>{row.name}</strong>
                  <small>
                    {t(row.status)} · v{row.version_number}
                  </small>
                </div>
                <button
                  className="danger-text"
                  disabled={action.pending}
                  onClick={() => setRemoving(row)}
                >
                  {t("unassignGroup")}
                </button>
              </div>
            ))}
            <Pagination
              page={groupPage}
              count={groups.data?.count || 0}
              onChange={setGroupPage}
            />
          </>
        )}
      </div>
    </section>
  );
}
