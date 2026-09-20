# Precision sample - measure references

Thirty references that resolved, drawn from the build, for checking by
hand. For each: does the cited provision in `raw_text` really correspond
to `citation_path`, and does the text quoted from the Act match it?

Resolution is mechanical, so what this checks is whether the grammar is
reading Finance's citation the way a person would - the one thing no
automated test in this project can tell us, because every one of them
reads the same grammar.

Seeded (`REFERENCE_SAMPLE_SEED` in `portage/measures_build.py`) and
**never overwritten by the build**.

| # | Measure | Lang | Citation | As published | Provision text | Result | Notes |
|---|---|---|---|---|---|---|---|
| 1 | Accelerated deductibility of Canadian Renewabl | en | `ITR 1219` | section 1219 |  |  |  |
| 2 | Logging Tax Credit | en | `ITA 127` | section 127 |  |  |  |
| 3 | Canada Training Credit | fr | `ITA 122.91` | article 122.91 |  |  |  |
| 4 | Labour Mobility Deduction for Tradespeople | en | `ITA 8(14)` | paragraph 8(1)(t) and subsection 8(14) | For the purposes of this subsection and paragraph (1)(t), |  |  |
| 5 | Non-taxation of capital gains on principal res | fr | `ITA 54` | alinéa 40(2)(b), définition de « résidence principale » à l'article 54 | In this Subdivision, |  |  |
| 6 | Tax treatment of active business income of for | fr | `ITA 94.2(2)` | articles 91 et 113 et paragraphes 20(1), 93.1(1), 94.2(2) et 95(1) | If this subsection applies at any time to a beneficiary under, or a pa |  |  |
| 7 | Employee benefit plans | en | `ITR 6801` | section 6801 | For the purposes of paragraph (l) of the definition salary deferral ar |  |  |
| 8 |  | fr | `ITR 6801` | article 6801 | For the purposes of paragraph (l) of the definition salary deferral ar |  |  |
| 9 | $200 capital gains exemption on foreign exchan | fr | `ITA 39(2)` | paragraphes 39(1.1) et 39(2) | If, because of any fluctuation after 1971 in the value of a currency o |  |  |
| 10 | Non-taxation of personal property of status In | fr | `ITA 81(1)(a)` | alinéa 81(1)(a) | an amount that is declared to be exempt from income tax by any other e |  |  |
| 11 | Accelerated capital cost allowance for vessels | en | `ITR 1100(1)(v)` | paragraph 1100(1)(v) | such amount as the taxpayer may claim in respect of property that is |  |  |
| 12 | Tax treatment of Canada Pension Plan and Quebe | fr | `ITA 56(1)(a)` | article 118.7 et alinéas 56(1)(a), 60(1)(e) et 60(1)(e.1) | any amount received by the taxpayer in the year as, on account or in l |  |  |
| 13 |  | fr | `ITA 6` | alinéas 149(1)(c) et d) à d.6) |  |  |  |
| 14 | Hardest-Hit Business Recovery Program | fr | `ITA 125.7` | articles 125.7 et 164 |  |  |  |
| 15 | Teacher and Early Childhood Educator School Su | fr | `ITA 122.9` | article 122.9 |  |  |  |
| 16 |  | fr | `ITA 4` | alinéas 81(1)(c.1) [-c.4)], paragraphe 81(6), et |  |  |  |
| 17 | Non-taxation of benefits from private health a | fr | `ITA 18` | sous-alinéa 6(1)(a)(i) et articles 18 et 20.01 |  |  |  |
| 18 |  | fr | `ITA 20(1)(c)` | alinéas 20(1)(c) et bb) | an amount paid in the year or payable in respect of the year (dependin |  |  |
| 19 |  | fr | `ITA 81(6)` | alinéas 81(1)(c.1) [-c.4)], paragraphe 81(6), et | If, at the end of a taxation year of a taxpayer, the taxpayer owns a v |  |  |
| 20 | Registered Education Savings Plans | fr | `ITA 146.1` | article 146.1 Loi canadienne sur l'épargne-études et Règlement sur l'é |  |  |  |
| 21 | Deferral of capital gains through intergenerat | fr | `ITA 73(4.1)` | paragraphes 70(9) à (9.31) et 73(3) à (4.1) | If, because of subsection (4), this subsection applies to the taxpayer |  |  |
| 22 | Tax treatment of Canada Pension Plan and Quebe | en | `ITA 118.7` | section 118.7 and paragraphs 56(1)(a), 60(1)(e) and (e.1) | For the purpose of computing the tax payable under this Part by an ind |  |  |
| 23 | Earned depletion | en | `ITR 1201` | section 1201 | In computing a taxpayer’s income for a taxation year there may be dedu |  |  |
| 24 | Tax treatment of active business income of for | en | `ITA 94.2(2)` | sections 91 and 113 and subsections 20(1), 93.1(1), 94.2(2) and 95(1) | If this subsection applies at any time to a beneficiary under, or a pa |  |  |
| 25 | Clean Technology Investment Tax Credit | en | `ITA 127.45` | section 127.45 |  |  |  |
| 26 | Canada Emergency Rent Subsidy and Lockdown Sup | fr | `ITA 164` | articles 125.7 et 164 |  |  |  |
| 27 | Immediate expensing for small businesses | en | `ITR 1100(0.1)` | section 1100 (0.1) to (0.3), subsection 1102(20.1), section 1104 (3.1) | For the purposes of paragraph 20(1)(a) of the Act, a deduction is allo |  |  |
| 28 | Preferential tax rate for small businesses | en | `ITA 125` | section 125 |  |  |  |
| 29 | Accelerated deductibility of Canadian Renewabl | fr | `ITA 66.1(6)` | paragraphe 66.1(6) | In this section, |  |  |
| 30 | Accelerated deductibility of some Canadian Exp | en | `ITA 66.1` | section 66.1 |  |  |  |

Source: Report on Federal Tax Expenditures 2026, retrieved 2026-09-19. Provision text from the Income Tax Act / Regulations, consolidation 2026-06-18.
