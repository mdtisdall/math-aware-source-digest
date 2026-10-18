# Failure messages and what to do

| message | meaning | what to do |
|---|---|---|
| `needs approval: host ... is not in downloads.allowed_hosts` | the download policy does not cover the host | ask the user (file, source, size); do not fetch it another way |
| `no record matched the title (it may not exist)` | no bibliographic record matches | tell the user; ask for a DOI or the PDF; do not supply the citation yourself |
| `no Crossref or DataCite record for DOI ...` | the DOI is wrong or not registered | tell the user |
| `Unpaywall skipped: it needs network.contact_email` | open copies were not searched | optional: the user may set a contact email |
| `html-page`, `not-pdf`, `too-small`, `unreadable`, `encrypted` | the download is not a usable PDF | report the code; ask the user for the PDF |
| `title-not-found` | the PDF's first pages do not show the title | it may be another paper: report it, do not use it |
| `unsafe-archive` | an archive tried to write outside its directory | report it; do not extract it by other means |
| `math-as-images` | the XML has formulas only as images | the PDF route is needed |
| `Zotero's local API does not answer` | Zotero is closed or its local API is off | ask the user to start Zotero 7 and allow local access |
| `the local model server ... does not answer`, `... exited with code ...` | the local model server is down | report the log tail; do not substitute a cloud model |
| `model ... is refused: use an instruct model` | a thinking model was configured | use an instruct model |
| `entry not written` | the entry fails the schema or the span checks | report the errors; do not edit the JSON to force it through |
