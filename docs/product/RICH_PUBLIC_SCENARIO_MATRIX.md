# Rich public scenario matrix

The default POC experience uses real public companies and authoritative public
sources. It does not infer a BTX commercial relationship from those sources.

| Company | Industry | Public event/source | POC teaching scenario |
| --- | --- | --- | --- |
| Boeing | Commercial Aerospace / Defense | FAA production oversight update | Ideal strategic target |
| GE Aerospace | Commercial Aerospace / Defense | NASA propulsion contracts | Strong cold prospect |
| Lockheed Martin | Defense / Space | NASA CLPS | Cross-BU coordination |
| Northrop Grumman | Defense / Space | NASA VADR | Strong public program context |
| Anduril Industries | Defense (robotics secondary) | DoD microelectronics remarks | Visible company, poor fit hypothesis |
| Blue Origin | Space | NASA VADR | Strong cold prospect |
| Rocket Lab USA | Space | NASA VADR | Needs research / low coverage |
| Intel | Semiconductor | Commerce CHIPS award | Ideal strategic target |
| TSMC Arizona | Semiconductor | Commerce CHIPS award | Strong cold prospect |
| Applied Materials | Semiconductor | Commerce equipment announcement | Warm simulated context, declining outlook |
| Medtronic | Medical | SEC annual report | Needs research / low coverage |
| Symbotic | Unclassified (robotics secondary) | SEC annual report | Explicit scoring exclusion |

## Official source-validation record

The POC preserves the cited official URL even when publisher controls prevent an
automated check. The state is also returned as `source_validation_state` on the
Intelligence API so the product never describes an automation-blocked source as
browser-verified. Reviewed 2026-08-16 using a normal browser without credentials
or access-control bypasses.

| Company | Original official source | Source type | Final state | Review note |
| --- | --- | --- | --- | --- |
| Anduril Industries | https://www.defense.gov/News/Speeches/Speech/Article/3948717/remarks-by-deputy-secretary-of-defense-kathleen-hicks-at-the-2024-microelectr/ | DoD speech | `BROWSER_VERIFIED` | Opens through the agency’s official current-domain redirect; supports the Microelectronics Commons remarks dated 2024-10-29. |
| Intel | https://www.commerce.gov/news/press-releases/2024/11/biden-harris-administration-announces-chips-incentives-award-intel | Commerce press release | `AUTOMATION_BLOCKED` | The normal browser reached the publisher’s Cloudflare “Just a moment” control. The original official URL remains evidence; it is not called broken or browser-verified. |
| TSMC Arizona | https://www.commerce.gov/news/press-releases/2024/11/biden-harris-administration-announces-chips-incentives-award-tsmc | Commerce press release | `BROWSER_VERIFIED` | Opens normally and supports the CHIPS award dated 2024-11-15. |
| Applied Materials | https://www.commerce.gov/node/7087 | Commerce press release | `BROWSER_VERIFIED` | Opens normally and names Applied Materials in the advanced-packaging award announcement dated 2025-01-16. |
| Medtronic | https://www.sec.gov/Archives/edgar/data/1613103/000161310325000091/mdt-20250425.htm | SEC Form 10-K | `BROWSER_VERIFIED` | Opens normally and identifies Medtronic’s fiscal year ended 2025-04-25. |
| Symbotic | https://www.sec.gov/Archives/edgar/data/1837240/000183724025000278/sym-20250927.htm | SEC Form 10-K | `BROWSER_VERIFIED` | Opens normally and identifies Symbotic’s fiscal year ended 2025-09-27. |

No source was replaced in this review. The original DoD URL is retained in
provenance even though it redirects to the agency’s current official domain.

## Field rules

**Publicly verified** fields are company identity, domain, industry, facility,
official/public event, source URL, and legitimate public professional contact.
They carry research provenance and never establish a BTX customer, prospect,
quote, CRM, owner, deal, or revenue relationship.

**Simulated BTX context** consists of score selections, revenue/bookings,
quotes, CRM, ownership, workflow, matching, and action state. Score coverage
is therefore a POC teaching signal, not a commercial fact. A score below 50%
coverage is presented as **Needs research**, and explicit exclusions are not
scored.

**Needs research** means a real identity exists but public evidence is not
sufficient for a strong recommendation. **Unavailable** means the POC lacks an
approved fact. The POC contains no generated placeholder companies or synthetic
public locations.
