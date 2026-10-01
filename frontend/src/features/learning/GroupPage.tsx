import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import type { GroupDetails, GroupMember } from "../../entities/learning";
import { api } from "../../services/api";
import { Badge, Empty, ErrorState, Loading } from "../../components/UI";
import { RemoteSelect } from "../../components/RemoteSelect";
import { useAction } from "../../hooks/useAction";

export function GroupPage() {
  const { id } = useParams();
  const { t } = useTranslation();
  const action = useAction();
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
      <Badge>{group.data.status}</Badge>
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
            className="primary"
            disabled={!student || action.pending}
            onClick={async () => {
              const result = await action.run(`groups/${id}/members/`, {
                student,
              });
              if (result.ok) setStudent("");
            }}
          >
            {t("addMember")}
          </button>
        </section>
      )}
      {action.feedback}
      {members.data?.map((member) => (
        <div className="record-row" key={member.id}>
          <span>
            {member.student_name}
            <small>{member.student_email}</small>
          </span>
          {group.data.status === "ACTIVE" && (
            <button
              disabled={action.pending}
              onClick={() =>
                void action.run(`groups/${id}/remove-member/`, {
                  student: member.student,
                })
              }
            >
              {t("removeMember")}
            </button>
          )}
        </div>
      ))}
    </>
  );
}
