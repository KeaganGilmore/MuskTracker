# Statistical Models Documentation

## Overview

MuskTracker implements three complementary models for tweet volume forecasting:

1. **Negative Binomial GLM** - Handles overdispersed count data
2. **Hawkes Process** - Captures self-exciting temporal dynamics
3. **SARIMAX** - Baseline with seasonality and exogenous regressors

---

## 1. Negative Binomial Regression

### Mathematical Formulation

The Negative Binomial distribution models count data with overdispersion (variance > mean):

**Probability Mass Function**:
```
P(Y = y | μ, α) = Γ(y + α⁻¹) / (Γ(α⁻¹)y!) * (α⁻¹ / (α⁻¹ + μ))^(α⁻¹) * (μ / (α⁻¹ + μ))^y
```

Where:
- `Y` = tweet count
- `μ` = mean (modeled via log link)
- `α` = dispersion parameter (α → 0: high overdispersion; α → ∞: Poisson)

**GLM Structure**:
```
log(μ) = β₀ + β₁x₁ + β₂x₂ + ... + βₖxₖ
```

**Features** (`xᵢ`):
- Cyclical time encoding: `hour_sin`, `hour_cos`, `day_sin`, `day_cos`
- Weekend indicator
- Linear time trend
- (Optional) Exogenous event intensities

### Why Negative Binomial?

- **Overdispersion**: Tweet counts exhibit high variance (bursty behavior)
- **Count Data**: Maintains non-negative predictions
- **Interpretability**: Coefficients have clear log-rate interpretations
- **Robustness**: Handles zero counts naturally

### Prediction

**Point Estimate**:
```
ŷ = exp(Xβ̂)
```

**Confidence Interval** (95%):
```
Var(Y) = μ + α*μ²
SE = √Var(Y)
CI = ŷ ± 1.96*SE
```

### Limitations

- Assumes constant dispersion across time
- Ignores temporal dependencies (autoregression)
- Requires sufficient data for stable α estimation

---

## 2. Hawkes Self-Exciting Process

### Mathematical Formulation

Hawkes processes model point processes where past events increase future event rates.

**Conditional Intensity**:
```
λ(t) = μ + ∫₀ᵗ φ(t - s) dN(s)
```

Where:
- `λ(t)` = instantaneous event rate at time t
- `μ` = baseline intensity (background rate)
- `φ(t)` = excitation kernel (exponential decay)
- `N(s)` = counting process of past events

**Exponential Kernel**:
```
φ(t) = α * β * exp(-β*t)
```

Where:
- `α` = branching ratio (self-excitation strength)
- `β` = decay rate (how fast influence fades)

### Why Hawkes?

- **Temporal Clustering**: Models "tweet storms" and bursty behavior
- **Self-Reinforcement**: Past tweets increase probability of near-future tweets
- **Realistic Dynamics**: Captures autocorrelation naturally
- **Regime Detection**: Identifies periods of heightened activity

### Implementation

**Library**: `tick` (Python Hawkes process toolkit)

**Fitting**:
1. Convert count data to event times (approximate)
2. Maximum likelihood estimation via gradient descent
3. Learn `μ`, `α`, `β` from data

**Prediction**:
- Use baseline intensity `μ` as hourly rate estimate
- In production: integrate conditional intensity over forecast horizon

### Limitations

- Count-to-events conversion is approximate (loses intra-hour structure)
- Requires sufficient events (>10) for stable fitting
- Forecasting requires numerical integration of intensity
- No direct exogenous covariate support in standard formulation

---

## 3. SARIMAX (Seasonal ARIMA with Exogenous Regressors)

### Mathematical Formulation

**ARIMA(p, d, q)**:
```
Φ(B)(1 - B)ᵈyₜ = Θ(B)εₜ
```

Where:
- `Φ(B)` = AR polynomial of order p
- `Θ(B)` = MA polynomial of order q
- `d` = differencing order
- `B` = backshift operator

**Seasonal Component** (P, D, Q, s):
```
Φₛ(Bˢ)(1 - Bˢ)ᴰ
```

Where `s` = seasonal period (24 for hourly data with daily seasonality)

**Exogenous Regressors**:
```
yₜ = Xₜβ + ARIMA_component
```

### Default Configuration

- **Order**: (2, 0, 2) - 2 AR lags, no differencing, 2 MA lags
- **Seasonal**: (1, 0, 1, 24) - 24-hour seasonal cycle
- **Exogenous**: Event intensity, calendar features (optional)

### Why SARIMAX?

- **Baseline**: Well-established, interpretable benchmark
- **Seasonality**: Captures daily/weekly patterns explicitly
- **Exogenous**: Incorporates external events
- **Forecasting**: Built-in multi-step ahead prediction with CIs

### Limitations

- Assumes Gaussian errors (not ideal for count data)
- Can produce negative forecasts (clipped to 0)
- Computationally intensive for large datasets
- Requires stationarity or differencing

---

## Model Comparison

| Feature | Negative Binomial | Hawkes | SARIMAX |
|---------|------------------|---------|---------|
| **Data Type** | Count | Point Process | Continuous |
| **Overdispersion** | ✅ Native | ⚠️ Implicit | ❌ Gaussian |
| **Temporal Deps** | ❌ None | ✅ Self-exciting | ✅ AR/MA |
| **Seasonality** | ⚠️ Via features | ❌ None | ✅ Explicit |
| **Exogenous** | ✅ GLM framework | ❌ Not standard | ✅ Regression |
| **Interpretability** | ✅ High | ⚠️ Medium | ⚠️ Medium |
| **Forecast CIs** | ✅ Parametric | ⚠️ Approximate | ✅ Analytical |

**Recommendation**:
- **Hawkes**: Best for bursty, self-reinforcing patterns
- **Negative Binomial**: Best for stable count modeling with exogenous factors
- **SARIMAX**: Best for seasonal baseline comparison

---

## Evaluation Metrics

### Root Mean Squared Error (RMSE)
```
RMSE = √(1/n Σ(yᵢ - ŷᵢ)²)
```
- Penalizes large errors heavily
- Same units as target variable (tweet counts)

### Mean Absolute Error (MAE)
```
MAE = 1/n Σ|yᵢ - ŷᵢ|
```
- Robust to outliers
- Interpretable: average prediction error

### Mean Absolute Percentage Error (MAPE)
```
MAPE = 100/n Σ|yᵢ - ŷᵢ| / yᵢ  (for yᵢ > 0)
```
- Scale-independent
- Interpretable as percentage error

### Log-Likelihood (for probabilistic models)
```
LL = Σ log P(yᵢ | θ)
```
- Measures model fit to data distribution
- Higher is better
- Comparable across models with same data

---

## Rolling Backtest Methodology

**Purpose**: Evaluate model performance on unseen future data.

**Procedure**:
1. Define evaluation window (e.g., last 60 days)
2. Divide into N rolling windows (default: 12)
3. For each window:
   - Train on past T days (default: 30)
   - Forecast next H hours (default: 24)
   - Compute metrics on actual vs predicted
4. Aggregate metrics across windows

**Advantages**:
- Tests generalization to future data
- Detects overfitting
- Mimics production deployment

**Example**:
```
Window 1: Train [Day 1-30]  → Test [Day 31]
Window 2: Train [Day 5-35]  → Test [Day 36]
...
Window 12: Train [Day 55-85] → Test [Day 86]
```

---

## Regime Shift Detection

**Method**: Rolling variance analysis

**Algorithm**:
1. Compute rolling mean and std over W-hour window (default: 168 = 1 week)
2. Calculate variance ratio: `σₜ / σₜ₋ᵤ`
3. Detect shift if ratio > threshold (default: 2.0 std deviations)

**Use Cases**:
- Identify periods requiring model retraining
- Adjust forecasting uncertainty
- Trigger alerts for anomalous behavior

---

## Hyperparameter Tuning

### Negative Binomial
- **Tunable**: Feature engineering (lag windows, rolling windows)
- **Fixed**: α (dispersion) learned via MLE

### Hawkes
- **Tunable**: `decay` (initial β), `penalty` ('none', 'l1', 'l2')
- **Learned**: `baseline` (μ), `adjacency` (α)

### SARIMAX
- **Tunable**: `order` (p, d, q), `seasonal_order` (P, D, Q, s)
- **Strategy**: Grid search or AIC/BIC minimization

---

## Production Considerations

### Model Selection
- Run backtest on all three models
- Select based on lowest RMSE or MAPE
- Consider ensemble (weighted average)

### Retraining Frequency
- Daily: Incorporate latest tweets
- Weekly: Full hyperparameter retuning
- On regime shift: Emergency retraining

### Confidence Intervals
- Use 95% CIs for uncertainty quantification
- Alert on CI width expansion (high uncertainty)
- Clip lower bounds to 0 (counts)

### Computational Cost
- **Negative Binomial**: Fast (seconds)
- **Hawkes**: Medium (minutes for large datasets)
- **SARIMAX**: Slow (minutes, depends on order)

---

## References

1. **Negative Binomial**: Hilbe, J. (2011). *Negative Binomial Regression*. Cambridge University Press.
2. **Hawkes Process**: Hawkes, A. G. (1971). "Spectra of some self-exciting and mutually exciting point processes."
3. **SARIMAX**: Box, G. E. P., Jenkins, G. M., Reinsel, G. C. (2015). *Time Series Analysis: Forecasting and Control*.
4. **tick Library**: Bacry, E., et al. (2017). "tick: a Python library for statistical learning."

