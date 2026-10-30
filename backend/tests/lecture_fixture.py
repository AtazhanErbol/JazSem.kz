"""Deterministic content ONLY for isolated unit/browser tests; never a production provider."""


def lecture_data():
    def paragraphs(count):
        return "\n\n".join(
            f"Synthetic example {i + 1}: explain each operation on both sides of an equation. "
            "Substitution checks whether the resulting value satisfies the original expression. "
            "Compare the intermediate values and state the assumptions explicitly."
            for i in range(count)
        )

    return {
        "title": "Синтетическая лекция · Ә Ғ Қ Ң Ө Ұ Ү Һ І",
        "objective": "Understand equivalent transformations and verify solutions by substitution.",
        "outcomes": ["Explain an equivalent transformation.", "Solve and check a linear equation."],
        "introduction": paragraphs(3),
        "terminology": paragraphs(3),
        "theory": paragraphs(25),
        "examples": "### Step-by-step example\n\n"
        + paragraphs(16)
        + "\n\n| Step | Value |\n| --- | --- |\n| 1 | $x=2$ |",
        "mistakes": paragraphs(4),
        "conclusions": paragraphs(3),
        "self_check": [
            "Why transform both sides?",
            "How do you verify a solution?",
            "When is division invalid?",
        ],
        "references": [],
        "source_gaps": ["Synthetic test fixture; not a factual lecture."],
    }
