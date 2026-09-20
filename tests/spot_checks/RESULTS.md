# Spot check results

Hand verification of the build against the official Justice Laws site.

This is the only check in the project that does not compare the XML against itself.
Every automated guard - the round trip, the uniqueness test, the symmetric join -
reads the same four files the build reads. If those files were misread in the same
way twice, only a human looking at the published text would notice.

**Checked by Matt on 18 and 19 September 2026.** Transcribed from his worksheet
(`Portage spot checks.xlsx`, kept in this directory) exactly as recorded.

The citations below are the seeded samples as they stood when the checks were made.
Those four files are preserved as `verified_2026-09_*.md`. Sample generation has
since been changed to exclude unsearchable rows, so the current `spot_checks_*.md`
files draw a different sample.

A row that was skipped is recorded as **not checked**, with the reason. A skipped
row is never counted as a pass.

This file is **never overwritten by the build**.

---

## Income Tax Act - English

Sample: `verified_2026-09_ita_en.md`  
Official site: <https://laws-lois.justice.gc.ca/eng/acts/I-3.3/>  
Searched via: <https://laws-lois.justice.gc.ca/Search/Advanced.aspx>  
**Checked on:** 2026-09-18 and 2026-09-19  
**Result:** 10 confirmed, 1 not checked (skipped), 9 not checked

| # | Citation | Level | Result | Notes |
|---|---|---|---|---|
| 1 | `18(9.2)(b)(i)` | subparagraph | confirmed 2026-09-18 |  |
| 2 | `40(3.1)(a)6` | paragraph | not checked (string too short to search) |  |
| 3 | `60(l)(v)(D)(I)` | subclause | confirmed 2026-09-18 |  |
| 4 | `60.011(1)` | subsection | confirmed 2026-09-19 |  |
| 5 | `95(1)"designated acquired corporation"(b)` | paragraph | confirmed 2026-09-19 |  |
| 6 | `95(2.31)(c)(ii)(B)` | clause | confirmed 2026-09-19 |  |
| 7 | `107(4.1)(c)(ii)` | subparagraph | confirmed 2026-09-19 |  |
| 8 | `108(2)(b)(vi)` | subparagraph | confirmed 2026-09-19 |  |
| 9 | `122.1(1.3)(b)` | paragraph | confirmed 2026-09-19 |  |
| 10 | `144(11)` | subsection | confirmed 2026-09-19 |  |
| 11 | `146.01(1)"excluded withdrawal"(a)` | paragraph | confirmed 2026-09-19 |  |
| 12 | `146.1(7.1)(b)` | paragraph | not checked |  |
| 13 | `147.3(5)` | subsection | not checked |  |
| 14 | `183.3(5)(c)` | paragraph | not checked |  |
| 15 | `212(9)(c)` | paragraph | not checked |  |
| 16 | `219(1)(d)(i)` | subparagraph | not checked |  |
| 17 | `221.2(2)(b)` | paragraph | not checked |  |
| 18 | `247(5)` | subsection | not checked |  |
| 19 | `248(1)"qualified Canadian journalism organization"(a)(iii)(A)` | clause | not checked |  |
| 20 | `256.1(3)` | subsection | not checked |  |

---

## Income Tax Regulations - English

Sample: `verified_2026-09_itr_en.md`  
Official site: <https://laws-lois.justice.gc.ca/eng/regulations/C.R.C.,_c._945/>  
Searched via: <https://laws-lois.justice.gc.ca/Search/Advanced.aspx>  
**Checked on:** 2026-09-19  
**Result:** 10 confirmed, 2 not checked (skipped), 8 not checked

| # | Citation | Level | Result | Notes |
|---|---|---|---|---|
| 1 | `304(1)(a)` | paragraph | confirmed 2026-09-19 |  |
| 2 | `306(1)(b)(i)` | subparagraph | confirmed 2026-09-19 |  |
| 3 | `1100(1)(zc)(i)(H)` | clause | confirmed 2026-09-19 |  |
| 4 | `1100(14)` | subsection | confirmed 2026-09-19 |  |
| 5 | `1101(5e.1)(b)` | paragraph | confirmed 2026-09-19 |  |
| 6 | `1104(10)(b)(i)` | subparagraph | not checked (skipped) |  |
| 7 | `1104(13)"producer gas"(b)(iv)` | subparagraph | confirmed 2026-09-19 |  |
| 8 | `1206(1)"Canadian exploration and development overhead expense"(d)(v)` | subparagraph | confirmed 2026-09-19 |  |
| 9 | `1207(1)(b)` | paragraph | confirmed 2026-09-19 |  |
| 10 | `1900(1)"group term life insurance policy"(b)` | paragraph | confirmed 2026-09-19 |  |
| 11 | `2400(6)(b)` | paragraph | not checked (skipped) |  |
| 12 | `4900(1)(r)` | paragraph | confirmed 2026-09-19 |  |
| 13 | `5202"qualified activities"(a)` | paragraph | not checked |  |
| 14 | `5901(1)(a)(ii)(A)` | clause | not checked |  |
| 15 | `5905(5.1)(a)(v)` | subparagraph | not checked |  |
| 16 | `5907(1)"whole dividend"(b)` | paragraph | not checked |  |
| 17 | `5907(1.1)(a)(v)(C.1)(II)` | subclause | not checked |  |
| 18 | `5907(8)(b)` | paragraph | not checked |  |
| 19 | `7306(b)` | paragraph | not checked |  |
| 20 | `8901.1(1)(b)(i)` | subparagraph | not checked |  |

---

## Income Tax Act - French

Sample: `verified_2026-09_ita_fr.md`  
Official site: <https://laws-lois.justice.gc.ca/fra/lois/I-3.3/>  
Searched via: <https://laws-lois.justice.gc.ca/Recherche/Avancee.aspx>  
**Checked on:** 2026-09-19  
**Result:** 10 confirmed, 0 not checked (skipped), 10 not checked

| # | Citation | Level | Result | Notes |
|---|---|---|---|---|
| 1 | `18(17)"position"(a)(vii)` | subparagraph | confirmed 2026-09-19 |  |
| 2 | `41(2)(b)(ii)` | subparagraph | confirmed 2026-09-19 |  |
| 3 | `60.022(5)(d)` | paragraph | confirmed 2026-09-19 |  |
| 4 | `61(4)"income-averaging annuity contract"(a)(i)(B)` | clause | confirmed 2026-09-19 | shows as 61(4)(a)(i)(B) |
| 5 | `95(2)(f.11)(i)(B)` | clause | confirmed 2026-09-19 |  |
| 6 | `96(2.7)` | subsection | confirmed 2026-09-19 |  |
| 7 | `110(1.1)(d)` | paragraph | confirmed 2026-09-19 |  |
| 8 | `110.6(1)"qualified farm or fishing property"(a)(iv)` | subparagraph | confirmed 2026-09-19 |  |
| 9 | `122.92(1)"secondary unit"(a)` | paragraph | confirmed 2026-09-19 |  |
| 10 | `135.2(8)(c)(vii)` | subparagraph | confirmed 2026-09-19 |  |
| 11 | `146.1(2)(g.3)(i)(B)` | clause | not checked |  |
| 12 | `146.4(1.2)(d)` | paragraph | not checked |  |
| 13 | `147(5)(a)` | paragraph | not checked |  |
| 14 | `149.1(1)"relevant person"(b)(ii)` | subparagraph | not checked |  |
| 15 | `204.1(3)` | subsection | not checked |  |
| 16 | `222(6)(c)` | paragraph | not checked |  |
| 17 | `237.1(5)(c)(ii)` | subparagraph | not checked |  |
| 18 | `239(2.1)(c)` | paragraph | not checked |  |
| 19 | `248(25)(b)(iii)(A)(I)` | subclause | not checked |  |
| 20 | `252(2)(a)(ii)` | subparagraph | not checked |  |

---

## Income Tax Regulations - French

Sample: `verified_2026-09_itr_fr.md`  
Official site: <https://laws-lois.justice.gc.ca/fra/reglements/C.R.C.,_ch._945/>  
Searched via: <https://laws-lois.justice.gc.ca/Recherche/Avancee.aspx>  
**Checked on:** 2026-09-19  
**Result:** 10 confirmed, 4 not checked (skipped), 6 not checked

| # | Citation | Level | Result | Notes |
|---|---|---|---|---|
| 1 | `304(1)(a)` | paragraph | confirmed 2026-09-19 |  |
| 2 | `306(1)(b)(i)` | subparagraph | confirmed 2026-09-19 |  |
| 3 | `1100(1)(zc)(i)(H)` | clause | confirmed 2026-09-19 |  |
| 4 | `1100(14)` | subsection | confirmed 2026-09-19 |  |
| 5 | `1102(1)(j)` | paragraph | confirmed 2026-09-19 |  |
| 6 | `1104(17)` | subsection | confirmed 2026-09-19 |  |
| 7 | `1106(1.1)` | subsection | confirmed 2026-09-19 |  |
| 8 | `1206(1)"stated percentage"(a)(ii)` | subparagraph | confirmed 2026-09-19 | shows as: 1206(01)(a)(ii) |
| 9 | `1212(1)(b)(i)` | subparagraph | not checked (skipped) |  |
| 10 | `2000(2)(f)` | paragraph | not checked (skipped) |  |
| 11 | `2411(7)` | subsection | not checked (skipped) |  |
| 12 | `5002` | section | not checked (skipped) |  |
| 13 | `5204"cost of capital"(c)` | paragraph | confirmed 2026-09-19 |  |
| 14 | `5903(6)(d)` | paragraph | confirmed 2026-09-19 |  |
| 15 | `5906(3)(d)` | paragraph | not checked |  |
| 16 | `5907(1.1)(b)` | paragraph | not checked |  |
| 17 | `5907(2.01)` | subsection | not checked |  |
| 18 | `5911(3)(c)` | paragraph | not checked |  |
| 19 | `8300(1)` | subsection | not checked |  |
| 20 | `9002(3)(a)` | paragraph | not checked |  |

---

## Summary

| Instrument | Language | Checked on | Confirmed | Not checked (skipped) | Not checked |
|---|---|---|---|---|---|
| Income Tax Act | English | 2026-09-18 and 2026-09-19 | 10 | 1 | 9 |
| Income Tax Regulations | English | 2026-09-19 | 10 | 2 | 8 |
| Income Tax Act | French | 2026-09-19 | 10 | 0 | 10 |
| Income Tax Regulations | French | 2026-09-19 | 10 | 4 | 6 |
| **Total** | | | **40** | **7** | **33** |

**No mismatches.** Every citation that was checked showed the record's text on the
official site at the citation path the record claims.

---

## Notes followed up

Two rows were confirmed with a note about how the official site displays the
path. Both were investigated afterwards. Neither is a data defect.

**Income Tax Act, French, #4** - `61(4)"income-averaging annuity contract"(a)(i)(B)`,
recorded as *"shows as 61(4)(a)(i)(B)"*.

This is the definition-path convention, and it is expected. The official site
displays a provision that sits inside a definition by its label path alone.
Portage includes the defined term in quotation marks, because without it the
paths collide - 248(1)(a) would name 86 different provisions. The text matched;
only the way the path is written differs.

**Income Tax Regulations, French, #8** - `1206(1)"stated percentage"(a)(ii)`,
recorded as *"shows as: 1206(01)(a)(ii)"*.

Investigated on 19 September 2026. **No label was altered and nothing needs
cataloguing.**

- In the French Regulations XML, the definition *pourcentage indiqué* sits
  inside `<Subsection><Label>(1)</Label>`, and its paragraph a) subparagraph
  (ii) reads "50 pour cent dans le cas d'une dépense engagée après 1989 et avant
  1990," - which is exactly the text Portage stores.
- The complete set of subsection labels in section 1206 is
  `(1) (2) (3) (3.1) (4) (4.1) (4.2) (4.3) (5) (6) (7) (8) (8.1) (9)`. **No
  label in section 1206 contains a zero, in either language.**
- The official page was fetched and read directly. It renders the definition
  under subsection **(1)**. The only `01)` strings on that page are inside
  cross-references to `66(12.601)b)`.
- The stored row has `label_raw = '(1)'`, `label_raw_fr = '(1)'`,
  `label_anomaly_fr = 0`, `alignment = 'verified'`.

So the underlying finding is the same as #4 above - the site writes the path
without the defined term - and the `(01)` could not be reproduced. It is most
likely a slip while transcribing `(1)`. Recorded here rather than silently
dropped, because a note that was raised deserves an answer on the record.
