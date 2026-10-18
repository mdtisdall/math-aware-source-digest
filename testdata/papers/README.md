# Test papers

The PDFs of the test papers listed in [../papers.toml](../papers.toml), committed
so that the tests and the ground truth can be reproduced from this repository
alone, even if a source changes or disappears. Each file's SHA-256 is pinned in
`papers.toml` and checked by the tests; `masd testdata verify-remote` compares
the original sources with the same hashes.

Authors, journals, volumes and pages are from the Crossref records (and NTRS
for the NASA reports). Each paper is in the public domain or under a Creative Commons licence that
allows redistribution. The files are the publishers' or archives' files,
unchanged.

| file | paper | licence and source |
|---|---|---|
| `student-1908.pdf` | Student (1908). The probable error of a mean. *Biometrika* 6(1):1–25. doi:10.2307/2331554 | Public domain (published 1908). File from Zenodo record 1449458, released under CC0 1.0; the first page is a cover sheet added by JSTOR. |
| `hestenes-stiefel-1952.pdf` | M. R. Hestenes and E. Stiefel (1952). Methods of conjugate gradients for solving linear systems. *Journal of Research of the National Bureau of Standards* 49(6):409–436. doi:10.6028/jres.049.044 | Public domain: NIST states that papers of its Journal of Research are U.S. Government publications in the public domain. File from nvlpubs.nist.gov. |
| `zach-knoll-pock-2023.pdf` | M. Zach, F. Knoll and T. Pock (2023). Stable deep MRI reconstruction using generative priors. *IEEE Transactions on Medical Imaging* 42(12):3817–3832. doi:10.1109/TMI.2023.3311345 | © 2023 The Authors. Licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). File from ieeexplore.ieee.org. |
| `blumenthal-2026.pdf` | M. Blumenthal, T. Holliber, J. I. Tamir and M. Uecker (2026). Fast and robust diffusion posterior sampling for MR image reconstruction using the preconditioned unadjusted Langevin algorithm. *Magnetic Resonance in Medicine* 96(3):1323–1332. doi:10.1002/mrm.70416 | © 2026 The Author(s). Licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). File from onlinelibrary.wiley.com. |
| `harris-kleefeld-2019.pdf` | I. Harris and A. Kleefeld (2019). Analysis of new direct sampling indicators for far-field measurements. *Inverse Problems* 35(5):054002. doi:10.1088/1361-6420/ab08be | Original content licensed under CC BY 3.0 (https://creativecommons.org/licenses/by/3.0/); the article states that further distribution must keep the attribution to the authors, the title, the journal citation and the DOI, as given here. File from iopscience.iop.org. |
| `smith-schmidt-mcgee-1962.pdf` | G. L. Smith, S. F. Schmidt and L. A. McGee (1962). Application of statistical filter theory to the optimal estimation of position and velocity on board a circumlunar vehicle. NASA TR R-135. NTRS 19620006857 | Public domain: a NASA report by NASA Ames authors; NTRS marks it "public use permitted". File from ntrs.nasa.gov. |
| `blucker-1968.pdf` | T. J. Blucker, R. E. Eckelkamp and S. Pines (1968). Verification of the Kalman filter equations used in the LM AGS. NASA technical memorandum. NTRS 19700026383 | NTRS marks it "public use permitted"; a NASA Manned Spacecraft Center memorandum. File from ntrs.nasa.gov. |
| `lucka-2016.pdf` | F. Lucka (2016). Fast Gibbs sampling for high-dimensional Bayesian inversion. *Inverse Problems* 32(11):115019. doi:10.1088/0266-5611/32/11/115019 | Original content licensed under CC BY 3.0 (https://creativecommons.org/licenses/by/3.0/); attribution as above. File from iopscience.iop.org. |
| `hodge-1972.pdf` | D. B. Hodge (1972). The calculation of the eigenvalues and eigenfunctions of Mathieu's equation. NASA contractor report (Ohio State University). NTRS 19720007908 | NTRS marks it "public use permitted". File from ntrs.nasa.gov. |

`../sources/zach-knoll-pock-2023/arxiv-2210.13834/` holds `main.tex` and
`acronyms.tex` of arXiv:2210.13834 (Zach, Knoll and Pock), licensed under CC BY
4.0, unchanged; the figures of the arXiv source are left out.
