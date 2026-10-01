import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import type { GroupDetails, GroupMember } from "../../entities/learning";
import { api } from "../../services/api";
import { Badge, Empty, ErrorState, Loading, Modal } from "../../components/UI";
import { RemoteSelect } from "../../components/RemoteSelect";
import { useAction } from "../../hooks/useAction";

export function GroupPage() {
  const { id } = useParams();
  const { t } = useTranslation();
  const action = useAction();
  const [removing, setRemoving] = useState<GroupMember>();
  const [student, setStudent] = useState("");
  const group = useQuery({
    queryKey: ["groups", id],
    queryFn: ({ signal }) =>
      api<GroupDetails>(`groups/${id}/`, "GET", undefined, signal),
  });
  const members = useQuery({
    queryKey: ["members", id],
    queryFn: ({ signal }) =>
      api<GroupMember[]>(`groups/${id}/members/`, "GET", undefined, signal),
  });
  if (group.isPending) return <Loading />;
  if (group.error)
    return (
      <ErrorState error={group.error} retry={() => void group.refetch()} />
    );
  return (
    <>
      <h1>{group.data.name}</h1>
      <Badge>{t(group.data.status)}</Badge>
      <h2>{t("members")}</h2>
      {members.isPending && <Loading />}
      {members.error && (
        <ErrorState
          error={members.error}
          retry={() => void members.refetch()}
        />
      )}
      {members.data?.length === 0 && <Empty />}
      {group.data.status === "ACTIVE" && (
        <section className="panel">
          <RemoteSelect
            label={t("student")}
            source={`users/?role=STUDENT&is_active=true&owner_teacher=${group.data.teacher}`}
            value={student}
            onChange={(value) => setStudent(String(value))}
          />
          <button
            className="primary contextual-action"
            disabled={
              !student ||
              action.pending ||
              members.isPending ||
              !!members.error ||
              members.data?.some((member) => member.student === student)
            }
            onClick={async () => {
              const result = await action.run(`groups/${id}/members/`, {
                student,
              });
              if (result.ok) setStudent("");
            }}
          >
            {t("addMember")}
          </button>
          {!student && (
            <p className="field-hint">{t("learningDisplay.chooseStudent")}</p>
          )}
        </section>
      )}
      {action.feedback}
      {removing && (
        <Modal
          title={t("removeMember")}
          onClose={() => {
            if (!action.pending) setRemoving(undefined);
          }}
        >
          <p>
            <strong>{removing.student_name}</strong>
          </p>
          <p>{t("removeMemberHint")}</p>
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
                const result = await action.run(`groups/${id}/remove-member/`, {
                  student: removing.student,
                });
                if (result.ok) setRemoving(undefined);
              }}
            >
              {t("removeMember")}
            </button>
          </div>
        </Modal>
      )}
      {members.data?.map((member) => (
        <div className="record-row" key={member.id}>
          <span>
            {member.student_name}
            <small>{member.student_email}</small>
          </span>
          {group.data.status === "ACTIVE" && (
            <button
              disabled={action.pending}
              onClick={() => setRemoving(member)}
            >
              {t("removeMember")}
            </button>
          )}
        </div>
      ))}
    </>
  );
}
