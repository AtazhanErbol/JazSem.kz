import { useTranslation } from "react-i18next";
import { useState } from "react";

interface Option {
  text: string;
  is_correct: boolean;
}
interface Question {
  text: string;
  type: "SINGLE_CHOICE" | "MULTIPLE_CHOICE";
  explanation: string;
  source_chunks: string[];
  options: Option[];
}
interface Assignment {
  title: string;
  instructions: string;
  source_chunks: string[];
}
interface Topic {
  title: string;
  content: string;
  source_chunks: string[];
  assignments: Assignment[];
  questions: Question[];
}
interface Week {
  title: string;
  topics: Topic[];
}
export interface DraftData {
  title: string;
  description: string;
  source_gaps: string[];
  weeks: Week[];
}

export function DraftEditor({
  data,
  onChange,
  onRegenerate,
  disabled,
}: {
  data: DraftData;
  onChange: (data: DraftData) => void;
  onRegenerate: (week: number, topic: number, instruction: string) => void;
  disabled: boolean;
}) {
  const { t } = useTranslation();
  const [instruction, setInstruction] = useState("");
  const update = (fn: (draft: DraftData) => void) => {
    const next = structuredClone(data);
    fn(next);
    onChange(next);
  };
  const chunks = data.weeks.flatMap((w) =>
    w.topics.flatMap((t) => t.source_chunks),
  );
  const topic = (): Topic => ({
    title: "",
    content: "",
    source_chunks: [...new Set(chunks)].slice(0, 5),
    assignments: [],
    questions: [],
  });
  const move = <T,>(items: T[], index: number, direction: number) => {
    const target = index + direction;
    if (target >= 0 && target < items.length)
      [items[index], items[target]] = [items[target], items[index]];
  };
  return (
    <fieldset disabled={disabled} className="draft-editor">
      <label>
        {t("title")}
        <input
          value={data.title}
          onChange={(e) =>
            update((d) => {
              d.title = e.target.value;
            })
          }
        />
      </label>
      <label>
        {t("description")}
        <textarea
          value={data.description}
          onChange={(e) =>
            update((d) => {
              d.description = e.target.value;
            })
          }
        />
      </label>
      {data.source_gaps.map((gap, i) => (
        <p className="notice" key={i}>
          {gap}
        </p>
      ))}
      {data.weeks.map((week, wi) => (
        <section className="draft-week" key={wi}>
          <label>
            {t("week")} {wi + 1}
            <input
              value={week.title}
              onChange={(e) =>
                update((d) => {
                  d.weeks[wi].title = e.target.value;
                })
              }
            />
          </label>
          <div className="mini-actions">
            <button
              type="button"
              onClick={() => update((d) => move(d.weeks, wi, -1))}
            >
              ↑ {t("up")}
            </button>
            <button
              type="button"
              onClick={() => update((d) => move(d.weeks, wi, 1))}
            >
              ↓ {t("down")}
            </button>
            <button
              type="button"
              onClick={() =>
                update((d) => {
                  d.weeks.splice(wi, 1);
                })
              }
            >
              {t("remove")}
            </button>
          </div>
          {week.topics.map((topic, ti) => (
            <details className="draft-topic" key={ti}>
              <summary>{topic.title || t("topic")}</summary>
              <label>
                {t("title")}
                <input
                  value={topic.title}
                  onChange={(e) =>
                    update((d) => {
                      d.weeks[wi].topics[ti].title = e.target.value;
                    })
                  }
                />
              </label>
              <label>
                {t("content")}
                <textarea
                  rows={9}
                  value={topic.content}
                  onChange={(e) =>
                    update((d) => {
                      d.weeks[wi].topics[ti].content = e.target.value;
                    })
                  }
                />
              </label>
              <div className="mini-actions">
                <button
                  type="button"
                  onClick={() =>
                    update((d) => move(d.weeks[wi].topics, ti, -1))
                  }
                >
                  ↑ {t("up")}
                </button>
                <button
                  type="button"
                  onClick={() => update((d) => move(d.weeks[wi].topics, ti, 1))}
                >
                  ↓ {t("down")}
                </button>
                <button
                  type="button"
                  onClick={() =>
                    update((d) => {
                      d.weeks[wi].topics.splice(ti, 1);
                    })
                  }
                >
                  {t("remove")}
                </button>
              </div>
              <h3>{t("assignments")}</h3>
              {topic.assignments.map((assignment, ai) => (
                <div className="panel" key={ai}>
                  <label>
                    {t("title")}
                    <input
                      value={assignment.title}
                      onChange={(e) =>
                        update((d) => {
                          d.weeks[wi].topics[ti].assignments[ai].title =
                            e.target.value;
                        })
                      }
                    />
                  </label>
                  <label>
                    {t("instructions")}
                    <textarea
                      value={assignment.instructions}
                      onChange={(e) =>
                        update((d) => {
                          d.weeks[wi].topics[ti].assignments[ai].instructions =
                            e.target.value;
                        })
                      }
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() =>
                      update((d) => {
                        d.weeks[wi].topics[ti].assignments.splice(ai, 1);
                      })
                    }
                  >
                    {t("remove")}
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() =>
                  update((d) => {
                    d.weeks[wi].topics[ti].assignments.push({
                      title: "",
                      instructions: "",
                      source_chunks: topic.source_chunks,
                    });
                  })
                }
              >
                + {t("addAssignment")}
              </button>
              <h3>{t("tests")}</h3>
              {topic.questions.map((question, qi) => (
                <div className="panel" key={qi}>
                  <label>
                    {t("text")}
                    <textarea
                      value={question.text}
                      onChange={(e) =>
                        update((d) => {
                          d.weeks[wi].topics[ti].questions[qi].text =
                            e.target.value;
                        })
                      }
                    />
                  </label>
                  <label>
                    {t("type")}
                    <select
                      value={question.type}
                      onChange={(e) =>
                        update((d) => {
                          d.weeks[wi].topics[ti].questions[qi].type = e.target
                            .value as Question["type"];
                        })
                      }
                    >
                      <option>SINGLE_CHOICE</option>
                      <option>MULTIPLE_CHOICE</option>
                    </select>
                  </label>
                  {question.options.map((option, oi) => (
                    <div className="draft-option" key={oi}>
                      <label>
                        {t("text")}
                        <input
                          value={option.text}
                          onChange={(e) =>
                            update((d) => {
                              d.weeks[wi].topics[ti].questions[qi].options[
                                oi
                              ].text = e.target.value;
                            })
                          }
                        />
                      </label>
                      <label className="check-label">
                        <input
                          type="checkbox"
                          checked={option.is_correct}
                          onChange={(e) =>
                            update((d) => {
                              d.weeks[wi].topics[ti].questions[qi].options[
                                oi
                              ].is_correct = e.target.checked;
                            })
                          }
                        />
                        {t("is_correct")}
                      </label>
                      <button
                        type="button"
                        onClick={() =>
                          update((d) => {
                            d.weeks[wi].topics[ti].questions[qi].options.splice(
                              oi,
                              1,
                            );
                          })
                        }
                      >
                        {t("remove")}
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={() =>
                      update((d) => {
                        d.weeks[wi].topics[ti].questions[qi].options.push({
                          text: "",
                          is_correct: false,
                        });
                      })
                    }
                  >
                    + {t("addOption")}
                  </button>
                  <label>
                    {t("explanation")}
                    <textarea
                      value={question.explanation}
                      onChange={(e) =>
                        update((d) => {
                          d.weeks[wi].topics[ti].questions[qi].explanation =
                            e.target.value;
                        })
                      }
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() =>
                      update((d) => {
                        d.weeks[wi].topics[ti].questions.splice(qi, 1);
                      })
                    }
                  >
                    {t("remove")}
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() =>
                  update((d) => {
                    d.weeks[wi].topics[ti].questions.push({
                      text: "",
                      type: "SINGLE_CHOICE",
                      explanation: "",
                      source_chunks: topic.source_chunks,
                      options: [
                        { text: "", is_correct: true },
                        { text: "", is_correct: false },
                      ],
                    });
                  })
                }
              >
                + {t("addQuestion")}
              </button>
              <label>
                {t("instructions")} · AI
                <textarea
                  value={instruction}
                  onChange={(e) => setInstruction(e.target.value)}
                />
              </label>
              <button
                type="button"
                disabled={!instruction.trim()}
                onClick={() => onRegenerate(wi, ti, instruction)}
              >
                ↻ {t("generate")}
              </button>
            </details>
          ))}
          <button
            type="button"
            onClick={() =>
              update((d) => {
                d.weeks[wi].topics.push(topic());
              })
            }
          >
            + {t("addTopic")}
          </button>
        </section>
      ))}
      <button
        type="button"
        onClick={() =>
          update((d) => {
            d.weeks.push({ title: "", topics: [topic()] });
          })
        }
      >
        + {t("addWeek")}
      </button>
    </fieldset>
  );
}
