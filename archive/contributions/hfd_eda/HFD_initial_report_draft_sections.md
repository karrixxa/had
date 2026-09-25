# HFD Rail Crossing Project: Draft Sections for the Initial Report

Draft text for Sections 3 (Data Description), 4 (Pipeline overview), 4.1 (Data Wrangling), talking points for 4.2 (Data Exploration), and Appendix 6.1 (Variable Definitions). Figures referenced as `figX_*.png` are in the `figures/` folder. Figures `fig1`–`fig8` come from Peikun's `eda.py`; `fig0` and `figA`–`figG` are new. Figure numbers below are placeholders; renumber once the final order is set.

---

## Fixes needed in the current shared draft

These are worth correcting before submission, since the rubric deducts for errors and unclear content.

1. **Section 3.2 is out of date.** It describes "7 sensors, as well as traffic data from an additional 42 crossings" from "August 2023 to January 2025." That is the previous D2K team's data. Our export has 67 sensor IDs, 285,263 records, and runs from 7 September 2022 to 20 September 2026 (replacement text is below).
2. **Section 3 opening paragraph has a broken sentence** ("Department of Transportation crossing inventory and only has 3 useful information…" and "We also received data from our sponsor Leonard Chan who" trails off).
3. **Appendix 6.1 still contains template text** ("Soma", "Cell body (contains cell nucleus)", "Input terminal"). Replacement tables are at the end of this file.
4. **Section 1.2 bullets are broken across lines** (for example "which are" / "not, and investigate…" became separate bullets), and "Target Variable (Y)" is a stray bullet.
5. **Section 3.3 Limitations and Section 5.2 Future Work are empty.** Draft text for 3.3 is below.
6. **Literature review cites unrelated work** (digit recognition in natural images, deep belief networks). Nick may want to swap these for work on grade-crossing blockage prediction (for example the Federal Railroad Administration i-CATSS report Peikun cites), binary time-series forecasting, and Brier-score evaluation.
7. **Acronyms** such as HFD, FRA, CAD, ERF, EMS, and IoT need to be spelled out at first use (rubric item).

---

## 3 Data Description

### 3.1 TRAINFO Crossing Blockage Data

The primary dataset is a record of blocked at-grade rail crossings collected by TRAINFO, a company that installs roadside sensors to detect when a train occupies a crossing. The sensors were deployed as part of the City of Houston's Smart Railroad Crossings project, funded through the Federal Railroad Administration (FRA). Each row of the export describes one blockage: the crossing's FRA identification number, the street name, the date and clock time at which the blockage began, and its duration in minutes. Blockage end times, the gaps between consecutive blockages, and the minute-by-minute state of each crossing can all be derived from these fields.

The full export used in this report was downloaded on 20 September 2026. It contains 285,263 records from 67 FRA identification numbers, spanning 7 September 2022 to 20 September 2026. Two pairs of identification numbers report identical records (the two Tidwell Road IDs and the two Telephone Road IDs), so the export represents 65 distinct sensor feeds. Figure A shows that the network grew in two stages. Seven crossings east of downtown Houston have reported since 2022 or early 2023, while almost all remaining sensors began reporting in late June 2024. Many of the newer sensors report intermittently, with gaps of one or more months.

> **Figure A** (`figA_network_coverage.png`). Monthly number of blockage records for every TRAINFO sensor in Houston. Each row is one crossing and each column is one calendar month; darker blue means more records, and grey means no records that month. The eight study crossings (orange labels, above the orange line) have the longest and most complete histories. Most other sensors begin reporting in late June 2024 (dashed line) and have frequent gaps.

Across the full export, the raw durations also show quality problems that motivate the cleaning described in Section 4.1: 487 records have negative durations, 210 records last longer than 24 hours, and the longest single record lasts 21,902 minutes (about 15 days), which cannot be a real train occupying a crossing. Most times are recorded to the minute, but 7,508 records (including all Telephone Road records) are recorded to the second.

### 3.2 The Eight Study Crossings

Following our mentors' direction, the initial analysis focuses on the eight crossings shown on TRAINFO's main Houston page: Market Street, Hirsch Road, Commerce Street, York Street, Lockwood Street, Leeland Street, Polk Street, and Telephone Road. They lie within about 6 kilometers of one another east of downtown Houston, on four Union Pacific rail lines and one industrial side track (Figure 1). Seven of them are the only crossings in the network that were reporting before mid-2024, giving them three and a half to four years of history compared with at most about two years elsewhere. That length is what makes a time-ordered training and testing design possible. Together they contribute 153,141 records (54% of the full export) and cover 7 September 2022 to 20 September 2026. Their records in the eight-crossing file match the full export row for row. Table 1 summarizes each crossing after cleaning.

> **Figure 1** (`fig1_map.png`, Peikun). Locations of the eight study crossings. Circle size shows the average number of minutes each crossing is blocked per day. Dark grey lines are railroad tracks and light lines are major roads (OpenStreetMap). Orange arrows show pairs of crossings where a blockage at the first is usually followed by a blockage at the second a few minutes later.

**Table 1.** Summary of the eight study crossings after cleaning. "Days with data" excludes sensor outages and fault days. "Rail line" is the nearest Union Pacific line in OpenStreetMap.

| Crossing | FRA ID | Rail line | Days with data | Blockages | Median length (min) | Longer than 30 min | Blocked min per day |
|---|---|---|---|---|---|---|---|
| Market Street | 755709E | Strang Subdivision | 1,303 | 20,259 | 6.5 | 7.1% | 194 |
| Hirsch Road | 755640L | Industrial spur | 1,100 | 7,989 | 12.8 | 25.8% | 207 |
| Commerce Street | 288129A | West Belt | 1,470 | 34,783 | 7.0 | 2.5% | 223 |
| York Street | 859517C | Galveston Subdivision | 1,430 | 12,455 | 6.5 | 4.6% | 90 |
| Lockwood Street | 859523F | Galveston Subdivision | 1,460 | 11,347 | 8.0 | 7.3% | 107 |
| Leeland Street | 288224V | West Belt | 1,209 | 26,795 | 5.9 | 4.3% | 209 |
| Polk Street | 288039B | East Belt | 1,371 | 14,780 | 4.4 | 4.8% | 106 |
| Telephone Road | 288051H | East Belt | 306 | 2,023 | 3.7 | 4.4% | 71 |

### 3.3 Houston Fire Department Data

*(Keep the existing Section 3.1 text on dispatch records, station profiles, district profiles, call types, and train delay reports, with acronyms spelled out. Add one sentence making clear its role:)* These records come from the earlier D2K projects with the Houston Fire Department. They are not inputs to the forecasting model, but they provide context on where and how often blockages have delayed responses, and they can later be used to prioritize which crossings matter most for dispatch.

### 3.4 Supplementary Data

Rail line and road geometry for the study area were downloaded from OpenStreetMap and stored with the project (`osm_rail_roads.json`). They are used to assign each crossing to a rail line and to check that crossings whose blockages are statistically linked are in fact connected by track. Candidate additions for later in the semester are the FRA grade crossing inventory (train counts, track counts, and gate type for each crossing), a holiday calendar, and hourly weather.

### 3.5 Limitations of the Data

Several properties of the data limit what can be concluded from it. First, a record only tells us that a sensor detected a blockage. We have not yet confirmed with TRAINFO whether a blockage means that gate arms were down or that a train was physically on the crossing, and these can differ by a minute or more. Second, the export records blockages but not "all clear" messages, so a long period with no records could mean either that no trains passed or that the sensor was not reporting; Section 4.1 describes how we separate the two. Third, the sensors occasionally malfunction, producing bursts of very short false blockages or single records lasting days. Fourth, traffic levels shift over time: four crossings are blocked 28% to 44% less often after mid-2025 than before, and we cannot tell from the data alone whether this reflects real changes in rail operations or changes to the sensors. Finally, the eight study crossings are a small, closely spaced part of the city, so conclusions about them may not transfer to crossings elsewhere in Houston.

---

## 4 Data Science Pipeline

The pipeline turns raw TRAINFO blockage records into a clean, minute-by-minute record of whether each crossing is blocked, and then uses that record to forecast whether a crossing will be blocked 5, 10, 15, or 30 minutes ahead. It has five stages (Figure 0). Data wrangling removes errors, joins records that belong to the same train, and marks periods when a sensor was not reporting. Exploration measures the patterns a model could use, such as how long blockages last, how blockages travel between crossings, and how traffic changes over time. Modeling starts from two simple baselines and adds complexity only when it improves forecasts on held-out data. Evaluation uses a strictly time-ordered train, validation, and test split and reports results for each crossing as well as overall.

> **Figure 0** (`fig0_pipeline.png`). Overview of the data science pipeline, from raw sensor records to evaluated forecasts.

---

## 4.1 Data Wrangling

All cleaning is implemented in two scripts, `prepare.py` and `eda.py`, so every number in this section can be regenerated from the raw export in a few minutes.

### 4.1.1 Restructuring the Raw Export

The raw eight-crossing file repeats each crossing's name, coordinates, Google Maps link, and TRAINFO source link on every one of its 153,141 rows. We split it into two tidy tables: a station table with one row per crossing (identifier, name, coordinates, and source link) and an event table with one row per blockage record (crossing, start time, duration, and derived end time). The two tables are linked by the FRA identification number. The Google Maps link and source link are kept only in the station table, since they carry no information about blockages.

Start times are built by combining the date and clock-time columns. Telephone Road records times to the second (for example 18:46:06) while the other seven crossings record only hours and minutes. A parser that assumes a single format silently discards all 2,113 Telephone Road rows, so we parse the two formats separately and keep a flag recording which resolution each row uses.

### 4.1.2 Duplicates and Invalid Values

We removed 119 rows that exactly duplicated another row (same crossing, start time, and duration). Eighteen records had slightly negative durations (as low as −0.15 minutes); these were set to zero and flagged rather than deleted, because the start time is still valid evidence that a train was present. We also flag, but keep, records that share a start time with another record at the same crossing and records that begin before the previous record at that crossing has ended.

### 4.1.3 Joining Records That Belong to One Train

The sensors sometimes report a single train as several short records a few seconds apart. The problem is worst at York Street, where 47% of raw records last less than one minute. We therefore join consecutive records at the same crossing into one blockage episode whenever the crossing was clear for 2 minutes or less between them. This reduces 153,022 records to 131,799 episodes. Figure B shows a typical hour at York Street before and after joining.

> **Figure B** (`figB_wrangling_example.png`). A worked example of the wrangling steps for one hour at York Street. (a) Seven raw sensor records, several lasting under a minute and separated by seconds. (b) After joining records separated by 2 minutes or less, three blockage episodes remain; the label above each shows how many raw records it contains. (c) The resulting minute-by-minute blocked or clear state, which is the quantity the models will predict.

A small number of episodes are built from very many records: 145 episodes contain 20 or more records (up to 426), mostly at York Street, and typically last 45 to 85 minutes. These may be a slow or stopped train that repeatedly triggers the sensor, or they may be sensor "chatter." We keep them but retain the number of joined records as a variable so they can be examined or excluded later.

### 4.1.4 Missing Data: Sensor Outages and Fault Days

The export contains only blockages, so missing data does not appear as empty cells. It appears as long periods with no records at all. Because a busy crossing is almost never clear for a full day, we treat any interval longer than 24 hours without a record as a sensor outage rather than as a period with no trains. This rule identifies 128 outages covering 565 crossing-days; the longest is a 121-day outage at Hirsch Road. Outage periods are marked as unobserved and are excluded from all statistics and from model training and testing, rather than being filled in. Imputing them would invent train traffic that never occurred.

The opposite problem also occurs. From 25 to 28 February 2025, the Hirsch Road sensor reported 1,243 blockages of about 40 seconds each, roughly 50 times its normal daily count. We flag any day on which a crossing's episode count exceeds three times its rolling 29-day median and more than half of the episodes are shorter than one minute. This rule flags those four days at Hirsch Road plus three single days at York Street; the 1,351 episodes on these seven days are excluded.

Peikun's week-by-week coverage chart (Figure 2) shows the result. Commerce and Lockwood report almost continuously, Hirsch and Leeland have gaps of several months, Telephone begins only in May 2025, and Market stops reporting in April 2026.

> **Figure 2** (`fig2_coverage.png`, Peikun). Average blockages per day at each crossing, computed week by week. Grey cells are weeks in which the sensor was not reporting for at least half the week.

### 4.1.5 Timestamps and Daylight Saving Time

The timestamps carry no time zone. We tested whether they are local Houston clock time by counting records during the hour that does not exist when clocks move forward in March. On all four "spring forward" Sundays in the data (2023 to 2026), there are zero records between 2:00 and 3:00 a.m., although the eight crossings average 4.2 records in that hour on a typical day. If the clock did not skip that hour, the chance of seeing zero records on all four days would be about 5 in 100 million. On the four "fall back" Sundays, the repeated 1:00 a.m. hour contains 5 to 12 records compared with 4.6 on a typical day, as expected when that hour occurs twice. We conclude that timestamps are local Central Time with daylight saving time applied. The modeling data will convert all times to Coordinated Universal Time so that every minute is unique, which affects only the four repeated hours in the record.

### 4.1.6 New Variables: The Minute-by-Minute Crossing State

Forecasting requires the state of every crossing at every minute, not a list of blockages. We therefore build a grid with one row per crossing and one column per minute from 7 September 2022 to 21 September 2026 (8 crossings × 2,124,000 minutes). Each cell records two values: whether the crossing was blocked during any part of that minute, and whether its sensor was reporting at that minute (not in an outage or fault day, and within the sensor's active period). The prediction target for horizon *h* is the blocked state *h* minutes after the forecast time, for *h* = 5, 10, 15, and 30. A training example is used only when the sensor is reporting both at the forecast time and at the target time.

From the grid and the episode table we derive the features planned for modeling: whether the crossing is blocked now; how long the current blockage or clear spell has lasted; the time since the last blockage started; the same state variables for every other crossing, with emphasis on crossings upstream on the same track; the hour of the day, day of the week, and a holiday indicator; each crossing's historical blocked rate for that hour of the week, computed from training data only; and rolling blockage counts over the previous 1, 6, and 24 hours. Full definitions are given in Appendix 6.1.

### 4.1.7 Checking That the Cleaning Choices Do Not Drive the Results

The 2-minute joining gap and the 24-hour outage threshold are judgment calls, so we repeated the cleaning with other values (Figure C). Joining matters a great deal at York Street, where the median blockage length jumps from 1.6 minutes with no joining to 6.3 minutes with a 1-minute gap, but changes little between 1, 2, and 5 minutes at most crossings; Hirsch Road is the main exception. The outage threshold matters more: a 12-hour rule marks 1,228 crossing-days as outages, the 24-hour rule 565, and a 48-hour rule 471. The 24-hour rule sits near the point where the curves flatten, which suggests it separates real outages from ordinary quiet nights. Telephone Road is the exception because it averages only about four blockages a day, so some of its "outages" may be genuine quiet periods.

> **Figure C** (`figC_sensitivity.png`). Sensitivity of the cleaned data to two cleaning choices. (a) Number of blockage episodes as a percentage of the count with no joining, for joining gaps of 0, 1, 2, and 5 minutes. (b) Median blockage length for the same gaps. (c) Total days marked as sensor outages for thresholds of 6, 12, 24, and 48 hours. The dotted line marks the value used in this report.

### 4.1.8 Class Balance and the Train, Validation, and Test Split

Blocked minutes are the minority class. Across all reporting minutes, crossings are blocked 10.9% of the time, ranging from 4.9% at Telephone Road to 15.5% at Commerce Street (Figure D, panel a). The current state is highly informative for a few minutes and then fades (panel b). A crossing blocked now is still blocked 5 minutes later 51% to 85% of the time, depending on the crossing, but 30 minutes later only 21% to 48% of the time, approaching its long-run average.

> **Figure D** (`figD_target.png`). The prediction target. (a) Percentage of reporting minutes during which each crossing is blocked. (b) Chance that a crossing is blocked a given number of minutes later, starting from a blocked crossing (solid lines) or a clear crossing (dashed lines). The gap between the two sets of lines shrinks quickly over the first 30 minutes, which is why the current state alone supports only short-range forecasts.

To prevent the model from learning from the future, we split the data by time rather than at random: training from September 2022 through December 2024, validation from January through June 2025, and testing from July 2025 through September 2026. The test period matches the one used in Peikun's preliminary forecasting test. Table 2 shows the observed days in each period. Telephone Road has no training data, so it will either be evaluated with a model shared across crossings or reported separately.

**Table 2.** Days of reporting data per crossing in each period.

| Crossing | Training (Sep 2022–Dec 2024) | Validation (Jan–Jun 2025) | Test (Jul 2025–Sep 2026) |
|---|---|---|---|
| Market | 832 | 181 | 290 |
| Hirsch | 482 | 175 | 443 |
| Commerce | 842 | 181 | 447 |
| York | 835 | 181 | 414 |
| Lockwood | 845 | 168 | 447 |
| Leeland | 581 | 181 | 447 |
| Polk | 752 | 174 | 445 |
| Telephone | 0 | 19 | 287 |

The split also exposes a shift in traffic levels over time (Figure G). Average blocked minutes per day fall between the training and test periods by 44% at Polk Street (131 to 74), 37% at York Street (99 to 62), 30% at Lockwood Street (122 to 86), and 28% at Hirsch Road (252 to 181), while Commerce and Leeland change by less than 10%. A model trained on earlier years will therefore tend to over-predict blockages at these crossings unless it can adapt. This motivates two design choices: using recent-history features (rolling counts) rather than relying only on long-run averages, and checking probability calibration on the test period.

> **Figure G** (`figG_monthly.png`). Average minutes blocked per day at each crossing, month by month. Shading marks the validation (blue) and test (orange) periods; dashed lines show the average over the training and test periods. Several crossings are blocked noticeably less often in the test period than in training.

### 4.1.9 Data Volume After Wrangling

**Table 3.** Data volume at each wrangling step (eight study crossings).

| Step | Count |
|---|---|
| Raw rows | 153,141 |
| After removing exact duplicates | 153,022 |
| Blockage episodes after joining records 2 minutes or less apart | 131,799 |
| Episodes on flagged sensor-fault days (excluded) | 1,351 |
| Episodes kept for analysis | 130,448 |
| Sensor-outage intervals (more than 24 hours without a record) | 128 (565 crossing-days) |
| Minute grid | 8 crossings × 2,124,000 minutes |
| Crossing-minutes with the sensor reporting | 13,892,538 (81.8% of the grid) |
| ...of which blocked | 1,510,412 (10.9%) |

---

## 4.2 Data Exploration: Talking Points for Dylan

These are the findings Peikun's analysis and the new figures support. Each could anchor a subsection.

**How long blockages last (Figure 3, Figure 4; Peikun).** A typical blockage lasts 4 to 8 minutes, about the time a freight train takes to pass. Hirsch Road is the outlier (median 12.8 minutes, a quarter longer than 30 minutes) because it sits on an industrial side track where trains are assembled. The most useful result is the remaining-wait curve: at most crossings, blockages that have lasted under 10 minutes usually clear within 3 to 8 more minutes, but one that has lasted 20 minutes typically has another 9 to 28 to go. This supports a simple rule for dispatchers: wait if the train just arrived, and reroute if it has been there for more than about 10 minutes.

**Time of day and day of week (Figure 5, Peikun; Figure F, new).** Freight trains run around the clock, so calendar effects are weak. Every crossing is blocked at least 3% of the time in every hour. By day of week, most crossings vary by less than 10% around their own average (York Street by only 3%), so day of week will be a weak feature. The exceptions are Hirsch Road (Fridays about 17% above average) and Telephone Road, whose day-to-day differences mostly reflect its small sample.

> **Figure F** (`figF_dayofweek.png`). Percentage of time each crossing is blocked on each day of the week (numbers in cells). Color shows how far each value is above (orange) or below (blue) that crossing's own average, so patterns within a row are visible even though crossings differ in overall traffic.

**Blockages travel along the track (Figure 6, Figure 7; Peikun).** A blockage at one crossing is often followed by one at a connected crossing a few minutes later. The strongest link is York to Lockwood: 5 minutes after York is blocked, Lockwood is 36 times more likely than usual to become blocked, and 56% of York blockages are followed by a Lockwood blockage within 2 to 8 minutes. Only the six pairs connected by track show strong links, and the delays add up along the track (Commerce to York about 6 minutes, York to Lockwood about 5, Commerce to Lockwood about 10). When all eight sensors were reporting, at least two crossings were blocked at the same time 18% of the time, which matters for anyone planning a detour.

**What happens after a crossing clears (Figure E, new).** The chance of a new blockage in the next 10 minutes depends on how long a crossing has been clear, and the pattern differs by crossing. At Leeland Street, trains arrive in clusters: right after clearing there is a 27% chance of another blockage within 10 minutes, which falls to about 13% after an hour. Commerce and Lockwood show the opposite: the chance is lowest right after a train passes (17% and 2%) and peaks 10 to 15 minutes later (22% and 8%), consistent with trains being spaced apart on the line. This means "time since the last blockage" is a useful feature and should be allowed to act differently at each crossing.

> **Figure E** (`figE_reblock.png`). Chance that a new blockage starts within the next 10 minutes, given how long the crossing has already been clear. Flat lines would mean past clear time carries no information; the rising and falling curves show that it does, in different ways at different crossings.

**How far ahead is prediction possible (Figure 8, Peikun; Figure D, new).** In a preliminary test with gradient-boosted trees, forecasts beat the time-of-week average clearly at 5 minutes, modestly at 10 to 15 minutes, and barely at 30 minutes. Adding the state of the other seven crossings helps most where there is a strong upstream link: Lockwood's 10-minute skill rises from 0.06 to 0.24 when York's state is included. Figure D shows why the useful horizon is short: the information in the current state fades quickly over the first 30 minutes.

**Data quality (Figures A, 2, C, G).** Coverage gaps, the Hirsch fault days, the chatter episodes, and the drop in traffic after mid-2025 are all exploration findings as well as wrangling issues.

---

## 6.1 Appendix: Variable Definitions

**Table A1. Station table** (one row per crossing, 8 rows).

| Variable | Type | Description |
|---|---|---|
| FRA ID | Text | Federal Railroad Administration crossing identification number; primary key |
| Name | Text | Street name of the crossing |
| Short name | Text | Short label used in figures (for example "York") |
| Latitude, Longitude | Decimal | Crossing location in degrees |
| TRAINFO source link | Text | Web address of the crossing's TRAINFO export |

**Table A2. Event table** (one row per raw record after removing duplicates, 153,022 rows).

| Variable | Type | Description |
|---|---|---|
| FRA ID, Name | Text | Crossing (links to the station table) |
| Start | Date and time | Local time at which the sensor reported the crossing blocked |
| Duration | Decimal (minutes) | Reported length of the blockage; negative values set to zero |
| End | Date and time | Start plus duration |
| Time resolution | Category | Whether the start time was recorded to the minute or the second |
| Gap to previous record | Decimal (minutes) | Minutes between the end of the previous record and the start of this one at the same crossing |
| Negative-duration flag | Yes/No | Original duration was below zero |
| Same-start flag | Yes/No | Another record at this crossing has the same start time |
| Overlap flag | Yes/No | Record starts more than one minute before the previous record ended |

**Table A3. Episode table** (one row per blockage after joining, 131,799 rows).

| Variable | Type | Description |
|---|---|---|
| FRA ID, Name | Text | Crossing |
| Start, End | Date and time | Start of the first joined record and latest end among the joined records |
| Records joined | Integer | Number of raw records combined into this episode |
| Duration | Decimal (minutes) | End minus start |

**Table A4. Outage table** (one row per unobserved interval, 135 rows).

| Variable | Type | Description |
|---|---|---|
| FRA ID, Name | Text | Crossing |
| Interval start, Interval end | Date and time | Period treated as unobserved |
| Kind | Category | "Gap" (no record for more than 24 hours) or "Fault" (a day with a burst of false sub-minute blockages) |
| Hours | Decimal | Length of the interval |

**Table A5. Minute-level modeling table** (one row per crossing per forecast time; planned).

| Variable | Type | Role | Description |
|---|---|---|---|
| Blocked in *h* minutes | Yes/No | Target | Whether the crossing is blocked *h* = 5, 10, 15, or 30 minutes after the forecast time |
| Reporting | Yes/No | Filter | Sensor reporting at both the forecast time and the target time |
| Blocked now | Yes/No | Feature | Current state of the crossing |
| Current blockage length | Minutes | Feature | Time since the current blockage began (zero if clear) |
| Current clear spell | Minutes | Feature | Time since the last blockage ended (zero if blocked; capped at 24 hours) |
| Time since last blockage start | Minutes | Feature | Capped at 24 hours |
| Other crossings' state | Yes/No and minutes | Feature | Blocked-now and time-since-start for each of the other seven crossings |
| Recent activity | Counts | Feature | Blockage episodes at this crossing in the previous 1, 6, and 24 hours |
| Hour of day, Day of week, Holiday | Category | Feature | Calendar context |
| Time-of-week rate | Proportion | Feature and baseline | Share of training-period minutes blocked at this crossing in the same hour of the week |
| Crossing | Category | Feature | Identifies the crossing in models shared across crossings |
| Data split | Category | Bookkeeping | Training, validation, or test period |

---

## Reproducing everything

From the project folder: `python scripts/prepare.py` (cleaning, about 10 seconds), `python scripts/eda.py` (Peikun's figures 1–8; the forecasting test needs `xgboost`), `python scripts/eda_extra.py` (figures A–G, tables, and `reports/eda_extra_stats.json`), and `python scripts/fig_pipeline.py` (Figure 0). The raw exports go in `data/`, and `osm_rail_roads.json` in `data/external/`.
