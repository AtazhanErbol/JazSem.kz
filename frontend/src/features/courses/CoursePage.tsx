import { lazy, Suspense } from "react";
import { useUser } from "../../app/Auth";
import { Loading } from "../../components/UI";
const Builder = lazy(() =>
  import("./CourseBuilder").then((module) => ({
    default: module.CourseBuilder,
  })),
);
const Player = lazy(() =>
  import("./CoursePlayer").then((module) => ({ default: module.CoursePlayer })),
);
export function CoursePage() {
  const user = useUser();
  return (
    <Suspense fallback={<Loading />}>
      {user.role === "STUDENT" ? <Player /> : <Builder />}
    </Suspense>
  );
}
