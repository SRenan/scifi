# SCIFI: Science Finder

Utility that finds and downloads full pdfs for the selected IDs. Handles DOI, PMID, PMCID and converts between them as needed.

Browse the [documentation](./docs/index.html)

## Sources
- PubMed Open Access
- Unpaywall
- Sci-Hub

## TODO:
- Add sources:
  - Europe PMC
  - arXiv, ~~biorXiv, medrXiv~~
  - OpenAlex
- Rebuild doc on push with GitHub Actions

## Usage

```
scifi 10.1006/bbrc.2000.2954
scifi PMID:10720320
scifi PMC1234567
scifi 'https://pubmed.ncbi.nlm.nih.gov/10720320/'
```