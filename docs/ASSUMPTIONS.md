# Assumptions and Data Limitations

## Data Source Limitations

### X API v2 Free Tier Constraints

**Historical Depth**:
- ❌ **7-Day Lookback Limit**: Free tier restricts historical tweet access to last 7 days
- Impact: Cannot backfill older data without paid Academic/Enterprise access
- Workaround: Continuous daily ingestion to build historical database over time

**Rate Limits**:
- **450 requests per 15-minute window** for user timeline endpoint
- Impact: Backfilling large time ranges requires ~30 minutes (with retry backoff)
- Mitigation: Exponential backoff retry logic implemented; `wait_on_rate_limit=True`

**Data Granularity**:
- Tweet timestamps rounded to nearest second
- No millisecond precision for high-frequency analysis
- Impact: Hawkes process event times are approximate

**Pagination**:
- Maximum 100 tweets per API call
- For prolific users like @elonmusk, may require multiple pages
- Handled automatically by pagination logic

**Endpoint Availability**:
- Tweet counts endpoint (`/2/tweets/counts/all`) **not available** in free tier
- Workaround: Manual aggregation from individual tweets
- Impact: Slower ingestion compared to direct counts API

---

## Timezone and Location Uncertainties

### Timezone Normalization

**UTC Enforcement**:
- All timestamps normalized to UTC at ingestion
- X API returns timestamps in UTC (ISO 8601 format)
- Database stores `TIMESTAMP WITH TIMEZONE`

**User Timezone Unknown**:
- ❌ X API v2 does not provide user timezone in tweet metadata
- Assumption: **Elon Musk tweets from multiple timezones** (US West Coast, Texas, international travel)
- Impact: Cannot assign tweets to local "time of day" with certainty

**Implications**:
- Calendar features (`hour_of_day`) are **UTC-relative**, not user-local
- Models may miss local time patterns (e.g., "morning tweets" in PST vs UTC)
- Mitigation: Cyclical encoding (sin/cos) captures periodic patterns regardless of offset

### Geolocation

**No Location Data**:
- X API v2 free tier does not include geolocation fields
- Even with paid access, <1% of tweets have precise geo tags
- Assumption: **Location is unknown and variable**

**Impact**:
- Cannot model location-specific events (e.g., "tweets increase during SpaceX launches in Texas")
- Exogenous events must be global or time-based only

---

## Tweet Content Limitations

### Counts-Only Approach

**No Content Analysis**:
- ✅ **Intentional Design**: Only tweet counts, no text/sentiment/entities
- Rationale: Privacy, compliance, simplicity, API cost
- Trade-off: Cannot distinguish between announcement tweets vs replies

**Thread Structure**:
- No distinction between original tweets, retweets, replies, quotes
- Assumption: **All tweet types count equally**
- Impact: Reply-heavy periods may inflate counts without substantive content

**Deleted Tweets**:
- X API does not notify of deletions in historical data
- Soft delete flag (`is_deleted`) reserved for future reconciliation
- Assumption: **Deletions are rare and ignored**

---

## Statistical Modeling Assumptions

### Negative Binomial Model

**Stationarity**:
- Assumes dispersion parameter α is **constant over time**
- Reality: Tweet variance may change with events, regime shifts
- Mitigation: Rolling retraining every 24 hours

**Feature Independence**:
- GLM assumes features are not perfectly collinear
- Reality: Hour-of-day and day-of-week have complex interactions
- Mitigation: Cyclical encoding reduces multicollinearity

**Link Function**:
- Log link assumes **multiplicative effects** (e.g., weekends reduce rate by X%)
- May not capture additive or threshold effects

### Hawkes Process

**Exponential Decay**:
- Assumes excitation fades **exponentially** with time
- Reality: Influence may have long tails or multiple timescales
- Limitation: Single-kernel model; multi-kernel extensions exist

**Count-to-Events Conversion**:
- Hourly counts converted to event times by **uniform spreading**
- Assumption: **Tweets uniformly distributed within each hour**
- Reality: Clustering within hours (e.g., 10:05 AM burst)
- Impact: Underestimates intra-hour self-excitation

**Stationarity**:
- Assumes baseline intensity μ is **constant**
- Reality: Baseline may drift over time
- Mitigation: Sliding training window (last 30 days)

### SARIMAX

**Gaussian Errors**:
- Assumes residuals are **normally distributed**
- Reality: Count data has discrete, skewed distribution
- Impact: Confidence intervals may be miscalibrated

**Linear Trends**:
- AR/MA components assume **linear autocorrelations**
- Reality: Tweet behavior may be nonlinear, threshold-driven

**Seasonal Stability**:
- Assumes 24-hour seasonal period is **fixed and stable**
- Reality: Daily patterns may shift (e.g., weekday vs weekend)

---

## Exogenous Events

### Manual Curation

**Human Effort**:
- Events added manually via CLI (no automated news scraping in v1)
- Assumption: **User diligently curates relevant events**
- Limitation: Subjective, incomplete, delayed

**Event Boundaries**:
- Start/end times are **approximate** (e.g., "Tesla earnings call" may span 2-4 hours)
- Impact: Event intensity may bleed into non-event periods

**Intensity Scoring**:
- Intensity (0.0 to 1.0) is **subjectively assigned**
- No objective calibration (e.g., "0.8 = major announcement")
- Impact: Model sensitivity to intensity scale

### Event Overlap

**Multiple Events**:
- Uses **max intensity** across overlapping events
- Assumption: Dominant event drives behavior
- Alternative: Sum or weighted average (not implemented)

**Event Lag**:
- No lag between event occurrence and tweet response
- Reality: Some events may have **delayed effects** (hours/days)
- Mitigation: Event windows include buffer time

---

## Data Availability

### Cold Start Problem

**New Deployment**:
- On first run, only 7 days of history available
- Insufficient for SARIMAX seasonal modeling (needs weeks)
- Mitigation: 
  - Start with Negative Binomial (fewer data requirements)
  - Build historical database via daily ingestion

**Training Data Requirements**:
- **Negative Binomial**: Minimum 24 hours (1 day)
- **Hawkes**: Minimum 10 events (~2-3 days for active users)
- **SARIMAX**: Minimum 2 seasonal cycles (~48 hours for daily seasonality)

### Missing Data

**API Downtime**:
- If X API is unavailable, ingestion fails
- No data for downtime period
- Assumption: **Gaps are rare and short**
- Mitigation: Retry logic with exponential backoff

**User Account Changes**:
- If @elonmusk account is suspended/deleted, API returns 404
- Assumption: **Account remains active**
- Mitigation: Graceful error handling, alert on 404

---

## Model Evaluation Assumptions

### Backtest Validity

**Past Performance**:
- Assumes **past patterns predict future**
- Reality: Black swan events (e.g., Twitter acquisition) break patterns
- Limitation: Backtests cannot predict unprecedented events

**Training Window**:
- Uses last 30 days for training
- Assumption: **Recent data is most relevant**
- Trade-off: Longer windows capture more patterns but may be stale

### Regime Shifts

**Detection Lag**:
- Rolling variance requires 1-week window
- Assumption: **Shifts persist long enough to detect**
- Limitation: Sudden, brief spikes may be missed

**Threshold Sensitivity**:
- 2.0 std deviation threshold is **arbitrary**
- Too low: False positives (frequent retraining)
- Too high: False negatives (miss regime changes)

---

## Scalability Assumptions

### Single User

**@elonmusk Only**:
- System designed for one prolific user (~20-50 tweets/day)
- Assumption: **Not horizontally scaled to thousands of users**
- Extension: Multi-user support requires partitioning, user_id FK

### Database Size

**Growth Estimate**:
- 50 tweets/day × 365 days = 18,250 tweets/year
- Hourly buckets: 8,760 rows/year
- Database: ~100 MB/year (SQLite) or ~50 MB/year (Postgres)
- Assumption: **Single machine sufficient for years**

### Compute Resources

**Model Training**:
- Negative Binomial: <1 second (100 samples)
- Hawkes: ~10 seconds (1000 events)
- SARIMAX: ~30 seconds (1000 samples, order (2,0,2))
- Assumption: **Laptop/desktop sufficient; no GPU/cluster needed**

---

## Privacy and Compliance

### No Personal Data

**Public Tweets Only**:
- All data is **publicly available** via X.com
- No DMs, private accounts, or user profiles
- Compliance: No GDPR/CCPA concerns (public figure, public data)

**No Content Storage**:
- Tweet text/media **not stored** (counts only)
- Reduces storage, copyright risk, and moderation burden

### API Terms of Service

**X Developer Agreement**:
- Assumption: **Usage complies with X API Terms**
- Restrictions: No redistribution, commercial use may require approval
- Mitigation: Internal use only; no public API

---

## Summary of Key Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| 7-day API lookback | Cannot backfill old data | Daily ingestion |
| No user timezone | Local time patterns missed | Cyclical encoding |
| Counts-only (no content) | Cannot distinguish tweet types | Accept trade-off |
| Manual event curation | Incomplete event coverage | Future: Automate via news API |
| Gaussian SARIMAX errors | Miscalibrated CIs for counts | Use NB/Hawkes |
| 30-day training window | May miss long-term trends | Evaluate periodically |
| Single-user design | Not multi-tenant | Sufficient for MVP |

---

## Future Work to Address Limitations

1. **Paid X API Access**: 
   - Academic Research tier for 30-day lookback
   - Full-archive search for historical analysis

2. **Automated Event Detection**:
   - Integrate News API (e.g., NewsAPI.org, GDELT)
   - NLP pipeline for event extraction from headlines

3. **Multi-Timezone Modeling**:
   - Probabilistic timezone assignment via historical patterns
   - Separate models per likely timezone

4. **Ensemble Models**:
   - Weighted average of NB + Hawkes + SARIMAX
   - Bayesian model averaging for uncertainty

5. **Real-Time Streaming**:
   - X API v2 filtered stream for live ingestion
   - Online learning / incremental model updates

6. **Content Features** (Optional):
   - Sentiment analysis (positive/negative/neutral)
   - Topic modeling (Tesla, SpaceX, Crypto)
   - Trade-off: Privacy, complexity, API cost

