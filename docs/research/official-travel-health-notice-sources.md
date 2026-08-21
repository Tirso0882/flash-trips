# Official travel-health notice sources

Date reviewed: 2026-08-21  
Originating issue: GitHub issue #29, “Research official travel-health notice sources”  
Decision supported: GitHub issue #5, “Choose the initial provider portfolio and adapter obligations”; this note does not select a provider

## Scope and method

This note asks which official sources are currently viable for non-personalised destination health notices in Travel Readiness. It uses only provider-, government-, or intergovernmental-owned documentation, interfaces, publications, terms, and licensing pages. Every source link below was accessed on 2026-08-21.

“Verified” means the adjacent primary source establishes the claim. “Unknown” means the reviewed public material did not establish it; absence from the reviewed documentation is not proof that a feature or right does not exist. No account was created, no paid interface was accessed, and no source response was retained as a fixture.

The relevant product boundary is narrower than “travel health”:

- Travel Readiness may report a destination-scoped outbreak or health risk, its affected area, the issuing authority, the authority’s stated notice level or general precautions, the publication/observation time, and an explicit limitation.
- It must not determine whether a particular Planner or Companion should receive a vaccine, drug, exemption, diagnosis, or treatment. Those answers depend on medical history, age, pregnancy, immune status, itinerary details, or clinician judgement and are personalised medical advice.
- Entry vaccination certificates, quarantine, testing, visa, and border rules are immigration or legal requirements. A source may contain them, but they cannot be normalised into the health-notice part of Travel Readiness.
- Runtime search may discover an official URL only as a Provider Observation. It cannot convert an arbitrary page into Evidence until an Operator has approved a versioned source-registry entry that validates the authority and audience, allowed domains and routes, extraction contract, destination mapping, freshness and correction rules, attribution and retention rights, and scope exclusions.

## Findings in brief

- **Global outbreak baseline:** WHO Disease Outbreak News (DON) has the clearest official structured interface and global remit. It is non-exhaustive, event-oriented rather than destination-complete, and its public reuse/retention rights need written confirmation for a commercial product.
- **Regional context:** ECDC CDTR and PAHO epidemiological alerts add Europe- and Americas-relevant threat intelligence. ECDC has comparatively clear CC BY 4.0 reuse, but CDTR is professional weekly reporting rather than a destination notice API. PAHO is mainly PDF/HTML and its standard publication licence is non-commercial.
- **Traveller-authority sources:** CDC Travelers’ Health and TravelHealthPro are directly traveller-facing. CDC offers a notice RSS feed and relatively clear federal reuse rules; TravelHealthPro offers a paid API but requires commercial and retention terms to be obtained before onboarding.
- **Demand-driven national authorities:** Poland and Colombia both publish official traveller-health material, but the reviewed public paths are mostly HTML/PDF, combine multiple audiences, and do not expose a documented travel-notice API or complete correction history. They need source-specific extraction validation and rights review before use as normalised Evidence.
- **Structured authority alternative:** Canada demonstrates a stronger onboarding shape: a dedicated travel-health RSS feed, country-advice JSON exports, and an explicit Open Government Licence. Its mixed country-advice payload still requires health-only extraction because it also contains security, entry/exit, law, and consular material.
- No source can safely stand in for an unsupported selected Advisory Authority. WHO, ECDC, PAHO, CDC, or another government’s advice may be useful global/regional context, but it is not equivalent to the selected Planner/Companion authority.

## Global baseline sources

### WHO Disease Outbreak News

**Role, audience, and coverage — verified**

WHO describes DONs as authoritative, independent information on confirmed or potential acute public-health events across all hazards. Publication criteria include unknown causes of potential international concern, known causes capable of serious international impact, and high-public-concern events that may disrupt travel or trade. WHO expressly says the set is not exhaustive of events to which it is responding ([WHO DON index](https://www.who.int/emergencies/disease-outbreak-news), accessed 2026-08-21).

This makes DON a **global baseline** for significant outbreak events, not a country-by-country traveller authority and not a guarantee that absence of a DON means absence of health risk.

**Access and deterministic extraction — verified**

WHO documents a REST endpoint at `GET /api/news/diseaseoutbreaknews`, item lookup by key, and related resources. The documented entity includes `Id`, `LastModified`, `PublicationDate`, `DateCreated`, `ItemDefaultUrl`, `Summary`, and `PublicationDateAndTime` ([WHO DON REST reference](https://www.who.int/api/news/diseaseoutbreaknews/sfhelp), accessed 2026-08-21). Canonical human-readable DON pages use stable identifiers such as `2026-DON600` and include a citable reference ([example DON update](https://www.who.int/emergencies/disease-outbreak-news/item/2026-DON600), accessed 2026-08-21).

The API schema and stable item URL make hand-authored, schema-pinned offline fixtures practical. A fixture should include the minimum fields required by the adapter and synthetic content rather than a copied production payload until retention rights are confirmed.

**Freshness and corrections — verified**

The API exposes publication and last-modified timestamps. DON updates may be new records that cite an earlier DON, while corrections can also modify a page in place with explicit `Corrigendum` or `Erratum` text ([updated DON linking its predecessor](https://www.who.int/emergencies/disease-outbreak-news/item/2026-DON600), [DON with dated corrigenda](https://www.who.int/emergencies/disease-outbreak-news/item/2026-DON603), and [DON with an erratum](https://www.who.int/emergencies/disease-outbreak-news/item/2026-DON594), all accessed 2026-08-21).

An adapter therefore needs both stable-ID deduplication and content/version fingerprinting. `LastModified` cannot by itself explain what changed; correction text and predecessor links need explicit parsing or conservative revalidation.

**Rights, limits, and availability — verified and unknown**

WHO’s general publication policy places post-2016 WHO publications under CC BY-NC-SA 3.0 IGO for non-commercial use and requires permission for commercial uses and electronic database products; third-party material is excluded ([WHO copyright](https://www.who.int/about/policies/publishing/copyright) and [permissions form](https://www.who.int/about/policies/publishing/permissions), accessed 2026-08-21). The separate `data.who.int` dataset terms generally use CC BY 4.0 but apply to datasets offered under those terms; the reviewed DON API page does not identify DON as one of those datasets ([WHO dataset terms](https://data.who.int/about/data/terms-and-conditions), accessed 2026-08-21).

Therefore commercial reproduction, payload caching, immutable retention, and fixture redistribution for DON are **unknown pending written WHO confirmation**. The public REST reference does not publish a numeric rate limit, quota, authentication requirement, uptime commitment, or deprecation policy. A spot request to the public collection endpoint returned `Cache-Control: public, s-maxage=900` but no `ETag` or HTTP `Last-Modified` validator; this is an observation, not a published contract, and must be revalidated during adapter onboarding ([WHO DON collection endpoint](https://www.who.int/api/news/diseaseoutbreaknews), accessed 2026-08-21).

**Travel Readiness boundary**

Safe content includes the event, affected geography, reported status, WHO risk assessment, publication time, general public-health precautions, and WHO’s travel/trade recommendation. Individual vaccine choice, prophylaxis, symptom interpretation, or treatment is medical advice and must be replaced with a clinician referral. A WHO discussion of travel restrictions or entry vaccination certificates must remain a cited limitation or be routed outside Travel Readiness, not converted into immigration/legal advice.

**Viability**

Viable as a global event baseline after rights confirmation and adapter validation. It cannot provide destination completeness or selected-authority equivalence.

### WHO International Travel and Health material

**Role and coverage — verified**

WHO’s International Travel and Health collection is primarily for travel-health practitioners and health professionals, with secondary relevance to health authorities, travellers, and the travel industry. Its vaccine module covers disease distribution, traveller risk, general precautions, and vaccines for which WHO has position statements ([WHO ITH module 4](https://www.who.int/publications/i/item/9789240113350), accessed 2026-08-21). The Travel Advice hub links infectious-disease risks, vaccination requirements, and travel-health publications ([WHO Travel Advice](https://www.who.int/travel-advice), accessed 2026-08-21).

This is a **global reference baseline**, not a continuously complete outbreak-notice feed.

**Access, freshness, and rights — verified**

The reviewed material is HTML and downloadable publication/PDF content rather than a dedicated destination-notice API. WHO warns that country requirements can change at any time and should be checked with the relevant consulate or embassy; the country-list publication records consultation with States Parties but is a dated edition ([WHO country-list PDF](https://cdn.who.int/media/docs/default-source/travel-and-health/vaccination-requirements-and-who-recommendations-ith-2022-country-list.pdf), accessed 2026-08-21). The publication reuse constraints are the WHO CC BY-NC-SA/commercial-permission terms described above ([WHO copyright](https://www.who.int/about/policies/publishing/copyright), accessed 2026-08-21).

No public rate limit, SLA, conditional-retrieval contract, or machine-readable correction/version feed was found in the reviewed official material. PDF-version checksums and hand-authored extraction fixtures are practical, but production text retention is permission-gated for commercial use.

**Travel Readiness boundary and viability**

Generic destination disease distribution and non-personalised precautions can support Travel Readiness. Recommendations based on traveller health profile, itinerary, age, pregnancy, immune status, or drug choice are personalised medical advice. Vaccination proof and entry/exit requirements are immigration/legal content. The material is viable as a curated background reference, not as the initial current-notice transport.

## Regional sources

### ECDC Communicable Disease Threats Report and surveillance data

**Role, audience, and coverage — verified**

ECDC describes the CDTR as a weekly summary of epidemic-intelligence information about communicable diseases of concern to the EU, including global developments with potential to affect Europe ([ECDC weekly threat reports](https://www.ecdc.europa.eu/en/publications-and-data/monitoring/weekly-threats-reports), accessed 2026-08-21). An individual issue identifies its audience as epidemiologists and health professionals and records the covered week and publication date ([CDTR week 33, 2026](https://www.ecdc.europa.eu/en/publications-data/communicable-disease-threats-report-8-14-august-2026-week-33), accessed 2026-08-21).

CDTR is a **regional professional-intelligence source**, not a traveller-authority-specific destination service.

**Access and freshness — verified**

Each reviewed issue has an HTML landing page, dated PDF, and sometimes a ZIP of maps and graphs. ECDC publishes a CDTR taxonomy RSS feed as well as a broader RSS directory ([CDTR RSS feed](https://www.ecdc.europa.eu/en/taxonomy/term/1505/feed) and [ECDC RSS feeds](https://www.ecdc.europa.eu/en/rss-feeds), accessed 2026-08-21). The feed supports structured issue discovery, but the public pages do not document a normalized threat-event API.

ECDC’s Surveillance Atlas supports interactive access and CSV export of aggregate EU/EEA routine surveillance data ([Surveillance Atlas](https://atlas.ecdc.europa.eu/), accessed 2026-08-21). ECDC explicitly limits its open-data policy to routine aggregate surveillance and excludes event-based EpiPulse/Early Warning and Response System data, so Atlas exports cannot be treated as a structured substitute for CDTR threat events ([ECDC open-data policy](https://www.ecdc.europa.eu/en/about-ecdc/who-we-are/key-documents/eueea-routine-surveillance-open-data-policy), accessed 2026-08-21).

Corrections may appear in later weekly reports as a `Corrigendum` describing the earlier error ([CDTR example](https://www.ecdc.europa.eu/sites/default/files/documents/Communicable-disease-threats-report-19-june-2021.pdf), accessed 2026-08-21). A registry entry must therefore track issue identity, PDF checksum, publication date, and later correction references.

**Rights, limits, and fixtures — verified and unknown**

Unless otherwise stated, ECDC-owned website information and documents are CC BY 4.0 and may be reproduced, adapted, and distributed commercially or non-commercially with ECDC attribution, a licence link, and modification disclosure; third-party content and the ECDC logo are excluded ([ECDC intellectual-property notice](https://www.ecdc.europa.eu/en/ecdc-intellectual-property-notices), accessed 2026-08-21). Surveillance-data outputs require attribution to ECDC and reporting Member States and carry accuracy/liability disclaimers ([ECDC third-party data access](https://www.ecdc.europa.eu/en/publications-data/access-eueea-surveillance-data-third-parties), accessed 2026-08-21).

This makes attributed, version-pinned CDTR text/data fixtures comparatively viable after checking each file for third-party content. Spot requests to a CDTR landing page returned `ETag` and HTTP `Last-Modified` headers, but these are observed implementation details rather than a published freshness contract; issue identifiers, RSS dates, covered periods, and PDF checksums remain the stronger cursors ([CDTR week 33, 2026](https://www.ecdc.europa.eu/en/publications-data/communicable-disease-threats-report-8-14-august-2026-week-33), accessed 2026-08-21). No numeric RSS/page rate limit, authentication requirement, or SLA was found.

**Travel Readiness boundary and viability**

Regional outbreak locations, status, trend, and general public-health measures may support non-personalised readiness. Clinical recommendations aimed at professionals must not be turned into individual advice. ECDC is viable as a European regional supplement, but the weekly PDF workflow and professional audience require a conservative adapter and cannot replace a selected national traveller authority.

### PAHO epidemiological alerts and updates

**Role, audience, and coverage — verified**

PAHO says its alerts describe international public-health events that have or could have implications for countries and territories of the Americas, and its updates add information to previously issued alerts. They cover infectious events and may also cover contaminated goods, food safety, chemical, or radionuclear events under the IHR, and they complement global WHO DONs ([PAHO alerts and updates](https://www.paho.org/en/epidemiological-alerts-and-updates), accessed 2026-08-21). Recommendations are commonly directed to Member States and health systems rather than individual travellers ([example 2026 measles alert](https://www.paho.org/en/documents/epidemiological-alert-measles-americas-region-7-august-2026), accessed 2026-08-21).

PAHO is an **Americas regional source**, not a traveller-authority-specific source.

**Access and freshness — verified and unknown**

The index is HTML; individual records have dated HTML landing pages and downloadable PDFs. Alerts are followed by updates as new information becomes available ([PAHO alerts and updates](https://www.paho.org/en/epidemiological-alerts-and-updates), accessed 2026-08-21). No dedicated public alert API, normalized event feed, correction history, or conditional-retrieval contract was found in the reviewed official documentation. A general PAHO page describes public alerts, maps, and reports but does not define a machine contract ([PAHO information management and dissemination](https://www.paho.org/en/detection-verification-and-risk-assessment-dva/information-management-and-dissemination), accessed 2026-08-21).

**Rights, limits, and fixtures — verified**

PAHO publications issued since 6 December 2019 are generally CC BY-NC-SA 3.0 IGO: non-commercial copying and adaptation are allowed with attribution and share-alike, while commercial use requires permission; third-party material must be cleared separately ([PAHO permissions and licensing](https://www.paho.org/en/publications/permissions-and-licensing), accessed 2026-08-21). A current alert PDF carries PAHO copyright and a suggested citation but should still be checked for its item-specific rights statement ([example 2026 alert PDF](https://www.paho.org/sites/default/files/2026/07/2026-1-july-phe-epi-alert-fluovr-enfinal.pdf), accessed 2026-08-21).

Commercial payload retention, redistribution in Handbook snapshots, and captured fixtures are therefore blocked pending written permission. Hand-authored schema/extraction fixtures can avoid copying protected prose. No numeric rate limit, authentication requirement, quota, or availability guarantee was found.

**Travel Readiness boundary and viability**

Affected countries/regions, event dates, public-health status, and general precautions may support readiness. Member-State operational guidance and clinical case-management recommendations must not be presented as individual traveller advice. PAHO is regionally valuable but commercially permission-gated and operationally HTML/PDF-heavy.

## Traveller-authority-specific sources

### CDC Travelers’ Health

**Role, audience, and coverage — verified**

CDC uses Travel Health Notices (THNs) to tell travellers about global health risks during outbreaks, gatherings, natural disasters, and infrastructure disruptions, and publishes four precaution levels ([CDC THN index](https://wwwnc.cdc.gov/travel/notices), accessed 2026-08-21). Destination pages describe diseases, vaccines, medicines, and health risks for international travellers, while directing individual decisions to a clinician ([CDC pre-travel guidance](https://wwwnc.cdc.gov/travel/page/before-travel), accessed 2026-08-21).

CDC is a **traveller-authority-specific source**. Its advice reflects CDC/United States public-health policy and must not be silently represented as the selected authority for every Planner or Companion.

**Access and freshness — verified**

CDC publishes a dedicated RSS feed for new or updated THNs at `https://wwwnc.cdc.gov/travel/rss/notices.xml`; feed items include canonical notice links and publication dates ([CDC RSS documentation](https://wwwnc.cdc.gov/travel/page/rss) and [THN RSS feed](https://wwwnc.cdc.gov/travel/rss/notices.xml), accessed 2026-08-21). Full notice and destination content remains HTML. Individual notices expose a `Page last reviewed` date and may include explicit dated change notes ([Global Polio THN](https://wwwnc.cdc.gov/travel/notices/level2/global-polio), accessed 2026-08-21). Destination pages also expose review dates and may carry topic-specific update dates ([Mexico destination page](https://wwwnc.cdc.gov/travel/destinations/traveler/none/mexico), accessed 2026-08-21).

CDC has a separate REST Content Services API, but CDC says not all web content is syndicated and allows requests to add pages ([CDC Content Services API](https://tools.cdc.gov/api/docs/info.aspx) and [syndication FAQ](https://tools.cdc.gov/medialibrary/docs/Syndication_The%20Basics.pdf), accessed 2026-08-21). Whether every THN and destination page is available with stable media IDs is **unknown pending catalog/account validation**. The RSS-plus-HTML path is the verified public path.

The RSS response observed on 2026-08-21 used `Cache-Control: no-cache` and exposed neither `ETag` nor HTTP `Last-Modified`; item `pubDate` and full-snapshot comparison are therefore the available observed cursors, and disappearance must be detected rather than waiting for a removal event ([THN RSS feed](https://wwwnc.cdc.gov/travel/rss/notices.xml), accessed 2026-08-21). Feed retention depth, canonical destination identifiers, removal semantics, and whether every edit updates `pubDate` still require adapter tests. RSS discovery should never be treated as the complete Evidence payload.

**Rights, limits, and fixtures — verified and unknown**

Most CDC website content is US public-domain material and may be reused, but CDC requires attribution, no implied endorsement, notice that the material is otherwise available free from CDC, and respect for separately marked contractor/third-party material; logos are restricted ([CDC use of agency materials](https://www.cdc.gov/other/agencymaterials.html), accessed 2026-08-21).

That supports attributed offline fixtures made only from confirmed public-domain text, although synthetic fixtures are safer where pages contain third-party maps or imagery. The reviewed RSS and Content Services documentation publishes no API key requirement, numeric rate limit, quota, or SLA. A source adapter still needs a conservative poll interval, bounded retries, and source-unavailable behaviour.

**Travel Readiness boundary**

THN level, affected location, disease/event, dates, and generic protective actions can support readiness. Destination pages frequently recommend vaccines and prescription malaria prophylaxis and explicitly tell travellers to discuss selection with a doctor; Flash Trips may cite the existence of the risk and refer to a clinician, but must not select a vaccine or drug. CDC’s generic website disclaimer also says its applications are not intended to provide medical advice ([CDC disclaimer](https://www.cdc.gov/other/disclaimer.html), accessed 2026-08-21). Country entry requirements embedded in destination pages are legal/immigration material and must be excluded.

**Viability**

Viable for a CDC/US Advisory Authority adapter, with RSS discovery plus validated HTML extraction. It is not a universal authority.

### UK TravelHealthPro / NaTHNaC

**Role, audience, and coverage — verified**

NaTHNaC is commissioned by the UK Health Security Agency. It publishes country-specific travel-health information, vaccine and malaria recommendations, factsheets, and worldwide outbreak surveillance relevant to UK travellers ([NaTHNaC service description](https://travelhealthpro.org.uk/about.php?pid=24&title=nathnac-provides), [country list](https://travelhealthpro.org.uk/countries), and [outbreak surveillance](https://travelhealthpro.org.uk/outbreaks), accessed 2026-08-21).

This is a **UK traveller-authority-specific source** with material for both travellers and health professionals.

**Access and freshness — verified**

Public country and outbreak pages are HTML and expose item-level update dates on reviewed content ([TravelHealthPro general advice](https://travelhealthpro.org.uk/factsheet/30/general-advice-for-travellers) and [example country page](https://travelhealthpro.org.uk/country/134/madagascar), accessed 2026-08-21). NaTHNaC offers a paid, opt-in JavaScript API with setup and annual subscription fees for Country Information, Outbreaks, Factsheets, and News; access and pricing require contact. A free widget provides previews and links rather than normalized content ([TravelHealthPro API and widget](https://travelhealthpro.org.uk/widget.php), accessed 2026-08-21).

The outbreak database is not uniformly official: NaTHNaC says reports are collated from governments, international organisations, and media, marks verification status, and warns that unverified reports may be wrong or later unsubstantiated ([TravelHealthPro outbreak surveillance](https://travelhealthpro.org.uk/outbreaks), accessed 2026-08-21). Only entries verified by an official source can qualify, and the upstream official URL should be retained.

**Rights, limits, and fixtures — verified and unknown**

TravelHealthPro states that website content is available under the Open Government Licence v3.0 unless otherwise stated, while NaTHNaC/TravelHealthPro/UKHSA logos are excluded ([TravelHealthPro API and widget](https://travelhealthpro.org.uk/widget.php), accessed 2026-08-21). The public page does not state whether the paid API adds caching, immutable payload retention, redistribution, fixture, or commercial-display restrictions; those are **contract unknowns**.

No public API schema, authentication mechanism, numeric quota, rate limit, SLA, conditional-retrieval behaviour, or correction/version contract was found. Paid sandbox/test access is also unknown.

**Travel Readiness boundary and viability**

Country risk summaries, verified outbreaks, generic prevention, timestamps, and official upstream links can support readiness for a UK authority. Vaccine schedules, antimalarial selection, contraindications, and advice based on medical history or planned activities require a health professional and cannot be personalised by Flash Trips. FCDO safety and entry requirements linked from country pages belong outside health notices. Public HTML is usable for link-out and carefully validated extraction under OGL; the API is technically promising but commercially and operationally unverified until account terms are obtained.

## Demand-driven national authority examples

### Poland: GIS/State Sanitary Inspection and MFA

**Role, audience, and coverage — verified**

Poland’s Chief Sanitary Inspectorate (GIS) publishes traveller pages about current destination health threats, recommended and required vaccinations, and when to seek travel-medicine advice. It points travellers to a world health-threat map operated on a State Sanitary Inspection domain and to an extraordinary-threat collection called `Bezpieczne podróżowanie` ([GIS traveller information](https://www.gov.pl/web/gis/informacje-dla-podrozujacych), [GIS safe-travel collection](https://www.gov.pl/web/gis/bezpieczne-podrozowanie3), and [State Sanitary Inspection world health-threat map](https://zagrozeniazdrowotne.gssewarszawa.pl/), accessed 2026-08-21).

This is a **Polish traveller-authority-specific source**. The Polish MFA separately publishes country profiles and warning levels prepared by diplomatic posts with the MFA ([Polish MFA traveller information](https://www.gov.pl/web/dyplomacja/informacje-dla-podrozujacych), accessed 2026-08-21). MFA material mixes security, entry/stay, consular, and health concerns and is not a health-only authority feed.

**Access, freshness, corrections, and fixtures — verified and unknown**

The reviewed GIS sources are HTML collections/pages and an interactive map; no documented public travel-health API, RSS feed, bulk export, stable destination identifier contract, or machine-readable correction history was found. The GIS traveller page shows a date of 20 June 2025, while the map presents current alarm/no-alarm states without a public historical version log on the reviewed landing page ([GIS traveller information](https://www.gov.pl/web/gis/informacje-dla-podrozujacych) and [health-threat map](https://zagrozeniazdrowotne.gssewarszawa.pl/), accessed 2026-08-21).

The Polish Open Data and public-sector-information regime provides a route to reuse public-sector information. GIS’s published reuse rules require the full GIS source name, creation or acquisition time, and disclosure of transformations for covered Public Information Bulletin material, while request-supplied information can carry case-specific conditions ([GIS reuse rules](https://www.gov.pl/web/gis/ponowne-wykorzystywanie2) and [Act on Open Data and Reuse](https://www.gov.pl/attachment/9c3d44f7-ca98-450e-adf3-d3f8265438a3), accessed 2026-08-21). The reviewed ordinary travel pages and interactive map do not clearly identify themselves as covered BIP material or grant specific commercial caching, map-data retention, or fixture redistribution rights, so those remain **source-specific legal unknowns** requiring GIS/GSSE confirmation.

No numeric rate limit, authentication requirement, conditional-retrieval guarantee, or SLA was found. Hand-authored HTML/extraction fixtures are possible; copied production pages or map records should not become fixtures until rights are confirmed.

**Travel Readiness boundary and viability**

Destination alarm state, named health threat, official publication date, and generic precautions may support readiness for a Polish Advisory Authority. Vaccine/drug recommendations based on the traveller require a clinician. MFA entry and stay conditions, warning levels, and consular instructions are legal/safety material and must not be merged into the health-notice adapter.

Poland is viable only after an Operator validates the GIS/GSSE ownership chain, destination mapping, page/map extraction, freshness semantics, rights, and fail-closed handling. The lack of a documented structured interface makes this a higher-maintenance adapter.

### Colombia: MinSalud and Instituto Nacional de Salud

**Role, audience, and coverage — verified**

Colombia’s Ministry of Health (MinSalud) publishes traveller guidance for people entering, leaving, or travelling within Colombia. Its current traveller page classifies Colombian municipalities by yellow-fever risk, says the list is updated as viral circulation, human cases, or epizootics change, and gives national and international traveller recommendations ([MinSalud traveller page](https://vacunacion.minsalud.gov.co/EV/Paginas/viajeros.aspx), accessed 2026-08-21). The broader port-health page covers health surveillance at points of entry and general traveller preparation ([MinSalud port health](https://www.minsalud.gov.co/salud/publica/epidemiologia/Paginas/salud-al-viajero.aspx), accessed 2026-08-21).

The Instituto Nacional de Salud (INS) publishes the weekly Boletín Epidemiológico Semanal (BES) for public-health event surveillance. It says BES uses weekly reports and historical averages, is useful for understanding outbreaks but must be complemented by other sources, and that case counts can change after analysis, adjustment, and classification ([INS BES example](https://www.ins.gov.co/buscador-eventos/BoletinEpidemiologico/2026_Boletin_epidemiologico_semana_23.pdf), accessed 2026-08-21).

MinSalud traveller material is a **Colombian traveller-authority-specific source**; INS BES is a **national professional surveillance source** that may corroborate destination risk within Colombia but is not itself a traveller-notice feed.

**Access, freshness, corrections, and fixtures — verified and unknown**

The verified travel source is HTML; INS BES is a dated weekly PDF archive. Colombia’s Open Data portal supports structured datasets and SODA APIs, including public-health surveillance and vaccination-point datasets, but no authoritative, destination-complete travel-health notice or current municipal yellow-fever risk dataset was identified in the reviewed catalog ([MinSalud open-data page](https://www.minsalud.gov.co/Paginas/datos-abiertos.aspx), [public-health surveillance dataset](https://www.datos.gov.co/Salud-y-Protecci-n-Social/Datos-de-Vigilancia-en-Salud-P-blica-de-Colombia/4hyg-wa9d), and [yellow-fever vaccination-points dataset](https://www.datos.gov.co/dataset/Puntos-Vacunaci-n-Fiebre-Amarilla/9aaj-u7wn), accessed 2026-08-21).

The traveller page identifies current circular-driven updates, but the reviewed HTML does not expose a normalized version history or correction feed. BES explicitly warns that counts may change after adjustment, so weekly issue identity and PDF checksums are required and reported counts must remain observation-time-bounded.

**Rights, limits, and fixtures — verified and unknown**

MinSalud says datasets on its open-data page are available freely and without restrictions for reuse and derivative services, and Colombia’s data-portal terms permit commercial and non-commercial reuse of portal data with source and last-update attribution ([MinSalud open data](https://www.minsalud.gov.co/Paginas/datos-abiertos.aspx) and [Datos.gov.co terms](https://herramientas.datos.gov.co/terminos), accessed 2026-08-21). General MinSalud website terms reserve intellectual-property and exploitation rights in site content, while INS website terms restrict copying, distribution, and transformation without authorisation ([MinSalud terms and conditions](https://www.minsalud.gov.co/Paginas/terminos/termino-y-condiciones.aspx) and [INS website terms](https://www.ins.gov.co/Transparencia/Documents/POLITICAS%20Y%20CONDICIONES%20DE%20USO%20DEL%20SITIO%20WEB%20DEL%20INS.pdf), accessed 2026-08-21). The traveller HTML page and INS PDFs were not identified as licensed open datasets.

Consequently, open-data records can be retained according to their item licence, but commercial copying, caching, and fixture redistribution of traveller-page/PDF prose remain **unknown pending written permission or item-specific licensing**. No numeric rate limit, API quota, authentication rule, conditional-retrieval guarantee, or SLA for the traveller pages/PDF archive was found.

**Travel Readiness boundary and viability**

Current municipal risk classifications, outbreak geography, dates, and generic public-health precautions may support readiness for a Colombian authority. Individual vaccine eligibility, booster need, contraindications, symptoms, and treatment are personalised medical advice. Certificate and entry requirements are immigration/legal content.

Colombia is viable only through versioned MinSalud/INS adapters that distinguish traveller guidance from professional surveillance, preserve changing-case caveats, and use open-data APIs only where the dataset’s authority, scope, freshness, and licence match the claim.

## Additional authority alternatives

### Canada

Canada provides a dedicated Travel Health Advisories RSS feed and describes its travel-health notices as potential risks to travellers plus recommended ways to reduce them ([Government of Canada public-health subscriptions](https://www.canada.ca/en/public-health/corporate/stay-informed-stay-connected/public-health-updates.html) and [border and travel health](https://www.canada.ca/en/public-health/services/travel-health.html), accessed 2026-08-21). Global Affairs Canada also publishes continually updated country-advice JSON indexes, including a chronologically updated export, but the dataset combines security, entry/exit, health, laws/culture, disasters, and consular help ([Canada country-advice dataset](https://open.canada.ca/data/en/dataset/bef2ebb3-ca9a-485f-aaff-5dc36eb89426), accessed 2026-08-21).

The Global Affairs Canada JSON dataset is under the Open Government Licence – Canada, which grants worldwide, royalty-free, perpetual reuse including commercial copying, modification, and distribution with attribution and no misrepresentation ([Canada country-advice dataset](https://open.canada.ca/data/en/dataset/bef2ebb3-ca9a-485f-aaff-5dc36eb89426) and [Open Government Licence – Canada](https://open.canada.ca/en/open-government-licence-canada), accessed 2026-08-21). That makes retained, attributed fixtures of the catalogued JSON dataset comparatively practical. It does **not** establish the same rights for Public Health Agency travel-notice HTML or feed text; Canada.ca terms generally require permission for commercial redistribution unless another licence is specified ([PHAC terms and conditions](https://www.canada.ca/en/public-health/corporate/terms-conditions.html), accessed 2026-08-21).

Canada is a credible **traveller-authority-specific structured alternative** and a useful model for registry design. Its two channels need separate registry rights: the mixed Global Affairs JSON export has clear open-data terms, while the PHAC health-notice feed supplies useful discovery but commercial text retention remains permission-gated. Health-only extraction, notice/destination identity validation, conditional-request tests, and confirmation of RSS/JSON quotas and availability are still required; no numeric rate limit or SLA was found in the reviewed pages.

### Australia

The Australian Department of Health directs travellers to Smartraveller for destination-specific developments and subscriber alerts and reserves individual vaccination decisions for a doctor ([Australian travel health](https://www.health.gov.au/topics/travel-health), accessed 2026-08-21). Smartraveller publishes destination exports and RSS resources for an Australian audience ([Smartraveller resources](https://www.smartraveller.gov.au/consular-services/resources) and [service scope](https://www.smartraveller.gov.au/consular-services), accessed 2026-08-21).

Its copyright page restricts commercial use of digital material without written permission ([Smartraveller copyright](https://www.smartraveller.gov.au/copyright), accessed 2026-08-21). It is therefore a technically structured **Australian traveller-authority-specific alternative**, but commercial retention and reproduction remain permission-gated. This agrees with the earlier provider research and does not change the portfolio decision.

## Demand-driven source-registry consequences

An Advisory Authority selection should resolve to a registry identifier, never directly to an arbitrary domain. A versioned registry entry needs at least:

1. **Authority identity and audience:** issuing organisation, jurisdiction, intended traveller population, languages, and whether it is global, regional, or traveller-authority-specific.
2. **Allowed origins:** exact HTTPS hosts, canonical URL patterns, redirect policy, and upstream authority relationships. A search hit outside these routes stays a Provider Observation.
3. **Coverage contract:** destinations/territories, disease/event classes, notice types, exclusions, and a typed distinction among event notice, destination background, professional surveillance, and entry requirement.
4. **Extraction contract:** API/feed/page/PDF version, stable identifiers, schemas/selectors, locale handling, destination normalization, required fields, and fail-closed behavior when layout or schema changes.
5. **Freshness contract:** publication and observation timestamps, expected cadence, maximum age by content type, poll budget, conditional validators where verified, and stale/unavailable outcomes.
6. **Correction contract:** in-place edits, successor/predecessor links, removals, corrigenda/errata, content fingerprinting, and deterministic revalidation triggers.
7. **Rights contract:** item-specific licence, commercial-use status, attribution text/link, third-party exclusions, allowed cache duration, payload-retention and deletion duties, Handbook quotation limits, and fixture policy.
8. **Operational contract:** authentication, quotas, lower application limits, retry policy, timeouts, availability assumptions, and separately authorised live-adapter tests.
9. **Safety contract:** fields allowed into non-personalised Travel Readiness and fields that must be excluded or converted into clinician, consular, immigration, legal, or emergency-service referrals.
10. **Review record:** Operator approval, evidence links, reviewed date, adapter and policy versions, test fixtures, known gaps, and the change that requires re-review.

Onboarding should be demand-driven:

- Collect actual Planner/Companion Advisory Authority selections through a typed product choice; do not infer an authority from language, current location, nationality, or model output.
- Onboard only selected authorities plus explicitly chosen global/regional baselines.
- If a selected authority has no approved registry entry, mark that authority-specific component unavailable and disclose the limitation while supported global or regional readiness may still complete. Return `Blocked: unsupported_advisory_authority` only when the Planner made that authority-specific coverage mandatory. Do not silently substitute CDC, WHO, the destination government, or another country’s advice.
- If companions select different authorities, retain separate Evidence and attribution rather than blending levels into a synthetic “consensus”.
- Runtime search may propose an official URL for Operator review. Until a new registry version validates it, the URL may be shown only as an unnormalised discovery result where policy permits; it cannot support a committed Travel Readiness result or Handbook claim.

## Unknowns and required validation

1. Obtain written commercial-use, caching, immutable-retention, quotation, and test-fixture confirmation for WHO DON and WHO travel-health publications.
2. Confirm PAHO commercial use and retained-derived-data rights; without permission, use links and hand-authored fixtures only.
3. Obtain the TravelHealthPro API schema, authentication, sandbox, quotas, SLA, correction semantics, commercial-display terms, cache duration, retention rights, and upstream-source fields.
4. Validate CDC RSS removal/update behavior, destination identifiers, conditional GET, whether THN/destination pages have stable Content Services media IDs, and the exact public-domain/third-party boundary per retained field.
5. Validate ECDC CDTR feed retention, CDTR ZIP formats, correction discovery, conditional `304` behaviour, and third-party rights in each retained publication.
6. Ask GIS/GSSE for the Polish map’s owner, data sources, destination IDs, update/correction process, commercial reuse, caching, attribution, retained fixture rights, rate limits, and availability expectations.
7. Ask MinSalud/INS whether the current municipal risk classification is available as a versioned open dataset/API and obtain rights for traveller-page and BES extraction/retention.
8. Validate Canada’s feed/item identifiers, health-only mapping, conditional retrieval, and operational limits; the JSON dataset’s strong licence does not prove adapter stability or grant rights to PHAC notice text.
9. For every authority, run a separately authorised adapter spike covering redirects, language variants, malformed/changed content, missing timestamps, corrections, removals, stale data, contradictory global/regional notices, and provider outage.

## Source-quality limitations

- This review used public primary sources only. It did not inspect paid API documentation, account dashboards, signed agreements, private IHR/EpiPulse systems, or correspondence with source owners.
- Public documentation establishes intended scope and interfaces, not completeness, latency, uptime, destination recall, or parsing stability. Spot HTTP requests were used only to observe current cache/validator headers; no complete live adapter, pagination run, correction replay, or conditional `304 Not Modified` test was completed.
- “No API/feed/rate limit/SLA found” means none was found in the reviewed official public material; it is not proof that none exists.
- Government and intergovernmental pages may contain third-party maps, images, or data with different rights. General site licences cannot be applied blindly to every embedded component.
- Publication timestamps are not always observation timestamps. Weekly reports and destination pages may contain facts collected on different dates, and some surveillance counts are explicitly provisional.
- Authority audiences are not interchangeable. Global and regional intelligence may add context, but only the selected traveller authority can fill the authority-specific role.
- Open licensing does not make professional or clinical text safe to personalise. Scope validation remains necessary even when copying and retention are legally permitted.

## Architecture and ADR compatibility

No genuine contradiction with an accepted ADR was found.

- The Operator-reviewed registry and Provider Observation-to-Evidence gate are required by ADR 0002’s deterministic authority boundary and ADR 0005’s provider-adapter/capability split.
- Typed source classes, freshness, scope, contradiction handling, fail-closed `Blocked` outcomes, adapter versions, and offline conformance fixtures align with ADR 0006.
- Excluding personalised medical, immigration, and legal advice aligns with the Travel Readiness definition in `CONTEXT.md` and ADR 0009’s high-risk interaction boundary.
- ADR 0010 requires every externally verifiable Handbook claim to carry Evidence attribution and observed time. Sources with non-commercial terms or unknown payload-retention rights cannot be copied wholesale into an immutable Evidence snapshot or Handbook. The implementation must either obtain permission, retain only expressly permitted provenance/derived fields, or keep that source out of the eligible portfolio; it cannot weaken snapshot immutability or attribution to accommodate a provider.

The resulting constraint is architectural, not a provider selection: global/regional baselines and selected Advisory Authorities are separate source roles, unsupported authority-specific claims must fail closed, and missing optional authority coverage must remain an explicit limitation rather than an invented substitute.
