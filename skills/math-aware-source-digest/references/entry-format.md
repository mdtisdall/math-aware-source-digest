# The entry and its configuration

An entry is a JSON file, `<output dir>/<key>.json`, checked against the
package's schema (`masd validate`). The Markdown file `<key>.md` is rendered
from it (`masd render`) and is never edited by hand.

- **Key:** the surname of the first author, or of both authors when there
  are two, then the year: `student-1908`, `hestenes-stiefel-1952`; `a`, `b`
  on a collision.
- **Fields:** citation (each field with its source and status), version,
  licence, summary, results (with the assumptions the source states, and
  their locations), notation (by span), cited spans, coverage (what the
  entry leaves out) and the verification record.
- **Spans:** text refers to a span as `{{s:<id>}}`; the renderer inserts the
  span's LaTeX. Each span's LaTeX also appears verbatim in a code block.

Configuration, in the project's `masd.toml`:

```toml
[output]
dir = "sources"
index = "README.md"
# template = "templates/source.md.j2"
# sections = ["citation", "summary", "results", "notation", "spans", "coverage"]
# headings = { coverage = "Omitted" }

[downloads]
allowed_hosts = []   # empty: every download asks
```
