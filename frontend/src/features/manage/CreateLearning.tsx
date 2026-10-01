import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useUser } from "../../app/Auth";
import { api } from "../../services/api";
import type { Row, Tree } from "../../entities/types";
import { ErrorState, Loading } from "../../components/UI";
import { RemoteSelect } from "../../components/RemoteSelect";
import { RecordForm } from "./RecordForm";

export function CourseCreate({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const user = useUser();
  const navigate = useNavigate();
  const [disciplineId, setDiscipline] = useState("");
  const [teacherId, setTeacher] = useState("");
  const discipline = useQuery({
    queryKey: ["disciplines", disciplineId],
    queryFn: ({ signal }) =>
      api<{ id: string; teachers: string[]; status: string }>(
        `disciplines/${disciplineId}/`,
        "GET",
        undefined,
        signal,
      ),
    enabled: !!disciplineId,
  });
  const responsible = user.role === "TEACHER" ? user.id : teacherId;
  const ready =
    discipline.data?.status === "ACTIVE" &&
    discipline.data.teachers.includes(responsible);
  return (
    <>
      <p className="muted">{t("workspace.courseIntro")}</p>
      <div className="record-form create-prerequisites">
        <h3>{t("discipline")}</h3>
        <RemoteSelect
          source="disciplines/?status=ACTIVE"
          label={t("discipline")}
          value={disciplineId}
          onChange={(value) => {
            setDiscipline(String(value));
            setTeacher("");
          }}
        />
        {user.role === "ADMIN" && (
          <Link
            className="button contextual-action"
            to="/app/disciplines?create=1"
          >
            {t("workspace.createDiscipline")}
          </Link>
        )}
        {disciplineId && discipline.isPending && <Loading />}
        {discipline.error && (
          <ErrorState
            error={discipline.error}
            retry={() => void discipline.refetch()}
          />
        )}
        {discipline.data && user.role === "ADMIN" && (
          <>
            <h3>{t("workspace.courseTeacher")}</h3>
            <RemoteSelect
              key={disciplineId}
              source={`users/?role=TEACHER&is_active=true&discipline=${disciplineId}`}
              label={t("workspace.courseTeacher")}
              value={responsible}
              onChange={(value) => setTeacher(String(value))}
            />
            <small className="muted">{t("workspace.courseTeacherHint")}</small>
          </>
        )}
        {discipline.data && !discipline.data.teachers.length && (
          <p className="notice">{t("workspace.noTeachers")}</p>
        )}
      </div>
      {ready && (
        <RecordForm
          resource="courses"
          fixed={{ discipline: disciplineId, teacher: responsible }}
          submitLabel={t("workspace.createAndOpen")}
          onDone={(row) =>
            row ? navigate(`/app/courses/${row.id}`) : onClose()
          }
        />
      )}
    </>
  );
}

export function ActivityCreate({
  resource,
  onClose,
}: {
  resource: "assignments" | "tests";
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [course, setCourse] = useState("");
  return (
    <>
      <p className="muted">{t("workspace.activityIntro")}</p>
      <h3>{t("workspace.locationStep")}</h3>
      <RemoteSelect
        source="courses/?active=true"
        label={t("workspace.chooseCourse")}
        value={course}
        onChange={(value) => setCourse(String(value))}
      />
      <Link className="button contextual-action" to="/app/courses?create=1">
        {t("createCourse")}
      </Link>
      {course && (
        <ActivityLocation
          key={course}
          course={course}
          resource={resource}
          onClose={onClose}
        />
      )}
    </>
  );
}

function ActivityLocation({
  course,
  resource,
  onClose,
}: {
  course: string;
  resource: "assignments" | "tests";
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [topic, setTopic] = useState("");
  const [week, setWeek] = useState("");
  const [step, setStep] = useState(1);
  const [structure, setStructure] = useState<"weeks" | "topics">();
  const versions = useQuery({
    queryKey: ["versions", course],
    queryFn: () => api<Row[]>(`courses/${course}/versions/`),
  });
  const draft = versions.data
    ?.filter((v) => ["DRAFT", "REVIEW"].includes(String(v.status)))
    .sort((a, b) => Number(b.version_number) - Number(a.version_number))[0];
  const tree = useQuery({
    queryKey: ["tree", course, draft?.id],
    queryFn: () => api<Tree>(`courses/${course}/tree/?version=${draft!.id}`),
    enabled: !!draft,
  });
  if (versions.isPending || (draft && tree.isPending)) return <Loading />;
  if (versions.error || tree.error)
    return <ErrorState error={versions.error || tree.error} />;
  if (!draft)
    return (
      <div className="workspace-empty">
        <h3>{t("workspace.draftNeeded")}</h3>
        <p>{t("workspace.draftNeededHint")}</p>
        <Link className="button" to={`/app/courses/${course}`}>
          {t("workspace.openBuilder")}
        </Link>
      </div>
    );
  if (!tree.data) return null;
  const data = tree.data;
  const topics = data.weeks.flatMap((w) => w.topics);
  const selectedTopic = topics.find((item) => item.id === topic);
  const weekId = week || data.weeks[0]?.id;
  if (step === 2 && selectedTopic)
    return (
      <section className="activity-step">
        <button className="quiet" onClick={() => setStep(1)}>
          ← {t("workspace.backLocation")}
        </button>
        <h3>{t("workspace.contentStep")}</h3>
        <p className="location-label">
          {String(data.course.title)} / {selectedTopic.title}
        </p>
        <p className="muted">
          {t(
            resource === "tests"
              ? "workspace.testNext"
              : "workspace.assignmentNext",
          )}
        </p>
        <RecordForm
          resource={resource}
          fixed={{ topic }}
          submitLabel={t(
            resource === "tests"
              ? "workspace.createTest"
              : "workspace.createAssignment",
          )}
          onDone={(row) =>
            row
              ? navigate(
                  `/app/courses/${course}?version=${draft.id}&activity=${row.id}`,
                )
              : onClose()
          }
        />
      </section>
    );
  return (
    <section className="activity-step">
      {topics.length > 0 && (
        <label>
          {t("workspace.chooseTopic")}
          <select
            aria-label={t("workspace.chooseTopic")}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          >
            <option value="">—</option>
            {data.weeks.map((w) => (
              <optgroup key={w.id} label={`${w.number}. ${w.title}`}>
                {w.topics.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
      )}
      {!topics.length && (
        <p className="notice">
          {t(
            data.weeks.length
              ? "workspace.topicNeeded"
              : "workspace.weekNeeded",
          )}
        </p>
      )}
      {structure ? (
        <div className="inline-creator">
          <h3>{t(structure === "weeks" ? "addWeek" : "addTopic")}</h3>
          {structure === "topics" && (
            <label>
              {t("week")}
              <select
                aria-label={t("week")}
                value={weekId}
                onChange={(e) => setWeek(e.target.value)}
              >
                {data.weeks.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.number}. {w.title}
                  </option>
                ))}
              </select>
            </label>
          )}
          <RecordForm
            key={`${structure}-${weekId}`}
            resource={structure}
            fixed={
              structure === "weeks"
                ? { course_version: draft.id }
                : { week: weekId }
            }
            defaults={{
              number: Math.max(0, ...data.weeks.map((w) => w.number)) + 1,
            }}
            onDone={(row) => {
              if (row && structure === "topics") setTopic(row.id);
              if (row && structure === "weeks") setWeek(row.id);
              setStructure(undefined);
            }}
          />
        </div>
      ) : (
        <div className="row-actions structure-actions">
          <button onClick={() => setStructure("weeks")}>
            + {t("addWeek")}
          </button>
          {data.weeks.length > 0 && (
            <button onClick={() => setStructure("topics")}>
              + {t("addTopic")}
            </button>
          )}
        </div>
      )}
      <div className="form-actions">
        <button onClick={onClose}>{t("cancel")}</button>
        <button
          className="primary"
          disabled={!selectedTopic || !!structure}
          onClick={() => setStep(2)}
        >
          {t("workspace.next")}
        </button>
      </div>
    </section>
  );
}
