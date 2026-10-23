# HYSPLIT back-trajectories for Lahore: Phase 1 feasibility

Checked on 2026-10-21 from this laptop. Everything below was either observed directly
(commands run, NOAA ARL pages and directory listings fetched) or is labelled as
unverified. Nothing has been installed or bulk-downloaded yet.

## 1. This computer

| Item | Observed |
|---|---|
| OS | Microsoft Windows 11 Pro, 10.0.26300, 64-bit |
| CPU / RAM | Intel Core Ultra 7 155H / 31.5 GB |
| Free disk | C: 70 GB, D: 231 GB |
| Running as admin | No (standard user token) |
| Python | 3.15.0 (Microsoft Store alias `WindowsApps\python.exe`) |
| curl | `C:\WINDOWS\system32\curl.exe` (supports resumable `-C -`) |
| Existing HYSPLIT | None found (`C:\hysplit`, `C:\hysplit4` absent) |

**Location warning:** this folder is under `OneDrive\Desktop`. Putting the meteorology
files here would make OneDrive try to sync about 185 GB of them. I propose keeping only scripts and
results in `hysplit_lahore\` and putting the met files in `D:\hysplit_met\` (not synced,
and it has room). This needs your OK because you asked me to work only in `hysplit_lahore`.

## 2. Installing and running HYSPLIT (official NOAA ARL sources only)

- The download page is <https://www.ready.noaa.gov/HYSPLIT.php>, which links to the Windows
  "public, unregistered" version at <https://www.ready.noaa.gov/HYSPLIT_hytrial.php>.
- The page's download form posts to `/ready2-bin/gettrialhysplit.pl` with the file
  **`HYSPLIT_win32U.exe`**. It requires an **email address** and clicking **"I agree"** to
  the HYSPLIT Use Agreement (<https://www.ready.noaa.gov/HYSPLIT_agreement.php>).
  That means accepting a licence and submitting personal data, so **you need to do this step yourself**
  (or tell me explicitly to do it and give me the email to use).
- The trial page says the unregistered version is identical to the registered one,
  except that dispersion runs don't work with *forecast* met data. This doesn't affect
  archived-data trajectories.
- <https://www.ready.noaa.gov/HYSPLIT_util.php> says Tcl/Tk is needed **only for the GUI**.
  HYSPLIT can run from a command window, so Tcl/Tk and ImageMagick are not needed here.
- The user's guide says the installer puts "all code and executables" in the directory you
  choose. I expect the command-line trajectory program `hyts_std.exe` in `<install>\exec\`, but this
  is **unverified until installed**.
- **Version:** not determined yet. The updates page
  (<https://www.arl.noaa.gov/hysplit/hysplit-model-updates/>) returned HTTP 403 to my
  requests. The exact version will be recorded from the installed files and program output.
- **Admin rights:** not stated by NOAA. The installer may ask for elevation. If it does,
  I'll stop and ask you. Installing to a user-writable folder (e.g. `C:\hysplit` or
  `D:\hysplit`) may avoid that.
- How it runs: one `CONTROL` file per day (start time, receptor lat/lon/height, `-72` h,
  vertical motion 0, model top, the list of met files, the output name). Then run `hyts_std.exe` in
  a working directory. The output is a `tdump` endpoints file: one record per trajectory-hour
  with date, age, lat, lon, **height in m AGL**, and diagnostic variables. Per the guide
  (S263), the **first diagnostic is always PRESSURE**, so pressure will be available.
  Sources: user's guide sections S262 (CONTROL) and S263 (endpoints), at
  <https://www.ready.noaa.gov/hysplitusersguide/>.

## 3. Meteorology for 2019-04-01 to 2025-02-28 (+3 days of spin-up before the start)

A 72 h back-trajectory arriving 2019-04-01 06 UTC starts on 2019-03-29 06 UTC, so the
data must start 2019-03-29. All of these are global files: the ARL archive has no regional
subset to download, so the 25–40 N, 60–80 E box doesn't reduce the size.

| Dataset | Covers the whole period? | Files needed | Size (from NOAA listings / HEAD) |
|---|---|---|---|
| **GDAS 1°** (`/data/archives/gdas1/`) | **Yes** (archive Dec 2004 – present) | 352 weekly files, `gdas1.mar19.w5` … `gdas1.feb25.w4` | **185,142,145,280 bytes (185.1 GB, 172.4 GiB)**, exact, from an HTTP HEAD on each file |
| GDAS 0.5° (`/data/archives/gdas0p5/`) | **No**: last file is `20190611_gdas0p5`; ARL lists it as "no longer updated" (Sep 2007 – Jun 2019) | n/a | about 581 MB/day |
| GFS 0.25° (`/data/archives/gfs0p25/`) | **No**: first file is `20190613_gfs0p25`, so Mar–Jun 2019 is missing | 2,088 daily files for 2019-06-13 … 2025-02-28 | about **6.05 TB** (2.7–3.1 GB per day, rounded listing sizes) |
| **NCEP/NCAR Reanalysis 2.5°** (`/data/archives/reanalysis/`) | **Yes** (archive 1948 – 17 Mar 2026) | 72 monthly files, `RP201903.gbl` … `RP202502.gbl` | **8,705,115,904 bytes (8.7 GB, 8.1 GiB)**, exact, from an HTTP HEAD on each file |

Notes from the archive itself:
- GDAS1 file naming: `w1` = days 1–7, `w2` = 8–14, `w3` = 15–21, `w4` = 22–28, `w5` = 29–end of month
  (no `w5` in a 28-day February). All 352 required names appear in the listings. In ARL's
  `missing.txt` I found no documented gaps or errors for 2019–2025 (its newest note is
  about `gdas1.dec25.w5`, which is outside the range).
- NOAA publishes MD5 checksums (`listing.md5.txt`) for both GDAS1 and reanalysis. Every
  required file is in them, so each download can be verified against NOAA's MD5 as well as
  recorded with SHA-256.
- Reanalysis: the folder also holds `RP202501.gbl.bad`, so ARL replaced the January 2025 file.
  The current `RP202501.gbl` is the one to use.
- GDAS0.5 readme: since 2017-07-19 those files are short-term GFS forecasts without vertical
  velocity (shown here only to explain why it isn't recommended, besides the coverage gap).
- The per-file byte counts (all 352 GDAS1 + 72 reanalysis files) are in `remote_file_sizes.tsv`
  next to this report. The raw listings were downloaded to `%TEMP%\claude_hy\` and aren't copied here.

### Download time

Measured from this laptop on 2026-10-21:

| Test | Result |
|---|---|
| NOAA, `gdas1.apr19.w1`, ranged GET (with my slow size checks running at the same time) | 18.7 MB in 339 s, then the server reset the connection |
| NOAA, `gdas1.apr19.w2`, curl, 50 MB range, nothing else running | 9.2 MB in 180 s (hit the time limit): **51,152 B/s ≈ 0.41 Mbit/s** |
| Non-NOAA comparison (speed.cloudflare.com, 25 MB) | 25 MB in 33.4 s: **748,316 B/s ≈ 6.0 Mbit/s** |

So today the bottleneck is **NOAA's server**, at about 0.4 Mbit/s per connection. This laptop's own
link is about 6 Mbit/s. These are single short tests: NOAA's speed may change by time of day.

| Dataset | Exact size | at NOAA speed measured today (1 connection) | at the laptop's link ceiling (6.0 Mbit/s) |
|---|---|---|---|
| GDAS 1° | 185,142,145,280 B (185.1 GB) | about **42 days** | about **69 h (2.9 days)** |
| Reanalysis 2.5° | 8,705,115,904 B (8.7 GB) | about **47 h** | about **3.2 h** |

The ARL readme asks users to keep to **two or fewer concurrent connections**. Two connections
might roughly halve the NOAA-limited times (about 21 days / 24 h), but I haven't tested that. I'd
measure again at the start of Phase 2 and report the real rate.

## 4. Recommendation

1. **GDAS 1°** is the only finer-than-2.5° ARL dataset that covers the whole period on its own.
   It's the usual choice for regional back-trajectories over South Asia, and 1° is adequate for
   72 h synoptic-scale transport into Lahore.
2. **NCEP/NCAR Reanalysis 2.5°** is far smaller and covers the period, but it's coarse for terrain near
   the Himalaya and Sulaiman ranges and for boundary-layer arrival heights like 500 m. It's useful as
   a quick fallback or a sensitivity check.
3. GDAS 0.5° and GFS 0.25° can't cover the period alone. A GDAS0.5 + GFS0.25 mix would also
   change resolution mid-record and need about 6 TB.

**Storage option for GDAS1:** keep all files on `D:\hysplit_met\` (fits in the 231 GB free, leaving about 46 GB),
or stream them: download a week (plus the previous week for spin-up), verify, run that week's
trajectories, then delete. The manifest keeps the file name, size, NOAA MD5 and SHA-256 either
way, and any file can be fetched again (curl resume). Streaming needs only about 1.2 GB of disk at a time.

## Decision (2026-10-21)

The user chose **NCEP/NCAR Reanalysis 2.5°** (72 monthly files, `RP201903.gbl` … `RP202502.gbl`,
8,705,115,904 bytes), with met files stored in **`D:\hysplit_met\`**, outside OneDrive.
Each 72 h run uses the arrival month's file, plus the previous month's file when the start
falls in it (arrivals on days 1–3 of a month).

Run design (decided 2026-10-21): **one trajectory per day, arriving 06 UTC at 500 m AGL only**.
No extra heights or arrival times.

HYSPLIT: `HYSPLIT_win64U_v5.4.2.zip` from NOAA's download page, SHA1
`a032db8bcffca2edd5a72eff05d5989f66bb1ffd` (matches NOAA's published value), unzipped to
`C:\HYSPLIT` without admin rights. `hyts_std.exe` reports `hysplit.v5.4.2`.

## 5. Decisions that were needed (as asked in Phase 1)

1. Which met dataset: GDAS 1° (recommended), Reanalysis 2.5°, or both.
2. Where the met files go: `D:\hysplit_met\` (recommended, outside OneDrive) or inside `hysplit_lahore`.
3. Keep all met files or stream and delete them after use.
4. You'll download and install `HYSPLIT_win32U.exe` yourself from the trial page (email + "I agree"),
   or explicitly authorise me to submit that form with an email you give.
5. Phase 2 extras (I'll ask again before running): a second arrival height of **1500 m AGL**,
   above the typical winter mixed layer, which captures regional and long-range transport, and/or a
   second arrival time of **18 UTC** (23 PKT, nocturnal stable boundary layer, when Lahore
   PM2.5 often peaks). Each one doubles run count but adds no download.
