# Initial travel-provider options and access constraints

Date reviewed: 2026-08-21  
Originating issue: GitHub issue #20, “Research initial travel-provider options and access constraints”  
Decision supported: GitHub issue #5, “Choose the initial provider portfolio and adapter obligations”

## Scope and method

This note compares providers for the initial Air Travel, Accommodation, Dining and Activities place discovery, Route Measurement, Travel Readiness, Budget foreign-exchange, and general-search roles. It does not select the portfolio.

“Verified” below means that the claim is supported by a current provider-owned document, first-party API, specification, or authoritative source repository linked next to the claim. “Unknown” means the public material did not establish the fact, or an account, contract, or live integration is needed to establish it. No provider account was created and no live inventory call was made.

Wanderlisted currently uses Duffel for flights, Hotelbeds for accommodation, Google Places and Routes for places and routes, Tavily constrained to named official domains for advisory discovery, Open-Meteo for weather, ExchangeRate-API for foreign exchange, and Tavily for general search. Those identifications come from the current Wanderlisted adapters and configuration, not from treating their comments as evidence about the providers: [Duffel adapter](https://github.com/Tirso0882/wanderlisted/blob/main/src/tools/flights_duffel.py), [Hotelbeds adapter](https://github.com/Tirso0882/wanderlisted/blob/main/src/tools/hotels_hotelbeds.py), [Google adapter](https://github.com/Tirso0882/wanderlisted/blob/main/src/tools/google_maps.py), [readiness retrieval](https://github.com/Tirso0882/wanderlisted/blob/main/src/readiness/retrieval.py), [Open-Meteo adapter](https://github.com/Tirso0882/wanderlisted/blob/main/src/readiness/weather.py), [currency adapter](https://github.com/Tirso0882/wanderlisted/blob/main/src/tools/currency.py), and [Tavily transport](https://github.com/Tirso0882/wanderlisted/blob/main/src/tools/tavily.py) (all accessed 2026-08-21).

## Cross-cutting comparison criteria

- A Provider Observation is not Evidence until the owning capability validates identity, scope, freshness, eligibility, and provenance. Search-engine snippets therefore cannot become official-advisory Evidence merely because they point at an official domain.
- Selected bookable items need policy-approved HTTPS provider deep links that remain valid for Trip Handbook delivery. A provider that only supports in-application booking, or issues short-lived links, needs a separately proven redirect/link strategy.
- Provider licence and retention terms must permit the immutable Evidence and Handbook Snapshot records required by the architecture. Where public terms prohibit caching, captured live payloads are not suitable CI fixtures; use hand-authored schema fixtures unless the contract expressly permits retained test data.
- A sandbox proves request and failure handling, not live inventory coverage or price accuracy. Live-provider tests remain separately authorised and are not required for deterministic offline acceptance.
- Published quota numbers are ceilings, not resource policy. Each adapter still needs lower per-Run call limits, bounded retries, cost limits, and fail-closed unavailable behaviour.

## Flight inventory

### Duffel — Wanderlisted incumbent; technically accessible, product-fit conditional

- **Access and test:** self-service registration provides test tokens and a risk-free test mode. Live tokens require account activation. Test mode deliberately favours the synthetic Duffel Airways carrier and does not provide realistic schedules or prices. [Dashboard access](https://duffel.com/docs/guides/getting-started-with-the-dashboard) and [test mode](https://duffel.com/docs/api/overview/test-mode) (accessed 2026-08-21).
- **Pricing and quota:** Flights is pay-as-you-go with no up-front fee; the public fee schedule lists a per-confirmed-order fee, a per-paid-ancillary fee, a 2% foreign-exchange fee where conversion is needed, and an excess-search charge above a 1,500:1 search-to-book ratio. The API rate-limit window is 60 seconds, the assigned limit is exposed in response headers, and higher limits require support. [Duffel pricing](https://duffel.com/pricing) and [response handling](https://duffel.com/docs/api/overview/response-handling) (accessed 2026-08-21).
- **Freshness and inventory:** an offer should be retrieved again before use because airline prices, services, and availability can change; even the refreshed offer is not guaranteed bookable. Supplier coverage and the live carriers available to this specific account remain account-test unknowns. [Offers](https://duffel.com/docs/api/offers/get-offers) (accessed 2026-08-21).
- **Deep links:** Duffel Links creates a Duffel-hosted search-and-book URL, but the session is single-use and expires after 24 hours. That is a usable hand-off mechanism, not yet a proven durable deep link for an immutable Handbook Snapshot. The ordinary Flights API otherwise leads to creating an order inside the integrating product. [Duffel Links](https://duffel.com/docs/guides/duffel-links) and [flight booking flow](https://duffel.com/docs/guides/getting-started-with-flights) (accessed 2026-08-21).
- **Attribution, licensing, fixtures:** public documentation reviewed here does not state a general display-attribution requirement or a right to retain live offer payloads as reusable fixtures. Test-mode responses are suitable for authorised integration tests; deterministic CI should use hand-authored contract fixtures until retention rights are confirmed.
- **Fit:** viable for development and live shopping if activation succeeds, but direct order creation would contradict Flash Trips’ current non-booking boundary. The 24-hour hosted link also needs an explicit revalidation/link policy before it can satisfy handbook delivery.

### Skyscanner Flights Live Prices — approval-gated redirect candidate

- **Access and test:** an API key is issued only after Partnerships approves an application. The public docs do not describe an open sandbox or synthetic test inventory. [Authentication](https://developers.skyscanner.net/docs/getting-started/authentication) (accessed 2026-08-21).
- **Pricing and quota:** public pricing is not stated. Quotas are partner-specific; published defaults are 100 create calls per second and minute and 100 poll calls per second/500 per minute, subject to the partner agreement. [Rate limits](https://developers.skyscanner.net/docs/getting-started/rate-limits) (accessed 2026-08-21).
- **Freshness, inventory, and deep links:** `/create` returns an initial cached subset, `/poll` gathers fuller live supplier results, the session token lasts about one hour, and each itinerary contains a booking `deepLink`. Skyscanner states that live prices are retrieved from airline and inventory partners for the search, while its FAQ warns that prices can still change. [Live Prices overview](https://developers.skyscanner.net/docs/flights-live-prices/overview), [quick start](https://developers.skyscanner.net/docs/flights-live-prices/quick-start), and [FAQ](https://developers.skyscanner.net/docs/faqs) (accessed 2026-08-21).
- **Commercial/display obligation:** live searches must be user-generated, have exact origin, destination, and dates, and produce a reasonable rate of visible end-user booking-link clicks; the provider expects roughly 5–20% of create sessions to result in a deep-link click. Redirect tracking uses Impact links. [Usage guidelines](https://developers.skyscanner.net/docs/getting-started/usage-guidelines) and [Impact links](https://developers.skyscanner.net/docs/getting-started/impact) (accessed 2026-08-21).
- **Fixtures:** the schema is documentable, but rights to retain live responses as CI fixtures and any test credentials are unknown pending approval. Hand-authored fixtures are the safe default.
- **Fit:** strong redirect/deep-link alignment, but viability is conditional on partner approval and on Flash Trips’ low-volume invitation traffic satisfying conversion expectations.

### Amadeus Enterprise APIs — credible inventory, no longer self-service

- The Amadeus for Developers self-service portal was decommissioned on 2026-07-17. Access now requires an Enterprise request, with an Enterprise sandbox, consultant-led product selection, and custom pricing. [Amadeus Enterprise API Portal](https://developers.amadeus.com/) (accessed 2026-08-21).
- Public current pages do not establish account-specific flight inventory, quota, redirect/deep-link support, retention rights, or production approval time. Those are contract-gated unknowns.
- **Fit:** credible enterprise alternative, but not presently a self-service initial-provider path. It becomes viable only after access and commercial terms are obtained.

### Expedia Flight Listings — not open to a new integration

Expedia’s Travel Redirect API provides flight search and booking deep links, but the official product page says all new API applications are paused. [Travel Redirect API](https://developers.expediagroup.com/travel-redirect-api) (accessed 2026-08-21). It is therefore not currently viable for a new Flash Trips integration, even though its redirect model matches the product boundary.

## Accommodation inventory

### Hotelbeds Booking API — Wanderlisted incumbent; accessible test, live certification required

- **Access and test:** registration gives an API key and secret for `api.test.hotelbeds.com`; test bookings create no property reservation or card charge. Evaluation access is limited to 50 requests per day, and higher/certification access follows account progression. [Getting started](https://developer.hotelbeds.com/documentation/getting-started/) (accessed 2026-08-21).
- **Live approval and pricing:** going live requires a certification review of availability, CheckRate, confirmation, content, voucher, and booking-management behaviour. Commercial pricing is a negotiated net or commissionable model with an HBX Group sales manager, not a public request tariff. [Certification](https://developer.hotelbeds.com/documentation/hotels/knowledge-base/certification-process/) and [pricing models](https://developer.hotelbeds.com/documentation/hotels/knowledge-base/pricing-models/) (accessed 2026-08-21).
- **Freshness and inventory:** most rates are directly bookable, while `RECHECK` rates require CheckRate for current availability and price. Exact live property, destination-code, and independent-property coverage for the intended markets requires account testing. [Booking API](https://developer.hotelbeds.com/documentation/hotels/booking-api/) (accessed 2026-08-21).
- **Deep links and product boundary:** the documented workflow confirms, retrieves, modifies, and cancels bookings. No provider-hosted consumer deep-link field was found in the public Booking API documentation reviewed. That makes redirect-only use an unresolved blocker and direct integration outside Flash Trips’ current boundary.
- **Attribution, licensing, fixtures:** display and payload-retention rights were not established by the public technical pages. Evaluation responses are useful for separately authorised integration tests; deterministic CI should use hand-authored schema fixtures until the agreement is reviewed.

### Booking.com Demand API — approval-gated, redirect-aligned candidate

- **Access and test:** both production and sandbox require a Booking.com partner API key and affiliate ID. The sandbox uses dedicated synthetic inventory, supports accommodation booking flows without production inventory, and is limited to 50 requests per minute. [Authentication](https://developers.booking.com/demand/docs/development-guide/authentication) and [sandbox](https://developers.booking.com/demand/docs/getting-started/sandbox) (accessed 2026-08-21).
- **Pricing and live quota:** the public docs describe an affiliate-partner model rather than a public per-call price. Production quota is account-specific and must be obtained from the account manager; sandbox is fixed at 50 requests per minute. [Rate limiting](https://developers.booking.com/demand/docs/development-guide/rate-limiting) (accessed 2026-08-21).
- **Freshness, inventory, and links:** search/availability responses carry current products and prices plus affiliate-attributed URLs. Version 3.2 consolidates mobile and web destinations in `url.app` and `url.web`; the redirect tutorial sends the traveller to Booking.com to pay and confirm. Sandbox IDs do not work in production. [Accommodation tutorial](https://developers.booking.com/demand/docs/accommodations/accommodation-tutorial), [v3.2 URL migration](https://developers.booking.com/demand/docs/migration-guide/v3.2/accommodations/details), and [sandbox limitations](https://developers.booking.com/demand/docs/getting-started/sandbox) (accessed 2026-08-21).
- **Attribution, licensing, fixtures:** affiliate ID and generated URL must be preserved for attribution. Booking.com’s production-readiness guidance says dynamic price and availability data must not be stored, so the purpose-built sandbox supports adapter testing but offline CI should use synthetic fixtures. [Production readiness](https://developers.booking.com/demand/docs/development-guide/production-readiness) (accessed 2026-08-21).
- **Fit:** the redirect flow fits the non-booking boundary and handbook-link requirement better than a wholesale booking API, but partner approval and exact inventory/commission terms are blockers.

### Skyscanner Hotels Live Prices — approval-gated redirect candidate

- The API searches bookable hotel offers up to one year ahead using create/poll sessions, and pricing options contain a `deeplink`. Supplier contracts mean API content and prices can differ from skyscanner.net and some options are unavailable through the API. [Hotels overview](https://developers.skyscanner.net/docs/hotels-live-prices/overview) and [API schema](https://developers.skyscanner.net/api/hotels-live/) (accessed 2026-08-21).
- The same partner approval, custom quota, user-generated-search, and conversion obligations as Skyscanner Flights apply. Public pricing, sandbox access, payload-retention rights, and the actual inventory available to Flash Trips remain unknown. [Authentication](https://developers.skyscanner.net/docs/getting-started/authentication), [rate limits](https://developers.skyscanner.net/docs/getting-started/rate-limits), and [usage guidelines](https://developers.skyscanner.net/docs/getting-started/usage-guidelines) (accessed 2026-08-21).
- **Fit:** potentially strong for external booking links, conditional on approval and low-volume conversion economics.

### Expedia lodging products — two different, approval-blocked paths

- Rapid Lodging is a partner-approved search-and-book API. It has a non-booking test endpoint with controllable test responses, but production requires launch review and business-development-manager enablement; exact limits and commercial terms are account-specific. [Rapid setup](https://developers.expediagroup.com/rapid/setup) and [booking test requests](https://developers.expediagroup.com/rapid/lodging/booking/rapid-booking-test-request) (accessed 2026-08-21). Its booking flow would require a strict read-only subset or remain outside current scope.
- Travel Redirect returns lodging deep links and would fit the hand-off model, but new API applications are paused. [Travel Redirect API](https://developers.expediagroup.com/travel-redirect-api) and [integration flow](https://developers.expediagroup.com/travel-redirect-api/api/integration-guide/integration-types) (accessed 2026-08-21).

## Place discovery

### Google Places API (New) — Wanderlisted incumbent; self-service, retention-constrained

- **Access and test:** access is through a Google Cloud project, API key, enabled API, and billing. No dedicated sandbox or synthetic place catalogue is documented. [Places REST reference](https://developers.google.com/maps/documentation/places/web-service/reference/rest) (accessed 2026-08-21).
- **Pricing and quota:** pay-as-you-go billing is selected by requested fields; a field mask is mandatory and the highest applicable Essentials, Pro, or Enterprise field controls the SKU. Quotas are per method per project and can be capped or increased in Cloud Console. [Usage and billing](https://developers.google.com/maps/documentation/places/web-service/usage-and-billing) (accessed 2026-08-21).
- **Freshness, geography, and links:** Details can return current and regular opening hours, business status, ratings, website URI, and `googleMapsUri`; exact field availability varies by place and selected SKU. Google Maps URLs can also produce HTTPS search links without an API key. Geographic completeness and source freshness are not promised per place and need market sampling. [Place Details](https://developers.google.com/maps/documentation/places/web-service/place-details) and [Maps URLs](https://developers.google.com/maps/documentation/urls/get-started) (accessed 2026-08-21).
- **Attribution and storage:** applications must identify Google Maps content and expose required third-party, photo, and review attributions. Places content may not be prefetched, cached, or stored except for documented exceptions; place IDs may be stored indefinitely. [Places policies](https://developers.google.com/maps/documentation/places/web-service/policies) (accessed 2026-08-21).
- **Fixtures and fit:** the storage restriction makes production-response snapshots poor Evidence or CI fixtures. Store permitted identifiers and independently validated canonical facts; use hand-authored fixtures for the adapter. The live API remains viable if the Evidence policy records source IDs/observed time without retaining prohibited content.

### Foursquare Places API — self-service alternative, similarly retention-constrained

- **Access, pricing, and quota:** service API keys are generated in the developer console. From 2026-06-01, the published schedule gives 500 free calls followed by tiered per-thousand pricing; Pay-as-you-go and Sandbox accounts are limited to 50 queries per second. The legacy V3 endpoints were deprecated on 2026-05-15 in favour of the FSQ OS Places-powered API. [Service keys](https://docs.foursquare.com/developer/docs/manage-service-api-keys), [2026 changes](https://docs.foursquare.com/developer/reference/upcoming-changes), and [rate limits](https://docs.foursquare.com/fsq-developers-places/reference/rate-limits) (accessed 2026-08-21).
- **Freshness, geography, and links:** the provider describes global POI data and accepts place edits, but does not publish a per-market completeness or freshness SLA on the reviewed pages. A current canonical consumer deep-link field was not verified for the new API.
- **Attribution and storage:** Foursquare credit is required. Place IDs, address IDs, and photo IDs may be cached indefinitely, but Pay-as-you-go and Sandbox users may not cache other attributes; Enterprise is limited to 24-hour local-device caching for other attributes. [Usage guidelines](https://docs.foursquare.com/fsq-developers-places/reference/usage-guidelines) (accessed 2026-08-21).
- **Fixtures and fit:** self-service access makes it testable, but the no-caching rule is a major mismatch for immutable Evidence and recorded fixtures. Use synthetic fixtures and confirm whether an Enterprise agreement can permit the required server-side Evidence record.

### OpenStreetMap data with Nominatim/Overpass — open-data control, public-service limits

- OpenStreetMap data is ODbL-licensed and requires visible OpenStreetMap attribution plus access to the licence; distributing a derived database can trigger share-alike obligations. [OSMF attribution guidelines](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines) (accessed 2026-08-21).
- The public Nominatim service permits at most one request per second, requires an identifying User-Agent/Referer and caching, discourages bulk/geocoding automation, and requires applications to be switchable to another service. [Nominatim policy](https://operations.osmfoundation.org/policies/nominatim/) (accessed 2026-08-21).
- Public Overpass instances are shared infrastructure with instance-specific policies; the main instance’s published safe-use guidance is under 10,000 queries and 1 GB per day. Self-hosting is possible but operationally substantial. [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API) and [installation](https://wiki.openstreetmap.org/wiki/Overpass_API/Installation) (accessed 2026-08-21).
- **Freshness, links, and fixtures:** community edits can be minutely at the data layer but completeness varies by place and tag. ODbL permits retained fixtures with attribution/share-alike analysis, and self-hosting gives deterministic dataset-version control. Public endpoints are viable only for a very small pilot, not as an unbounded production dependency.

## Route Measurement

### Google Routes API — Wanderlisted incumbent; strongest mode set, retention-constrained

- **Access and test:** uses a billed Google Cloud project/API key; no dedicated sandbox is documented. Compute Routes supports route duration/distance, traffic-aware options, waypoint optimisation, and transit route matrices. [Compute Routes reference](https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRoutes) (accessed 2026-08-21).
- **Pricing and quota:** pay-as-you-go SKU depends on Basic, Advanced, or Preferred features. Compute Routes is billed per request, matrices per origin×destination element; published limits are 3,000 route queries per minute and 3,000 matrix elements per minute. [Routes usage and billing](https://developers.google.com/maps/documentation/routes/usage-and-billing) (accessed 2026-08-21).
- **Freshness and deep links:** traffic-aware results are observation-time dependent. Route tokens are short-lived Navigation SDK inputs rather than durable public links; a separate Google Maps URL can provide an HTTPS directions hand-off. [Route tokens](https://developers.google.com/maps/documentation/routes/route_token) and [Maps URLs](https://developers.google.com/maps/documentation/urls/get-started) (accessed 2026-08-21).
- **Attribution, storage, and fixtures:** most Routes content cannot be cached; place IDs are the stated exception. [Routes policies](https://developers.google.com/maps/documentation/routes/policies) (accessed 2026-08-21). Therefore persist the validated Route Measurement and provenance only to the extent the contract permits, and use hand-authored offline fixtures rather than captured responses.

### openrouteservice — open-source road/active-mode alternative

- **Access, pricing, and quota:** the hosted Standard plan is free and publishes 2,000 Directions calls per day/40 per minute; self-hosted service removes hosted API quotas subject to hardware. [Plans](https://openrouteservice.org/plans/) (accessed 2026-08-21).
- **Coverage and modes:** hosted directions are global and support driving, truck, bicycle, walking, hiking, and wheelchair profiles. The reviewed product page does not offer public-transit routing, so this cannot replace Google transit measurements. [openrouteservice](https://openrouteservice.org/) (accessed 2026-08-21).
- **Attribution and licensing:** hosted results require openrouteservice/HeiGIT and OpenStreetMap attribution. The current HeiGIT terms state CC BY-SA 4.0, while a still-published staging/legacy page states CC BY 4.0; the applicable licence must be confirmed before retaining or redistributing results. [Current terms](https://openrouteservice.org/terms-of-service/) and [staging terms](https://staging.openrouteservice.org/terms-of-service/) (accessed 2026-08-21).
- **Freshness, links, and fixtures:** classic graph refresh cadence is not guaranteed on the reviewed pages. There is no documented durable consumer navigation deep link. Open licensing and self-hosting make version-pinned offline fixtures practical, but live-route freshness and self-host operating cost must be measured.

### Mapbox Directions API — commercial road/active-mode alternative

- Mapbox Directions uses an access token and request-based billing and supports driving, traffic-aware driving, walking, and cycling profiles. The public reference documents request-shape limits and route options; no public-transit profile is documented. [Directions API](https://docs.mapbox.com/api/navigation/directions) and [pricing guide](https://docs.mapbox.com/accounts/guides/pricing/) (accessed 2026-08-21).
- Exact free allowance, assigned rate limits, content-retention rights, attribution for a non-map Handbook presentation, and a durable consumer deep link were not established by the reviewed public pages. Those must be resolved against the account terms before this option is considered viable for immutable Evidence.
- Deterministic schema fixtures are practical; retaining live Mapbox results as fixtures remains a contract unknown.

## Official travel advisories

### Tavily over official domains — Wanderlisted discovery mechanism, not the authority

- Tavily is self-service with 1,000 free credits monthly; basic search costs one credit and advanced search two. Development keys allow 100 requests per minute and production keys 1,000, with production keys requiring a paid plan or pay-as-you-go. [Credits and pricing](https://docs.tavily.com/documentation/api-credits) and [rate limits](https://docs.tavily.com/documentation/rate-limits) (accessed 2026-08-21).
- Domain inclusion filters can constrain discovery, but Tavily’s ranking/snippet remains an intermediary observation. The official page URL and content must be fetched and validated before becoming advisory Evidence. Public documentation reviewed does not provide a durable test index or guarantee when a changed government page enters results.
- **Fixtures and fit:** synthetic search-result fixtures are straightforward; retaining live snippets requires terms review. Tavily is viable as fallback discovery and general search, not as the official-advisory source of record.

### Direct origin-country sources — viable authority adapters

- **United Kingdom:** the unauthenticated GOV.UK Content API returns structured JSON for `/foreign-travel-advice/{country}` and can be used by anyone for any purpose. The `travel_advice` schema includes `updated_at`, `reviewed_at`, `max_cache_time`, change history, country identity, and canonical content relationships. The API is beta and publishes a limit of 10 requests per second per client. GOV.UK content is generally reusable under the Open Government Licence with attribution. [Content API](https://content-api.publishing.service.gov.uk/), [API reference](https://content-api.publishing.service.gov.uk/reference.html), [travel-advice schema](https://docs.publishing.service.gov.uk/content-schemas/travel_advice.html), and [reuse guidance](https://www.gov.uk/help/reuse-govuk-content) (accessed 2026-08-21).
- **United States:** the Department of State publishes an official Travel Advisory RSS feed at `https://travel.state.gov/_res/rss/TAsTWs.xml`; advisories expressly assess risks for U.S. citizens, nationals, and legal residents. The source warns conditions can change rapidly. Bureau of Consular Affairs information is public domain unless marked otherwise, while third-party media may remain protected. [RSS](https://travel.state.gov/content/travel/en/rss.html), [advisory scope](https://travel.state.gov/en/international-travel/travel-advisories.html), and [copyright disclaimer](https://travel.state.gov/content/travel/en/copyright-disclaimer.html) (accessed 2026-08-21).
- **Australia:** Smartraveller publishes a free public `destinations-export` API and RSS feeds for all updates and higher advisory levels; its advice covers more than 170 destinations and is for Australians overseas. Its copyright page requires attribution but also restricts commercial use of digital material without written consent, so commercial retention/reproduction is permission-gated. [Resources](https://www.smartraveller.gov.au/consular-services/resources), [service scope](https://www.smartraveller.gov.au/consular-services), and [copyright](https://www.smartraveller.gov.au/copyright) (accessed 2026-08-21).
- **Access, pricing, links, and quotas:** these sources require no account and expose canonical government URLs. Apart from GOV.UK’s published 10-requests-per-second client limit, no paid pricing, sandbox, public SLA, or numeric rate limit was found on the reviewed official pages; polite conditional retrieval, source-specific caching metadata, and a lower application budget are required.
- **Fixtures and fit:** GOV.UK and U.S. advisory content have comparatively clear reuse paths for attributed fixtures. Smartraveller commercial fixtures require permission. For any unsupported authority, retaining hashes, timestamps, parsed levels, canonical URLs, and the minimum permitted quoted content is safer than copying complete pages.
- **Coverage constraint:** an advisory is authoritative only for the Planner/Companion nationality or residence policy to which it applies. There is no verified single official global advisory API. Flash Trips needs an explicit origin-country authority registry and a typed “no supported official authority” outcome.

## Weather

### Open-Meteo — Wanderlisted incumbent; viable with commercial licence for hosted product

- **Access, pricing, and quota:** the open endpoint requires no key but is non-commercial only, has no uptime guarantee, and is limited to 600 calls/minute, 5,000/hour, 10,000/day, and 300,000/month. Commercial subscriptions provide a dedicated keyed endpoint and monthly call budgets starting at one million calls. [Pricing](https://open-meteo.com/en/pricing) and [terms](https://open-meteo.com/en/terms) (accessed 2026-08-21).
- **Freshness and geography:** the Forecast API is global, defaults to seven days, and supports up to 16 days. Available models, variables, resolution, and update cadence vary geographically; historical and previous-run APIs are available for validation. [Forecast docs](https://open-meteo.com/en/docs) and [historical docs](https://open-meteo.com/en/docs/historical-weather-api) (accessed 2026-08-21).
- **Attribution and licensing:** API data is CC BY 4.0 and requires credit, a licence link, indication of changes, and a visible Open-Meteo link where data is displayed; some underlying datasets have additional attribution. [Licence](https://open-meteo.com/en/licence) (accessed 2026-08-21).
- **Links and fixtures:** the request URL can serve as source URL but is not a consumer weather page deep link. CC BY permits retained fixtures with required attribution, making this the clearest incumbent for deterministic forecast-contract tests.

### OpenWeather — self-service commercial alternative

- One Call requires an account/API key and separate pay-as-you-call subscription; the first 1,000 calls per day are free and overage is per call. Other plans use per-minute/month limits and publish different update frequencies. [One Call 3.0](https://openweathermap.org/api/one-call-3) and [pricing](https://openweathermap.org/price) (accessed 2026-08-21).
- One Call provides global current, hourly/daily forecast, and government weather alerts; exact horizons and products depend on the subscribed API generation/plan. [Weather APIs](https://openweathermap.org/api) (accessed 2026-08-21).
- Self-service plans require visible OpenWeather attribution and use ODbL or plan-specific terms; Enterprise can negotiate different attribution and service terms. [Licence explainer](https://openweathermap.org/storage/app/media/documents/License_explainer_25%20Feb_25.pdf) and [FAQ](https://openweathermap.org/faq) (accessed 2026-08-21).
- There is no dedicated sandbox; an API key and free allowance support integration tests. Offline fixture redistribution/share-alike consequences need licence review before recording live payloads.

### WeatherAPI.com — simple keyed alternative

- The free plan publishes 100,000 calls/month and three-day forecasts; paid tiers extend calls, history, and forecast/future horizons. Forecast data is updated every 4–6 hours and quota resets monthly. [Pricing](https://www.weatherapi.com/pricing.aspx) (accessed 2026-08-21).
- The API returns JSON/XML and supports up to 14-day forecasts in plans that include them; access and quota errors are explicit. [Documentation](https://www.weatherapi.com/docs/) (accessed 2026-08-21).
- There is no separate sandbox or consumer deep-link requirement. The terms require attribution for free use and permit current responses to be cached for 60 minutes, forecast responses for 24 hours, and historical responses indefinitely. Historical payloads are therefore suitable for retained fixtures; forecast fixtures should be synthetic or discarded within the permitted cache window unless broader rights are obtained. [Terms](https://www.weatherapi.com/terms.aspx) (accessed 2026-08-21).

## Foreign exchange

### ExchangeRate-API — Wanderlisted incumbent; self-service and cache-friendly

- **Access, pricing, and quota:** open access requires no key, is rate-limited, updates daily, and requires attribution. The keyed free plan provides 1,500 requests/month with daily updates; the public Pro plan starts at a monthly fee, provides 30,000 requests/month, and updates hourly. Higher tiers update every five minutes. [Open access](https://www.exchangerate-api.com/docs/free), [pricing](https://www.exchangerate-api.com/), and [data update rates](https://www.exchangerate-api.com/product/our-exchange-rate-data) (accessed 2026-08-21).
- **Freshness and coverage:** each response provides last/next update timestamps. Less-traded currencies may not change on every provider refresh. Supported currencies and historical depth depend on plan. [Standard response](https://www.exchangerate-api.com/docs/standard-requests) and [data methodology](https://www.exchangerate-api.com/product/our-exchange-rate-data) (accessed 2026-08-21).
- **Licensing and fixtures:** caching and reuse for the customer’s end purpose are expressly allowed, including commercial use, but redistribution or exposing programmatic exchange-rate access is prohibited. Open access requires a visible provider link; paid plans remove that attribution requirement. [Terms](https://www.exchangerate-api.com/terms) and [open-access attribution](https://www.exchangerate-api.com/docs/free) (accessed 2026-08-21).
- **Fit:** viable and unusually compatible with immutable Evidence and deterministic captured fixtures, subject to keeping Handbook rates as derived travel-budget information rather than redistributing an FX API.

### ECB Data Portal — free official reference-rate source with narrower purpose

- The ECB exposes an unauthenticated SDMX 2.1 REST API. `updatedAfter` and `If-Modified-Since` support incremental freshness checks and HTTP 304 responses. No numeric public quota was found. [API overview](https://data.ecb.europa.eu/help/api/overview) and [data queries](https://data.ecb.europa.eu/help/api/data) (accessed 2026-08-21).
- Reference rates cover 29 currencies against EUR, update around 16:00 CET on working days except TARGET closing days, are informational, and are strongly discouraged for transaction use. [ECB reference rates](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html) (accessed 2026-08-21).
- Public ESCB statistics may be reused free for commercial or non-commercial purposes if the source is quoted and the data/metadata are not modified; derived calculations must be identified as such under the general site disclaimer. [Reuse policy](https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html) and [disclaimer](https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html) (accessed 2026-08-21).
- **Fit and fixtures:** excellent official, deterministic source for daily EUR reference conversions and fixtures; insufficient alone for unsupported currencies, weekends/holidays without last-known-rate policy, or near-real-time budget checks.

### Frankfurter v2 — open-source central-bank aggregator

- Frankfurter is keyless, open source, self-hostable, and states that it aggregates daily rates from 84 central banks/official sources covering 201 currencies. There are no daily/monthly quotas, but abuse rate limiting applies. Requests can pin a named provider such as ECB instead of using the default blend. [Frankfurter API](https://frankfurter.dev/) and [ECB provider](https://frankfurter.dev/providers/ecb/) (accessed 2026-08-21).
- Commercial use is allowed, but the underlying authority’s terms still apply. Exact update time follows each source, and blended provenance must be retained per observation.
- **Fit and fixtures:** broad and easy to self-host/version for offline tests, but it is an intermediary rather than the official authority. Pinning a source and recording source/date avoids treating an unexplained blend as authoritative.

## General web search

### Tavily — Wanderlisted incumbent; self-service agent-oriented search

- **Access, price, and quota:** API-key self-service includes 1,000 free monthly credits; basic/advanced search costs one/two credits, paid plans are credit-based, and development/production keys allow 100/1,000 requests per minute. [Credits](https://docs.tavily.com/documentation/api-credits), [rate limits](https://docs.tavily.com/documentation/rate-limits), and [API introduction](https://docs.tavily.com/documentation/api-reference/introduction) (accessed 2026-08-21).
- **Freshness and coverage:** search supports general/news topics and domain allow/deny controls. Tavily markets real-time results but the reviewed docs provide no crawl timestamp or index-freshness SLA for ordinary search, so the returned URL must be fetched and observed time recorded when freshness matters.
- **Licensing, links, and fixtures:** results contain source URLs suitable for citations. Public pages reviewed do not clearly grant long-term storage/redistribution rights for snippets; retain canonical URLs and validated Evidence, and use synthetic response fixtures until terms are confirmed.
- **Fit:** viable for bounded discovery and general travel questions, but snippets and generated answers remain untrusted Provider Observations.

### Brave Search API — self-service independent-index alternative

- **Access, price, and quota:** a subscription and API key are required; the Search plan is priced per 1,000 requests, includes monthly credits, and publishes 50 requests/second capacity. Sliding-window and monthly quotas are returned in headers. [Pricing](https://api-dashboard.search.brave.com/documentation/pricing) and [rate limiting](https://api-dashboard.search.brave.com/documentation/guides/rate-limiting) (accessed 2026-08-21).
- **Freshness and coverage:** the API exposes web, news, images, videos, search operators, and freshness filters over Brave’s independent index. Exact index coverage and update latency for travel authorities require comparative tests. [Documentation](https://api-dashboard.search.brave.com/app/documentation) (accessed 2026-08-21).
- **Storage and attribution:** terms prohibit storing, caching, or building a database from search results except transient operational storage, and do not grant rights to third-party pages. The terms permit provider attribution in a prescribed “POWERED BY BRAVE” form and allow Brave to require it. [Terms](https://api-dashboard.search.brave.com/documentation/resources/terms-of-service) (accessed 2026-08-21).
- **Fixtures and fit:** use hand-authored fixtures only. The storage restriction means search-result payloads cannot themselves be the immutable Evidence record; separately fetch and license the source page.

### Azure OpenAI Web Search / Grounding with Bing — Azure-native but coupled alternative

- The Web Search tool is available through Azure OpenAI Responses with an Azure OpenAI deployment and authentication. Search tool calls incur additional charges, domain allow lists support up to 100 URLs, and standard Web Search does not expose unrestricted live internet access as a raw HTTP search API. [Azure OpenAI web search](https://learn.microsoft.com/azure/foundry/openai/how-to/web-search) (accessed 2026-08-21).
- Grounding with Bing is a First Party Consumption Service outside the Azure compliance/geo boundary; the Microsoft Data Protection Addendum does not apply. Returned citations and source links must be preserved/displayed as required. [Bing tools](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/bing-tools) (accessed 2026-08-21).
- **Fit:** viable for reasoning-grounded answers, but it couples retrieval to the reasoning provider and may not expose the raw, independently normalisable observations desired by a provider adapter. Exact quotas, retention, and offline-fixture rights are account/terms unknowns.

### Google Custom Search JSON API — unavailable to Flash Trips as a new customer

The API is closed to new customers and will discontinue for existing customers on 2027-01-01. [Custom Search JSON API](https://developers.google.com/custom-search/v1/overview) (accessed 2026-08-21). It is not a viable new-provider option.

## Unknowns and access checks for issue #5

1. Apply for or obtain written pre-sales confirmation from Skyscanner and Booking.com before treating either deep-link portfolio as available; record approval time, pilot-volume expectations, commercial terms, payload-retention rights, and whether invitation-only traffic qualifies.
2. Ask Duffel whether a link can target a selected offer and remain valid long enough for handbook delivery, and whether read-only shopping without Flash Trips taking payment/orders is an accepted use case under the search-to-book policy.
3. Ask Hotelbeds whether a certified account may expose a provider-hosted booking link instead of booking through Flash Trips. If not, it does not fit the current boundary despite technical inventory access.
4. Obtain the exact Google Maps Platform terms applicable to the billing region, then define the minimum Evidence record that can be retained without storing prohibited Places/Routes content.
5. Confirm Foursquare Enterprise retention terms before considering its rich place attributes for immutable Evidence.
6. Define supported Planner/Companion origin countries for Travel Readiness, then verify copyright/reuse and conditional-request behaviour for each official advisory source. Smartraveller needs written commercial-use clarification. Absence of a supported authority must return `Blocked`, not silently substitute another country’s advice.
7. Decide whether the hosted invitation pilot is commercial for Open-Meteo licensing purposes. The public free endpoint explicitly excludes commercial use.
8. Run separately authorised, budgeted market probes for intended destinations. Public provider pages do not prove actual airline/property/POI coverage, route quality, forecast accuracy, or search recall.

## Architecture and ADR compatibility

No genuine contradiction with an accepted ADR was found. The research does expose three selection constraints:

- Direct Duffel, Hotelbeds, Expedia Rapid, or Booking.com booking endpoints must not expand Flash Trips into booking, payment, cancellation, or reservation management without a new domain/architecture decision.
- Google and Foursquare retention restrictions mean their raw responses cannot simply be copied into immutable Evidence or offline fixtures; an adapter must retain only contract-permitted provenance and validated facts.
- Short-lived or single-use URLs cannot satisfy ADR 0010’s required provider-link validity without deterministic revalidation and a documented replacement-link policy.

## Source-quality limitations

- This review used public primary sources only. It did not inspect account dashboards, signed partner agreements, negotiated rate cards, or region-specific contract addenda.
- Dynamic pricing and quota pages can change without versioning. Values above are a 2026-08-21 access snapshot and must be revalidated before implementation.
- Provider documentation establishes API behaviour and stated coverage, not observed data quality. No live call verified inventory, latency, accuracy, link lifetime, or destination coverage.
- Some providers publish technical documentation without complete licensing/retention terms. Those gaps are marked unknown rather than inferred.
- Government advisories are official for the issuing government’s audience; comparing their levels as though they were interchangeable would be a policy error.
