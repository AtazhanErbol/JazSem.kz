from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OptionDraft(StrictModel):
    text: str = Field(min_length=1, max_length=4000)
    is_correct: bool


class QuestionDraft(StrictModel):
    text: str = Field(min_length=1, max_length=8000)
    type: Literal["SINGLE_CHOICE", "MULTIPLE_CHOICE"]
    explanation: str
    source_chunks: list[str] = Field(min_length=1, max_length=20)
    options: list[OptionDraft] = Field(min_length=2, max_length=8)

    @model_validator(mode="after")
    def correct_answers(self):
        count = sum(o.is_correct for o in self.options)
        if not count or (self.type == "SINGLE_CHOICE" and count != 1):
            raise ValueError("Invalid correct answer count")
        return self


class AssignmentDraft(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    instructions: str = Field(min_length=1, max_length=20000)
    source_chunks: list[str] = Field(min_length=1, max_length=20)


class TopicDraft(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=30000)
    source_chunks: list[str] = Field(min_length=1, max_length=20)
    assignments: list[AssignmentDraft] = Field(max_length=5)
    questions: list[QuestionDraft] = Field(max_length=20)


class WeekDraft(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    topics: list[TopicDraft] = Field(min_length=1, max_length=10)


class CourseDraft(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(max_length=20000)
    source_gaps: list[str]
    weeks: list[WeekDraft] = Field(min_length=1, max_length=16)


def validate_citations(draft, allowed):
    for week in draft.weeks:
        for topic in week.topics:
            for item in [topic, *topic.assignments, *topic.questions]:
                if not set(item.source_chunks) <= allowed:
                    raise ValueError("Draft cites sources outside this course")
