from __future__ import annotations

import pytest

from math_aware_source_digest import compare


@pytest.mark.parametrize(
    "a, b, level",
    [
        # The look-alike swaps seen in the pilot papers.
        (r"\gamma_k", r"y_k", "strict"),
        (r"\tilde{\phi}(x)", r"\hat{\phi}(x)", "strict"),
        (r"\mathcal{W} \subset H", r"\mathcal{V} \subset H", "strict"),
        (r"\mathcal{W}", r"W", "style"),
        (r"\mathbf{x} = A u", r"x = A u", "style"),
        (r"\mathbb{R}^n", r"R^n", "style"),
        # Dropped terms and changed relations.
        (r"a + b + c", r"a + c", "strict"),
        (r"\|x\| = 1", r"\|x\| \le 1", "strict"),
        (r"x^{2}", r"x_{2}", "strict"),
        (r"u^*", r"u'", "strict"),
        # Differences that do not change the rendered symbols.
        (r"\boldsymbol{x}", r"\mathbf{x}", "same"),
        (r"\left( a \right)", r"(a)", "same"),
        (r"a \, b \quad c", r"a b c", "same"),
        (r"a \le b", r"a \leq b", "same"),
        (r"\Vert x \Vert", r"\| x \|", "same"),
        (r"\parallel y - Ax\|_2", r"\| y - Ax \|_2", "same"),
        (r"\lbrace a \rbrace", r"\{ a \}", "same"),
        (r"E = mc^2 .", r"E = mc^{2}", "same"),
        (r"\dfrac{a}{b}", r"\frac{a}{b}", "same"),
        # The same notation written another way (seen in Zach et al. 2023).
        (r"E \coloneqq D", r"E := D", "same"),
        (r"\mathbb{E}[x] \eqqcolon m", r"\mathbb{E}[x] =: m", "same"),
        (r"p(x^\prime \mid z)", r"p(x' \mid z)", "same"),
        (r"x^\prime_i", r"x_i'", "same"),
        (r"x''", r"x^{\prime\prime}", "same"),
        (r"Z^{-1}_\theta", r"Z_{\theta}^{-1}", "same"),
        (r"\mathbb{R}_{\geq 0}^n", r"\mathbb{R}^{n}_{\geq 0}", "same"),
        (r"A^\mathrm{T}_k", r"A_k^{\mathrm{T}}", "same"),
        (r"j \in \llbracket 1, J \rrbracket", r"j \in [\![ 1, J ]\!]", "same"),
        (
            r"\begin{Bmatrix} a \\ b \end{Bmatrix}",
            r"\left\{ \begin{matrix} a \\ b \end{matrix} \right\}",
            "same",
        ),
        (
            r"\begin{pmatrix} a & b \end{pmatrix}",
            r"\left( \begin{array}{cc} a & b \end{array} \right)",
            "same",
        ),
        (
            r"\begin{cases} 0 & x \in A \\ 1 \end{cases}",
            r"\left\{ \begin{matrix} 0 & x \in A \\ 1 \end{matrix} \right.",
            "same",
        ),
        (r"\left. \begin{aligned} r &= 1 \end{aligned} \right\}", r"r = 1 \}", "same"),
        (r"\begin{pmatrix} {a} \end{pmatrix}", r"(a)", "same"),
        (r"x'", r"x^*", "strict"),
        (r"\begin{bmatrix} a \end{bmatrix}", r"\begin{pmatrix} a \end{pmatrix}", "strict"),
        (r"\left. \begin{aligned} r &= 1 \end{aligned} \right\}", r"r = 1", "strict"),
        (r"x_i^2", r"x_2^i", "strict"),
        # Marker's output format: numbers, entities, environments, alignment.
        (r"f(u) = 1 . [1]", r"f(u) = 1", "same"),
        (r"f(u) = 1, \qquad (12)", r"f(u) = 1", "same"),
        (r"f(u) = 1 \tag{3a}", r"f(u) = 1", "same"),
        (r"f(u) = 1 . \quad [2]", r"f(u) = 1", "same"),
        (r"f(u) = 1 , [A1]", r"f(u) = 1", "same"),
        (r"f(u) = 1 \right], \quad [\text{A1}]", r"f(u) = 1 \right],", "same"),
        (r"\tau_i &gt; 0", r"\tau_i > 0", "same"),
        (
            r"\begin{aligned} a &= b \\ c &= d \end{aligned}",
            r"\begin{equation} a = b \quad c = d \end{equation}",
            "same",
        ),
        (r"x &amp;\leftarrow y", r"x \leftarrow y", "same"),
        # ...but a number that is part of the mathematics stays.
        (r"a_{[1]} + b", r"a + b", "strict"),
    ],
)
def test_levels(a: str, b: str, level: str) -> None:
    assert compare.compare(a, b).level == level
    assert compare.compare(b, a).level == level


def test_braces_are_not_style() -> None:
    assert compare.compare(r"\lbrace", r"{").level == "strict"
