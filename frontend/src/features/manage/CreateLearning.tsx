import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useUser } from "../../app/Auth";
import { allRows, api } from "../../services/api";
import type { Row, Tree } from "../../entities/types";
import { ErrorState, Loading } from "../../components/UI";
import { RecordForm } from "./RecordForm";

export function CourseCreate({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const user = useUser();
  const navigate = useNavigate();
  const [disciplineId, setDiscipline] = useState("");
  const [teacherId, setTeacher] = useState("");
  const disciplines = useQuery({
    queryKey: ["options", "active-disciplines"],
    queryFn: async () =>
      (await allRows("disciplines/")).filter(
        (discipline) => discipline.status === "ACTIVE",
      ),
  });
  const teachers = useQuery({
    queryKey: ["course-teachers", user.id],
    queryFn: () =>
      user.role === "TEACHER"
        ? Promise.resolve<Row[]>([{ ...user }])
        : allRows("users/?role=TEACHER"),
  });
  if (disciplines.isPending || teachers.isPending) return <Loading />;
  if (disciplines.error || teachers.error)
    return <ErrorState error={disciplines.error || teachers.error} />;
  const discipline = disciplines.data.find((d) => d.id === disciplineId);
  const eligible = teachers.data.filter(
    (person) =>
      Array.isArray(discipline?.teachers) &&
      discipline.teachers.includes(person.id),
  );
  const responsible =
    user.role === "TEACHER"
      ? user.id
      : teacherId || (eligible.length === 1 ? eligible[0].id : "");
  const ready =
    !!discipline && eligible.some((person) => person.id === responsible);
  return (
    <>
      <p className="muted">{t("workspace.courseIntro")}</p>
      {!disciplines.data.length ? (
        <div className="workspace-empty">
          <h3>{t("workspace.noDisciplines")}</h3>
          <p>{t("workspace.noDisciplinesHint")}</p>
          {user.role === "ADMIN" && (
            <Link className="button primary" to="/app/disciplines?create=1">
              {t("workspace.createDiscipline")}
            </Link>
          )}
        </div>
      ) : (
        <div className="record-form create-prerequisites">
          <label>
            {t("discipline")}
            <select
              aria-label={t("discipline")}
              value={disciplineId}
              onChange={(e) => {
                setDiscipline(e.target.value);
                setTeacher("");
              }}
            >
              <option value="">{t("workspace.chooseDiscipline")}</option>
              {disciplines.data.map((d) => (
                <option key={d.id} value={d.id}>
                  {String(d.name)}
                </option>
              ))}
            </select>
          </label>
          {user.role === "ADMIN" && (
            <label>
              {t("workspace.courseTeacher")}
              <select
                aria-label={t("workspace.courseTeacher")}
                value={responsible}
                disabled={!discipline}
                onChange={(e) => setTeacher(e.target.value)}
              >
                <option value="">{t("workspace.chooseTeacher")}</option>
                {eligible.map((person) => (
                  <option key={person.id} value={person.id}>
                    {String(person.first_name)} {String(person.last_name)} ·{" "}
                    {String(person.email)}
                  </option>
                ))}
              </select>
              <small className="muted">
                {t("workspace.courseTeacherHint")}
              </small>
            </label>
          )}
          {discipline && !eligible.length && (
            <p className="notice">
              {t("workspace.noTeachers")}{" "}
              {user.role === "ADMIN" && (
                <Link to="/app/disciplines">
                  {t("workspace.openDisciplines")}
                </Link>
              )}
            </p>
          )}
        </div>
      )}
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
  const courses = useQuery({
    queryKey: ["options", "active-courses"],
    queryFn: async () =>
      (await allRows("courses/")).filter(
        (course) => course.status !== "ARCHIVED",
      ),
  });
  return (
    <>
      <p className="muted">{t("workspace.activityIntro")}</p>
      {courses.isPending ? (
        <Loading />
      ) : courses.error ? (
        <ErrorState error={courses.error} />
      ) : !courses.data.length ? (
        <div className="workspace-empty">
          <h3>{t("workspace.noCourses")}</h3>
          <p>{t("workspace.noCoursesHint")}</p>
          <Link className="button primary" to="/app/courses?create=1">
            {t("createCourse")}
          </Link>
        </div>
      ) : (
        <>
          <h3>{t("workspace.locationStep")}</h3>
          <label>
            {t("workspace.chooseCourse")}
            <select
              aria-label={t("workspace.chooseCourse")}
              value={course}
              onChange={(e) => setCourse(e.target.value)}
            >
              <option value="">—</option>
              {courses.data.map((c) => (
                <option value={c.id} key={c.id}>
                  {String(c.title)}
                </option>
              ))}
            </select>
          </label>
          {course && (
            <ActivityLocation
              key={course}
              course={course}
              resource={resource}
              onClose={onClose}
            />
          )}
        </>
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
