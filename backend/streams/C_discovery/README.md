# Offline Paris discovery

`DiscoveryService(LocalActivityRepository()).discover(profile, time_window, constraints)` accepts the actual `B_memory.CoupleProfile` snapshot and E's provisional `TimeWindow`, then returns E `CandidateActivity` objects sorted by profile-aware score. The activity repository is a protocol: future providers can supply normalized `ActivityListing` records without changing filtering or ranking.

The bundled JSON is an illustrative offline fixture, not live opening hours, inventory, prices, or a booking guarantee. Times are local `HH:MM`; weekdays use Monday=0. A listing must fit entirely in the window. `typical_budget` and `max_total_budget` are ceilings for **two** people; the lower ceiling applies. `include_types` is an exact type allowlist, all `required_tags` must match, and any `excluded_tags` rejects a listing. Couple and individual dislikes reject matching name/type/tag terms. Shared and individual interests raise ranking; recent activity names receive a novelty penalty. Ties sort by ID. Booking URLs pass through unchanged for human confirmation.

This direct E model output is provisional until the shared activity contract is finalized. No discovery call accesses the network.
