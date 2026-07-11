# CIRCL MISP OSINT observed source schema

Source inspected: `https://www.circl.lu/doc/misp/feed-osint/` on 2026-07-11.
The native feed directory, its `manifest.json`, and ten Event JSON documents
were inspected before implementation. The manifest contained 1,646 UUID keys
at inspection time. The directory also publishes `hashes.csv`.

Every inspected document had a top-level `Event` object. Observed Event keys
were `uuid`, `info`, `date`, `timestamp`, `publish_timestamp`, `published`,
`analysis`, `threat_level_id`, `extends_uuid`, `Orgc`, `Tag`, `Attribute`,
`Object`, and `EventReport`. `Object` and `EventReport` were not present in every
Event. No field is assumed to be universal except that a valid UUID is preferred
when present.

Observed Attribute keys included `uuid`, `type`, `category`, `value`, `comment`,
`timestamp`, `to_ids`, `deleted`, `disable_correlation`, `last_seen`, and nested
`Tag`. Observed Object keys included `uuid`, `name`, `meta-category`,
`description`, `template_uuid`, `template_version`, `comment`, `timestamp`,
`deleted`, `Attribute`, and `ObjectReference`. Object Attributes additionally
included `object_relation` and sometimes `data`. Event Reports contained `id`,
`uuid`, `event_id`, `name`, `content`, `timestamp`, and `deleted`.

Tags observed in the sample had `name`, `colour`, `local`, `exportable`, and
`relationship_type`, with fields varying by tag. Actor context is commonly
encoded as tag names such as `misp-galaxy:threat-actor="Packrat"` and
`misp-galaxy:mitre-enterprise-attack-intrusion-set="APT28"`; generic tags such
as `APT` also occur and are not treated as resolved actors.

HTTP Event responses exposed `ETag`, `Last-Modified`, and `Content-Length` in
the inspected sample. Raw response bytes are therefore authoritative, while
all normalized views are disposable and reproducible.
