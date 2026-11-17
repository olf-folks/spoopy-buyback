# Native deployment

Target: Debian 13, Python 3.13, PostgreSQL 17. Host: buyback.spoopy.net.

App: /srv/buyback/app. Virtualenv: /srv/buyback/venv.
Runtime secrets: /etc/buyback.env, root-owned mode 0600; loaded by systemd.
App service runs as buyback with Gunicorn bound to 127.0.0.1:8000.
Nginx is the only public app listener and overwrites X-Forwarded-Proto.
Use deploy/requirements.lock to reproduce the validated dependencies.
Celery and Redis have no active application tasks and are not needed.

Database initialization or restore must follow the owner's data decision.
Run migrations and collectstatic explicitly during a release, never on restart.
Create the administrator interactively using manage.py createsuperuser; no
predefined password is installed. Unknown item rates default to zero and need
staff review; an empty installation does not include historical pricing rules.

Before HTTPS issuance, DNS must route to 162.35.44.242. The HTTP ACME webroot
is /var/www/letsencrypt. After issuance, configure Nginx with the certificate,
redirect HTTP to HTTPS, and enable the certbot renewal timer and reload hook.
Secure cookies and HTTPS redirects are enabled in Django already.

Install backup.sh as /usr/local/sbin/buyback-backup and schedule it daily
once the database exists. It retains local PostgreSQL dumps for 14 days.
An independent offsite backup destination still needs to be configured.

Validation completed: Django deployment checks (only optional HSTS subdomain
and preload warnings), static collection, dependency consistency, SQLite
smoke tests, direct-origin ACME probe, and live pricing API request (HTTP 200).
PostgreSQL migrations, service startup, real HTTPS requests, admin account,
backup restore, and end-to-end appraisal remain pending deployment completion.


## Deployment status

Empty PostgreSQL database initialized with owner approval; migrations applied.
Gunicorn enabled and running. HTTPS certificate issued, Nginx redirect and
renewal reload hook installed. Public app, admin login and static CSS return
200. Staff user firmware has view/change permissions on buyback items.
Daily backups installed and restore verified in a temporary database.
No pending model migrations. Owner must configure actual buyback rates;
new catalog items default to zero. Offsite backup storage is not configured.

Pending item API updates run hourly at minute 7 via
/etc/cron.d/buyback-item-update. The root-owned wrapper loads runtime
configuration and runs Django as buyback, with a nonblocking lock and a
50-minute timeout. Logs: /var/log/buyback-item-update.log (rotated weekly).

## CCP catalog import

Official source: https://developers.eveonline.com/static-data/
Downloaded JSONL archive: /srv/buyback/sde/latest-jsonl.zip.
Imported build 3698585 (2026-11-13), SHA256:
afda59ef777c8e89ef7c6864dd5e103e4b75455ab158f370b780c8f6e0826649.

Run manage.py import_sde ARCHIVE --dry-run to preview. Omit --dry-run to
apply transactionally. Only published types are newly inserted. Existing
rows (including types absent from the export) are retained. Metadata fields
are updated; existing rates, flat costs, hauling fees and review flags are
preserved. New items start at zero rate/cost with needs_review=True and
needs_update=False. This imports reference metadata, not market prices.

Initial import inserted 27,125 rows for 27,490 total. Verified all 365
previous rows retained their business configuration, both staff accounts
still access admin/tax editors, and a second dry run reports zero changes.
No duplicates or missing group/category names. Pre/post backups taken and
post-import dump restored successfully into a temporary database.

Catalog, category tree and group item listings paginate 200 items per page.
Group-wide pricing submissions still apply to the entire selected group.
The existing category tree's list and template errors were repaired.

## Staff market tax editor

Staff opens /buyback/tax_edit/ with native collapsible CCP market branches.
MarketGroup/MarketType reference tables (migration 0008) are independent of
item rates. Load/refresh via manage.py import_market_menu ARCHIVE [--dry-run].
The importer validates parent references/cycles and preserves business rows.
Items lacking market mappings remain accessible under Outside the market.

A branch includes its descendants. Search narrows the selected branch;
bulk actions affect every matching item across all pages, not just visible
rows. Rate input uses percent units: 90 saves 0.9. Flat price zero enables
percentage pricing; nonzero flat price overrides it. Legacy inventory group
URLs remain available. The admin filter sidebar is unchanged.

Validated 10 automated tests, migration drift check, production staff access,
public HTTPS menu and CSRF POST on empty selection, plus static/public app
checks. Source rollback archive: /var/backups/buyback/releases/before-market-editor.tar.gz.

Individual market-editor item links open a matching staff item form with Jita
percentage, flat price, hauling fee and needs-review settings. Save/cancel
returns to the originating branch, search and page. Item metadata is read-only.
Bulk review status supports both Needs review and Reviewed for the entire
matching selection across pages.

2026-11-14: item/review changes deployed. All 13 isolated tests passed; live
HTTPS custom item editor and bulk review UI verified for both staff accounts.
No migration drift or production item changes during verification. App/database
backed up before deployment. See CHECKPOINT.md for rollback details.

## EVE login and alliance pricing (2026-11-14)

EVE SSO uses authorization code with PKCE and no private-data scopes. Configure
an EVE developer application with the exact callback:
https://buyback.spoopy.net/buyback/auth/eve/callback/

Runtime settings in /etc/buyback.env:
- EVE_LOGIN_ENABLED=True
- EVE_SSO_CLIENT_ID=<registered client ID>
- EVE_SSO_CALLBACK_URL=https://buyback.spoopy.net/buyback/auth/eve/callback/
- EVE_ALLIANCE_IDS=99003214,99010079 (Brave Collective, Brave United)
- EVE_REQUIRE_LOGIN=False (guests allowed)

Verified Brave characters receive existing jita_buy_percentage values. Guests
and other characters receive the outsider_jita_buy_percentage stored on each
item. Staff edits percentages per item or bulk selection. Rates are required;
zero is an explicit zero. Flat prices apply only to verified Spoopy Newbies members; other players use
their item percentage. Hauling behavior is unchanged. Newly discovered items inherit
the outsider default while their alliance rate retains existing zero behavior.

Alliance membership is read server-side from ESI characters/affiliation on each
appraisal request. ESI outages block quotes for logged-in characters rather than
reuse stale membership or silently switch rates; users can log out for guest
pricing. SSO verifies state/PKCE and JWT signature, issuer, both audiences, expiry,
and character subject. Access/refresh tokens are discarded after ordinary identity login. Separate
staff contract authorization stores encrypted tokens as described below. EVE
sessions do not grant Django staff access. EVE logout requires a CSRF-protected
POST and preserves a separate staff login. Appraisal/auth responses disable
caching. Scope-free PKCE must be supported by the registered EVE application.

Migration 0009 adds a nullable outsider rate; existing business values/accounts
were verified unchanged across migration. 27 isolated tests passed, plus live
HTTPS guest 85% appraisal, EVE login redirect, real ESI lookups for both alliances,
and both staff editors. Full player login/callback still needs a real browser
login. Predeployment app/environment backups are under
/var/backups/buyback/releases/before-eve-login-20261114.*; database dumps exist
before and after deployment. Dependency lock includes PyJWT/cryptography.

## Spoopy Newbies corporation tier (2026-11-14)

EVE_SPECIAL_CORPORATION_ID=98472700 is configured in the runtime environment. Eligibility uses corporation_id from the same ESI
affiliation response as alliance membership. Priority: Spoopy Newbies, then
Brave alliance, then outsider/guest. Corp membership takes precedence even if
the corporation changes alliance. Staff can set corp_jita_buy_percentage per
item or scoped bulk selection; rates are stored explicitly and zero remains
zero. Corp and outsider rates are independent. Flat overrides apply only to verified Spoopy Newbies members.

Migration 0010 adds a nullable corporation rate. Before/after fingerprints
verified existing item fields and accounts were preserved. 30 tests passed;
live ESI corporation lookup and both staff editors verified, guest appraisal
still 85%. Predeployment app/env backups:
/var/backups/buyback/releases/before-corp-tier-20261114.*. Pre/post DB backups
also taken. No item settings changed solely for live validation.


## Rates stored on every item (2026-11-14, current behavior)

User clarified that percentages must be written on every item. Migration 0011
filled only null corp_jita_buy_percentage and outsider_jita_buy_percentage with
0.85 across all 27,490 items; previous custom values, alliance rates, other item
fields and accounts were preserved. Both columns are now NOT NULL, with a
PostgreSQL insert default of 0.85 for new items. Pricing reads each item's stored
values directly; no environment/configuration fallback remains. Removed
EVE_CORP_PERCENTAGE/EVE_OUTSIDER_PERCENTAGE from settings and live environment.
There is no global defaults table. Staff forms require explicit percentages;
blank no longer means inheritance/reset. New SDE catalog entries receive stored
rates from the database's insert defaults. Existing rows retain their settings.

31 isolated tests passed, including an old-environment-values-ignored check.
Production full-row comparison matched exactly the expected null-only fills.
Live guest appraisal remains 85%; ESI, staff editors and services verified.
Rollback app/env: /var/backups/buyback/releases/before-stored-item-rates-20261114.*.
Database backups taken before and after migration.


## Corporation contract queue (2026-11-14)

Receiver: Spoopy Buyback corporation, ESI ID 98475239. Staff queue:
/buyback/staff/contracts/. Connect uses the existing callback and a separate
staff-bound PKCE flow requesting only esi-contracts.read_corporation_contracts.v1.
Regular appraisal login stays scope-free. The character must belong to Spoopy
Buyback; ESI confirms the necessary corporation roles before credentials are
saved. SSO consent was completed and real syncing validated successfully.

Migration 0012 adds ContractConnection and BuybackContract independently of item
pricing. Access/refresh tokens are Fernet-encrypted in the database with
EVE_TOKEN_ENCRYPTION_KEY in /etc/buyback.env (0600). Keep this key with protected
configuration backups; do not regenerate it while authorizations are stored.
Initial key-inclusive env backup:
/var/backups/buyback/releases/with-contract-token-key-20261114.env. No tokens or
keys are stored in source or rendered in pages. Refresh-token rotation is
serialized and committed before later ESI calls, preserving rotated credentials
when subsequent fetches fail. Disconnect removes credentials, keeping snapshots.

buyback-contract-sync.timer runs every 10 minutes; oneshot service runs as
buyback. Manual Refresh contracts is also available. Management command:
manage.py sync_buyback_contracts. With no authorization it exits successfully.
Incoming item-exchange contracts assigned to the receiving corporation are
saved across all ESI pages; page errors leave snapshots untouched. ESI normally
returns the past 30 days plus contracts in progress; older saved records remain,
with snapshot times displayed. No EVE contracts/payments are modified.

Queue/detail show resolved issuer names via public /universe/names, batched and
cached for 24 hours, with Unknown issuer (ID) on resolution failure. Detail loads
contract items and uses local catalog names. Contract/appraisal matching, asset
selection and wallet reconciliation are not implemented; no such private scopes
are requested. All contract routes require Django staff access and mutations
require CSRF-protected POSTs. Responses disable caching.

45 isolated tests pass. Live sync fetched 10 incoming contracts and resolved
all 5 issuers. Live staff queue/details, regular scope-free login, encrypted
connection authorization and service/timer verified. Backups before schema/app
changes and after real sync. Rollback archives:
/var/backups/buyback/releases/before-contracts-20261114.tar.gz and
/var/backups/buyback/releases/before-public-style-20261114.tar.gz.

## Public styling and flat-price eligibility (2026-11-14)

Main buyback uses tax-editor.css plus scoped buyback.css/buyback.js: matching
header, dark panels, responsive inventory form, summary, copy button and item
breakdown. Includes user-supplied default/member-rate copy and four acceptance
locations below the SSO button. Desktop (1440px) and phone (390px) rendering,
clipboard, notes and live appraisal checked in Chromium with no JS errors or
horizontal overflow. Corp-only flat prices show Flat price in item breakdown.
Alliance/outsider/guest appraisals ignore flat overrides and use their stored
item percentages. Staff forms/help text identify the corporation restriction.
Existing database prices and accounts were preserved throughout deployment.

## Navigation, classic UI and review browsing (2026-11-14)

Modern app pages use site_header.html/site-header.css for a consistent logo and
navbar. EVE login/logout and the verified character name are in the navbar;
when only Django staff login exists, the staff username is shown. Tax editor
and Contracts links require active staff, and server routes remain protected.
Shared navigation is also included on older utility/login app pages.

Old UI / New UI switches set buyback_ui in the current browser session, retaining
EVE identity. This is not a global setting or an account preference across
browsers. Classic mode intentionally hides the modern navbar, restores the
original large SPOOPY BUYBACK banner and two images, and uses its own top login/
logout/name/New UI controls. LegacyItemForm restores the original 96px textarea,
#303030 background and original gold text; modern textarea styling is isolated.
Submit/Clear/Staff occupy one row directly under the classic textbox; Staff is
only rendered for staff. Both layouts retain current pricing, notes and copy.

Market sidebar red dots indicate needs_review items in a group or any descendant.
Accessible labels/tooltips give the count. All items/Outside the market also
show indicators. Needs review only filters the item list and bulk-action scope;
it persists through branch navigation, search, pagination and item return links.
Marking items Reviewed clears corresponding dots on the next render. No pricing
or review flags were changed solely to verify the feature on production.

50 isolated tests passed, plus real desktop/mobile Chromium checks of navigation,
name display, restricted links, classic colors/height/button positions/banner,
old/new session isolation, real legacy submission/copy, and review filter/tree.
No migrations. Before-change backups:
/var/backups/buyback/releases/before-navigation-review-20261114.tar.gz and
/var/backups/buyback/releases/before-authbar-legacy-20261114.tar.gz.

Review-status selection fix: the bulk control now reads the complete matching
selection's saved Boolean values on every GET/reload. All reviewed selects
Reviewed; all pending selects Needs review; differing flags or no matches leave
Choose review status selected. The placeholder is not a third stored state and
cannot be submitted to modify rows. Individual item checkbox reflects its saved
flag. 51 tests passed, including both transitions and empty-action rejection;
live HTTPS reviewed/pending selections verified without changing flags.
Rollback subset: /var/backups/buyback/releases/before-review-select-20261114.tar.gz.
