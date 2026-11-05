# Synthetic Price Generation with Random Walks — Industry Standards by Asset Class

Oct 18, 2026 · @Marcello

## Purpose and scope

The industry baseline for synthetic prices in every asset class is the **geometric random walk** (discretised Geometric Brownian Motion, GBM) on log prices; the **biased** version adds a drift term, and each asset class then layers on the one or two extensions its data visibly demands (jumps, stochastic volatility, mean reversion, fat tails). No desk uses a pure random walk as its final model — it is the null hypothesis everything else is measured against.

Synthetic prices are used for three jobs:

1. **Null benchmarks.** Run a strategy on paths with no exploitable structure; any "edge" found there is overfitting or a backtest artefact (Bailey et al., 2014; Aronson, 2007).
2. **Stress and capacity tests.** Generate thousands of plausible futures to estimate drawdown distributions and tail risk (Glasserman, 2003).
3. **Pipeline validation.** Inject a *known* drift or pattern and check that the research pipeline recovers it — a unit test for the statistics.

**Random walk (RW) vs biased random walk (BRW).** An unbiased RW has zero expected log return per step. A BRW has a non-zero expected step, $\mu_s\,\Delta t$, which can be (a) a risk-neutral drift for pricing, (b) a real-world drift calibrated from history or from carry, or (c) a deliberately planted drift to test signal detection. Which one you choose depends on the job, not on the asset class.

In the expected step $\mu_s\,\Delta t$:

- $\mu_s$ is the drift (the bias) per second: the expected log return per second. $\mu_s = 0$ gives the unbiased random walk, and any other value gives the biased one.
- $\Delta t$ is the length of one simulation step, in seconds. In the tick generator it is the time between two consecutive ticks (for example 0.1 s at 10 ticks per second).
- $\mu_s\,\Delta t$ is therefore the expected log return of one step: the drift per second multiplied by the number of seconds the step lasts.

Each asset section below is layered: **Intuition → Theory → Example**, followed by a single References section.

**Notation.** Every formula is followed by a "where" list that defines each symbol in it. The symbols are defined again under every formula on purpose, so each formula can be read on its own. The same letter can mean different things in different models (for example $\kappa$, $\xi$, $\rho$, $L$ and $r$); the "where" list under each formula is the definition that applies to it. In the common foundation (random walk and GBM) time is in **seconds**: $\Delta t_i$ is the gap between two consecutive ticks, $\mu_s$ is the drift per second and $\sigma_s$ the volatility per square-root second. The asset-class sections after it use the **annual** rates quoted in the literature ($\mu$, $\sigma$, $r$), with $\Delta t$ in years; the conversion between the two is in "From annual parameters to per-tick parameters".

## Common foundation: random walk, GBM and drift

Every generator in this document is the same recipe — **simulate log returns, then exponentiate and cumulate** — with a different rule for what the return distribution looks like at each step.

**Implementation scope.** The first implementation of the tick generator uses the **arithmetic random walk** (below), with the drift and volatility in price units. GBM is kept in this document as the reference for a later iteration. The arithmetic walk is not bounded: it can leave the price range or become negative, so the generator must apply the price range rule of the domain analysis (reset to the initial bid). Its step size does not depend on the price level, while the GBM step grows with the price.

### Intuition

Prices are multiplicative: a 1% move on 100 and on 200 is the same "size" of news. So you random-walk the *logarithm* of price, which guarantees positive prices and makes returns scale-free. Adding a constant to each log step (the bias) tilts the walk upward or downward — that is all a "biased random walk" is.

Ticks arrive many times per second, and at irregular moments. The walk therefore takes one step per tick, and the size of the step scales with the time elapsed since the previous tick: the longer the gap, the larger the typical move. Expressing the drift and the volatility **per second** makes the same parameters valid at any tick rate.

### Theory

**Time and units.** The generator produces ticks, so time is measured in **seconds** and the step of the walk is the gap between two consecutive ticks. Drifts and volatilities are written **per second** in the two models below. Literature values are normally quoted per year; "From annual parameters to per-tick parameters" below shows the conversion.

**Arithmetic random walk** (Bachelier, 1900) — only for spreads, rates or prices that can go negative:

$P_i = P_{i-1} + \mu_s\,\Delta t_i + \sigma_s\sqrt{\Delta t_i}\,\varepsilon_i, \qquad \varepsilon_i \sim \text{iid } N(0,1)$

where:

- $i$ is the tick number: $i = 1, 2, 3, \dots$
- $P_i$ is the price (or spread, or rate) right after tick $i$, and $P_{i-1}$ is the price right after the previous tick.
- $\Delta t_i$ is the time between tick $i-1$ and tick $i$, in seconds. It can be constant (evenly spaced ticks) or random (irregular ticks, see "Tick timing" below).
- $\mu_s$ is the drift per second: the expected change of the price per second, in price units.
- $\mu_s\,\Delta t_i$ is the expected price change between the two ticks.
- $\sigma_s$ is the volatility per square-root second: the standard deviation of the price change over one second, in price units.
- $\sigma_s\sqrt{\Delta t_i}$ is the standard deviation of the price change between the two ticks.
- $\varepsilon_i$ is the random shock of tick $i$: a draw from a standard normal distribution.
- $N(0,1)$ is the standard normal distribution: mean 0 and standard deviation 1.
- "iid" means the shocks are independent of each other and all drawn from the same distribution.

**Geometric Brownian Motion** (Samuelson, 1965; Black & Scholes, 1973; Merton, 1973):

$dS_t = \mu_s S_t\,dt + \sigma_s S_t\,dW_t$

where:

- $t$ is time, in seconds.
- $S_t$ is the price at time $t$, and $dS_t$ is its infinitesimal change over the infinitesimal time $dt$ (a tiny fraction of a second).
- $\mu_s$ is the drift per second: the expected return per second (a very small number, for example $3 \times 10^{-9}$ per second for 7% a year).
- $\mu_s S_t\,dt$ is the deterministic part of the change: the price grows at rate $\mu_s$.
- $\sigma_s$ is the volatility per square-root second: the standard deviation of the return over one second.
- $W_t$ is a standard Brownian motion (Wiener process): a continuous random path whose increments $dW_t$ are normal with mean 0 and variance $dt$ (with $dt$ in seconds).
- $\sigma_s S_t\,dW_t$ is the random part of the change, proportional to the current price.

Its **exact** discretisation, evaluated at the tick times (no Euler error, because log S is Gaussian):

$S_i = S_{i-1} \exp\!\left[\left(\mu_s - \tfrac{1}{2}\sigma_s^2\right)\Delta t_i + \sigma_s\sqrt{\Delta t_i}\,Z_i\right], \qquad Z_i \sim N(0,1)$

where:

- $i$ is the tick number: $i = 1, 2, 3, \dots$
- $S_i$ is the price right after tick $i$, and $S_{i-1}$ is the price right after the previous tick.
- $\Delta t_i$ is the time between tick $i-1$ and tick $i$, in seconds (constant or random, see "Tick timing" below).
- $\mu_s$ is the drift per second (expected return per second).
- $\sigma_s$ is the volatility per square-root second, and $\sigma_s^2$ is the variance per second.
- $-\tfrac{1}{2}\sigma_s^2$ is the Itô correction, per second, explained below.
- $\left(\mu_s - \tfrac{1}{2}\sigma_s^2\right)\Delta t_i$ is the deterministic part of the log return between the two ticks.
- $\sigma_s\sqrt{\Delta t_i}\,Z_i$ is the random part of the log return between the two ticks.
- $Z_i$ is a random shock drawn from the standard normal distribution $N(0,1)$ (mean 0, standard deviation 1), drawn independently at every tick.
- $\exp[\cdot]$ is the exponential function: it turns the log return into a price multiplier, which keeps prices positive.

The $-\tfrac{1}{2}\sigma_s^2$ term is the Itô correction. It makes the expected terminal price equal to $E[S_T] = S_0\,e^{\mu_s T}$, while the median path grows only at the rate $\mu_s - \tfrac{1}{2}\sigma_s^2$ per second, that is $\text{median}(S_T) = S_0\,e^{(\mu_s - \frac{1}{2}\sigma_s^2)T}$. Forgetting it is the most common bug in home-made generators (Glasserman, 2003, ch. 3; Shreve, 2004, ch. 4).

In these two expressions:

- $S_0$ is the initial price, and $S_T$ is the price at the final time $T$.
- $T$ is the length of the simulated period, in seconds ($T = \sum_i \Delta t_i$ when the path is built from ticks).
- $E[S_T]$ is the expected value (the mean over many simulated paths) of the terminal price.
- $\text{median}(S_T)$ is the median (the middle value over many simulated paths) of the terminal price.
- $\mu_s$ is the drift per second, and $\sigma_s$ is the volatility per square-root second.
- $e^{x}$ is the exponential function, with $e \approx 2.718$.

**Tick timing.** The walk only needs the gaps $\Delta t_i$ between ticks. Two common choices:

- **Evenly spaced ticks:** $\Delta t_i = \dfrac{1}{f}$ for every $i$.
- **Irregular ticks (Poisson arrivals):** $\Delta t_i \sim \text{Exp}(f)$, so $E[\Delta t_i] = \dfrac{1}{f}$.

where:

- $f$ is the average tick rate, in ticks per second (for example $f = 10$).
- $1/f$ is the average gap between ticks, in seconds (0.1 s for $f = 10$).
- $\text{Exp}(f)$ is the exponential distribution with rate $f$: gaps are random, short gaps are more frequent than long ones, and the mean gap is $1/f$.
- $E[\cdot]$ is the expected value.

Because the price update uses $\Delta t_i$ itself, the formulas above hold for any gap, so a longer gap produces a larger move and a shorter gap a smaller one. Real tick data is irregular, and bursts of ticks around news are not captured by a constant $f$.

**Random number of ticks per time unit.** When the requirement is to produce $n$ ticks in every time unit, and $n$ itself is random, generate the tick times in two steps: first draw how many ticks each time unit gets, then place those ticks at random positions inside the time unit.

*Step 1: number of ticks in each time unit.*

$N_k \sim \mathcal{D}(\theta), \qquad k = 1, \dots, K$

where:

- $k$ is the index of the time unit (the bucket): $k = 1$ is the first one after the start of the series.
- $K = \lceil T / \tau \rceil$ is the number of buckets needed to cover the period, where $T$ is the length of the series in seconds and $\tau$ is the length of a bucket in seconds ($\tau = 1$ for a "ticks per second" requirement).
- $N_k$ is the number of ticks of bucket $k$: a non-negative integer, drawn independently for each bucket.
- $\mathcal{D}$ is the probability distribution of the counts (see the choices below).
- $\theta$ is the parameters of that distribution (for example its mean $\bar{n}$).
- $\bar{n} = E[N_k]$ is the mean number of ticks per bucket.

*Step 2: position of the ticks inside the bucket.* Given $N_k = n$, draw $n$ independent uniform numbers and sort them:

$t_{k,(j)} = (k-1)\,\tau + \tau\,U_{k,(j)}, \qquad j = 1, \dots, N_k$

where:

- $t_{k,(j)}$ is the time, in seconds from the start of the series, of the $j$-th tick of bucket $k$.
- $(k-1)\,\tau$ is the start time of bucket $k$, and $\tau$ is the length of the bucket, in seconds.
- $U_{k,(1)} \le U_{k,(2)} \le \dots \le U_{k,(N_k)}$ are the $N_k$ numbers drawn from the uniform distribution on $(0,1)$, sorted in increasing order. The parentheses around $j$ mean "$j$-th smallest".
- $j$ is the position of the tick inside the bucket, from the first to the last.

Once the buckets are put one after another, the gap used by the price walk is:

$\Delta t_i = t_i - t_{i-1}, \qquad t_0 = 0$

where:

- $i$ is the number of the tick over the whole series, counting the ticks of all buckets in time order.
- $t_i$ is the time of tick $i$, in seconds from the start of the series (one of the $t_{k,(j)}$ above).
- $t_{i-1}$ is the time of the previous tick, and $t_0 = 0$ is the start of the series, where the price is $S_0$.
- $\Delta t_i$ is the gap, in seconds, between tick $i-1$ and tick $i$. It is the quantity used in the random walk and GBM formulas above.
- A gap that crosses a bucket boundary runs from the last tick of one bucket to the first tick of the next one. If a bucket has no ticks ($N_k = 0$), the gap spans the empty bucket.

Equivalent way to draw the positions, without sorting. The $N_k + 1$ gaps that split a bucket of length $\tau$ into $N_k$ ticks are

$\tau\,\dfrac{E_0}{S}, \; \tau\,\dfrac{E_1}{S}, \; \dots, \; \tau\,\dfrac{E_{N_k}}{S}, \qquad S = \sum_{j=0}^{N_k} E_j, \qquad E_j \sim \text{iid Exp}(1)$

where:

- $E_0, E_1, \dots, E_{N_k}$ are $N_k + 1$ independent draws from the exponential distribution with rate 1 (mean 1).
- $S$ is their sum.
- $E_j / S$ is the fraction of the bucket taken by gap $j$; the fractions add up to 1, and $\tau E_j / S$ is the gap in seconds.
- The first gap, $\tau E_0 / S$, runs from the start of the bucket to its first tick, and the last gap, $\tau E_{N_k} / S$, from the last tick to the end of the bucket. The times of the ticks are the running sums of the first $N_k$ gaps.
- $\text{Exp}(1)$ is the exponential distribution with rate 1, and $\sum_{j=0}^{N_k}$ adds the terms from $j = 0$ to $j = N_k$. This is a Dirichlet draw with all parameters equal to 1.

Both ways give the same distribution. Because the positions are uniform and independent of the count, the method works for any distribution of counts $\mathcal{D}$.

**Choices for the distribution of the counts $\mathcal{D}$**

| Distribution | Mean | Variance | Behaviour |
| --- | --- | --- | --- |
| Poisson($\bar{n}$) | $\bar{n}$ | $\bar{n}$ | Standard choice. With the same $\bar{n}$ in every bucket, the whole series is a homogeneous Poisson process with rate $f = \bar{n} / \tau$, so the gaps are $\text{Exp}(f)$, as in "Tick timing" above. |
| Negative binomial($r$, $p$), with $p = \dfrac{r}{r + \bar{n}}$ | $\bar{n}$ | $\bar{n} + \dfrac{\bar{n}^2}{r}$ | Bursty: some buckets are quiet and others busy. The smaller $r$ is, the burstier the series. As $r \to \infty$ it becomes Poisson. |
| Fixed $n$ (point mass) | $n$ | $0$ | Exactly $n$ ticks in every bucket. |
| Any of the above limited to $[n_{min}, n_{max}]$ | depends | depends | Enforces bounds on the count. Redraw until the value is inside the bounds (truncated distribution); clipping to the bounds piles up probability at $n_{min}$ and $n_{max}$ and changes the mean. |

In the table:

- $\bar{n}$ is the mean number of ticks per bucket.
- $r > 0$ is the dispersion (shape) parameter of the negative binomial: it controls how much the variance exceeds the mean.
- $p$ is the success probability of the negative binomial, chosen as $r / (r + \bar{n})$ so that the mean is exactly $\bar{n}$.
- The variance is the squared standard deviation of $N_k$. A variance larger than the mean means the counts are more spread out than Poisson counts ("overdispersed").
- $n$ in the fixed row is the constant number of ticks per bucket, and $n_{min}$ and $n_{max}$ are the smallest and largest allowed counts.

**Default choice: negative binomial.** The counts $N_k$ are drawn from the negative binomial distribution with mean $\bar{n}$ and dispersion $r$. It reproduces the burstiness of real tick counts (variance above the mean), it contains the Poisson case as the limit $r \to \infty$, and it needs only two parameters, $\bar{n}$ and $r$. The value of $r$ is a configuration choice still to be calibrated; a small $r$ gives very uneven seconds and a large $r$ gives nearly Poisson counts. Optional bounds $[n_{min}, n_{max}]$ are applied by redrawing, as in the table.

To make the mean depend on the time of day, multiply the mean of each bucket by a deterministic factor: $\bar{n}_k = \bar{n}\,s_k$, where $s_k$ is the seasonal factor of bucket $k$ (above 1 in busy hours, below 1 in quiet ones, as the intraday factor $s(\tau)$ in the Forex section).

**What this does to the number of ticks and to the volatility**

The total number of ticks of the series is random:

$E[N] = K\,\bar{n}, \qquad \text{Var}[N] = K\,\text{Var}[N_k]$

where:

- $N = \sum_{k=1}^{K} N_k$ is the total number of ticks in the series.
- $E[N]$ and $\text{Var}[N]$ are its expected value and its variance.
- $K$ is the number of buckets, $\bar{n} = E[N_k]$ is the mean number of ticks per bucket, and $\text{Var}[N_k]$ is the variance of the count of one bucket (from the table).
- The variance formula holds because the counts of different buckets are independent.

So the number of records is only known after the series is produced; before that only its expected value $K\,\bar{n}$ is known. Two further points:

- The volatility per second does not depend on the count. The step size is $\sigma_s\sqrt{\Delta t_i}$, so a bucket with many ticks has small steps and a bucket with few ticks has large ones, and the variance over any stretch of time is still $\sigma_s^2$ times the time elapsed. If busy buckets should also be *more volatile*, the volatility must be made to depend on $N_k$; that is a different model and is not covered here.
- When timestamps are stored with a finite resolution (for example milliseconds), two ticks of the same bucket can get the same timestamp. At a high tick rate decide whether to allow equal timestamps or to nudge them apart.

**From annual parameters to per-tick parameters.** The conversion from the annual figures used in the literature and in the asset sections below is:

$\mu_s = \dfrac{\mu_a}{N_s}, \qquad \sigma_s = \dfrac{\sigma_a}{\sqrt{N_s}}$

and the parameters of one step of $\Delta t_i$ seconds are:

$\mu_{tick} = \mu_s\,\Delta t_i, \qquad \sigma_{tick} = \sigma_s\sqrt{\Delta t_i}$

where:

- $\mu_a$ is the annual drift (expected return per year, for example 0.08 for 8%).
- $\sigma_a$ is the annual volatility (standard deviation of the return per year, for example 0.07 for 7%).
- $N_s$ is the number of trading seconds per year. For FX, 260 trading days of 24 hours: $260 \times 24 \times 3600 = 22{,}464{,}000$. For crypto, 24/7: $365 \times 86{,}400 = 31{,}536{,}000$. For an exchange-traded asset, 252 days of 6.5 hours: $252 \times 6.5 \times 3600 = 5{,}896{,}800$.
- $\mu_s$ is the drift per second and $\sigma_s$ the volatility per square-root second, as used in the formulas above.
- $\Delta t_i$ is the time between two consecutive ticks, in seconds.
- $\mu_{tick}$ is the expected log return of one step, and $\sigma_{tick}$ is the standard deviation of the log return of one step.
- The volatility is divided by $\sqrt{N_s}$ and not by $N_s$ because variances add over time, not standard deviations.

This is why the tick rate does not change the volatility of the path:

$\text{Var}\!\left[\ln S_T - \ln S_0\right] = \sum_{i} \sigma_s^2\,\Delta t_i = \sigma_s^2\,T$

where:

- $\ln S_T - \ln S_0$ is the log return over the whole simulated period.
- $\text{Var}[\cdot]$ is the variance.
- $\sum_i$ adds the terms of all ticks of the period.
- $\sigma_s^2\,\Delta t_i$ is the variance of the log return of tick $i$.
- $T = \sum_i \Delta t_i$ is the total length of the period, in seconds.

The total variance depends only on $\sigma_s$ and $T$. Doubling the tick rate halves each step's variance and doubles the number of steps, so the volatility over any period stays the same.

All the asset sections below quote annual rates ($r$, $r_d$, $r_f$, $\sigma$, $\mu$), as in the literature. To use them in the tick generator, convert them with the formulas above.

**Choosing the drift μ (the "bias")**

| Use case | Drift convention | Source |
| --- | --- | --- |
| Option pricing / risk-neutral | $\mu = r - q$ (rate minus dividend or foreign rate) | Black & Scholes (1973); Hull (2022) |
| Real-world scenario / risk | $\mu$ = historical mean, usually shrunk towards a prior (equity premium, carry) | Meucci (2005) |
| Null benchmark for strategy testing | $\mu = 0$, or $\mu$ such that the median path is flat ($\mu = \tfrac{1}{2}\sigma^2$) | Aronson (2007) |
| Signal-recovery test | $\mu$ planted at a known value, then estimated back | Lo & MacKinlay (1988) |

In the table:

- $\mu$ is the drift (the bias), written here as an annual rate because that is how the conventions in the table are quoted. The generator uses the per-second drift $\mu_s = \mu / N_s$ (see the conversion above).
- $r$ is the risk-free interest rate, per year (the domestic rate for FX).
- $q$ is the continuous dividend yield, per year (for FX it is the foreign interest rate $r_f$).
- $\mu = r - q$ is therefore the growth rate that makes the expected price consistent with no-arbitrage pricing.
- $\sigma$ is the annual volatility. $\mu = \tfrac{1}{2}\sigma^2$ cancels the Itô correction $-\tfrac{1}{2}\sigma^2$, so the median path is flat. In per-second terms this is $\mu_s = \tfrac{1}{2}\sigma_s^2$.

Note that the sample mean of returns is estimated very imprecisely: its standard error is

$\text{SE}(\hat{\mu}) = \dfrac{\sigma}{\sqrt{T}}$

in annual units, so ten years of a 15%-vol asset pins $\mu$ down only to $\pm 4.7\%$ (Merton, 1980).

where:

- $\hat{\mu}$ is the estimate of the annual drift obtained from the sample of historical returns.
- $\text{SE}(\hat{\mu})$ is the standard error of that estimate: roughly how far $\hat{\mu}$ typically is from the true $\mu$.
- $\sigma$ is the annual volatility of the asset (0.15 in the example).
- $T$ is the length of the sample, in years (10 in the example).
- Check: $0.15 / \sqrt{10} \approx 0.047$, that is 4.7%. This is why industry practice prefers economically motivated drifts over historical ones.

**Stylised facts a plain GBM fails to reproduce** (Cont, 2001; Mandelbrot, 1963; Fama, 1965):

1. Heavy tails — return kurtosis well above 3 at daily and intraday horizons.
2. Volatility clustering — |r\_t| is autocorrelated for weeks to months, while r\_t itself is not.
3. Leverage effect — volatility rises after price falls (strong in equities, weak in FX).
4. Aggregational Gaussianity — tails thin out as the horizon lengthens.
5. Jumps — discontinuities around news, earnings, central-bank decisions, hacks.
6. Intraday and weekly seasonality in volatility and volume.

The standard extensions that fix these, used repeatedly in the asset sections:

| Extension | Fixes | Canonical reference |
| --- | --- | --- |
| Student-t innovations | Heavy tails | Praetz (1972); Blattberg & Gonedes (1974) |
| GARCH(1,1) volatility | Clustering, heavy unconditional tails | Engle (1982); Bollerslev (1986) |
| GJR / EGARCH | Leverage asymmetry | Glosten, Jagannathan & Runkle (1993); Nelson (1991) |
| Heston stochastic volatility | Clustering, smile, leverage via ρ < 0 | Heston (1993) |
| Merton / Kou jump-diffusion | Jumps, short-horizon tails | Merton (1976); Kou (2002) |
| Bates SVJ | All of the above together | Bates (1996) |
| Markov regime switching | Calm vs crisis regimes, drift shifts | Hamilton (1989) |
| Ornstein–Uhlenbeck | Mean reversion | Uhlenbeck & Ornstein (1930); Vasicek (1977) |

### Example

Minimal, vectorised tick-level GBM / BRW generator in Python (NumPy). Parameters are per second, as in the formulas above. Setting `mu_s=0` gives the drift-free null; any other `mu_s` gives the biased walk. With `irregular=True` the gaps between ticks are random (Poisson arrivals); with `irregular=False` ticks are evenly spaced.

```python
import numpy as np

SECONDS_PER_YEAR = 260 * 24 * 3600      # FX: 260 trading days of 24 h = 22,464,000 s

def annual_to_per_second(mu_a, sigma_a, n_seconds=SECONDS_PER_YEAR):
    """Convert annual drift and volatility to per-second values (volatility per sqrt-second)."""
    return mu_a / n_seconds, sigma_a / np.sqrt(n_seconds)

def gbm_ticks(S0, mu_s, sigma_s, ticks_per_second, n_ticks, irregular=True, seed=None):
    """Exact GBM sampled at tick times.
    mu_s per second, sigma_s per sqrt(second); returns tick times (s from start) and prices."""
    rng = np.random.default_rng(seed)
    if irregular:   # Poisson arrivals: exponential gaps with mean 1 / ticks_per_second
        dt = rng.exponential(1.0 / ticks_per_second, n_ticks)
    else:           # one tick every 1 / ticks_per_second seconds
        dt = np.full(n_ticks, 1.0 / ticks_per_second)
    Z = rng.standard_normal(n_ticks)
    log_ret = (mu_s - 0.5 * sigma_s**2) * dt + sigma_s * np.sqrt(dt) * Z
    t = np.concatenate(([0.0], np.cumsum(dt)))
    price = S0 * np.exp(np.concatenate(([0.0], np.cumsum(log_ret))))
    return t, price

# EURUSD at 1.08, 7% annual volatility, null drift, 10 ticks per second, about one hour of ticks
mu_s, sigma_s = annual_to_per_second(mu_a=0.0, sigma_a=0.07)
t, p = gbm_ticks(1.08, mu_s, sigma_s, ticks_per_second=10, n_ticks=36_000, seed=1)
```

With these numbers, $\sigma_s = 0.07 / \sqrt{22{,}464{,}000} \approx 1.48 \times 10^{-5}$ per $\sqrt{\text{second}}$. At 10 ticks per second the mean gap is $\Delta t = 0.1$ s, so one tick moves the price by about $\sigma_s\sqrt{0.1} \approx 4.7 \times 10^{-6}$ in relative terms (about 0.05 pip at 1.08). Over the hour the typical move is $\sigma_s\sqrt{3600} \approx 8.9 \times 10^{-4}$, about 9.6 pips, which equals the volatility of an hourly bar at this annual volatility ($0.07 / \sqrt{6240} \approx 8.9 \times 10^{-4}$, with $6240 = 260 \times 24$ hours per year). The tick rate changes how many points the path has, not how far it wanders.

The Itô correction is negligible over a few ticks and accumulates over long horizons. For example, with $\mu_s = 0$ and an annual volatility of 0.20, after one year of trading seconds the *mean* terminal price stays at $S_0$, but the *median* drifts down to

$S_0\,e^{(\mu_s - \frac{1}{2}\sigma_s^2)T} = S_0\,e^{-\frac{1}{2}\sigma_s^2 N_s} = 100\,e^{-0.02} \approx 98$

where:

- $S_0 = 100$ is the initial price.
- $\mu_s = 0$ is the drift per second (the unbiased walk).
- $\sigma_s = 0.20 / \sqrt{N_s}$ is the volatility per $\sqrt{\text{second}}$ that corresponds to an annual volatility of 0.20.
- $N_s$ is the number of trading seconds per year (22,464,000 for FX), and $T = N_s$ seconds is the length of the simulation: one year.
- The exponent is $-\tfrac{1}{2}\sigma_s^2 T = -\tfrac{1}{2}\cdot\dfrac{0.20^2}{N_s}\cdot N_s = -\tfrac{1}{2}(0.04) = -0.02$, and $e^{-0.02} \approx 0.98$.

To generate the ticks with a random number of ticks per time unit (see "Random number of ticks per time unit" above), draw the tick times first and feed the gaps to the GBM:

```python
def tick_times(n_buckets, bucket_s=1.0, mean_ticks=10.0, dispersion=None, seed=None):
    """Tick times with a random number of ticks per bucket, placed uniformly at random inside it.
    dispersion=None -> Poisson counts; dispersion=r -> negative binomial counts
    (mean = mean_ticks, variance = mean_ticks + mean_ticks**2 / r)."""
    rng = np.random.default_rng(seed)
    if dispersion is None:
        counts = rng.poisson(mean_ticks, n_buckets)
    else:
        p = dispersion / (dispersion + mean_ticks)
        counts = rng.negative_binomial(dispersion, p, n_buckets)
    bucket_of_tick = np.repeat(np.arange(n_buckets), counts)
    t = bucket_of_tick * bucket_s + rng.uniform(0.0, bucket_s, counts.sum())
    t.sort()          # ticks of bucket k lie in [k*bucket_s, (k+1)*bucket_s), so a global sort orders each bucket
    return t, counts

def gbm_from_gaps(S0, mu_s, sigma_s, dt, seed=None):
    """Exact GBM updated with the given gaps dt (seconds); returns S0 followed by the price at each tick."""
    rng = np.random.default_rng(seed)
    Z = rng.standard_normal(len(dt))
    log_ret = (mu_s - 0.5 * sigma_s**2) * dt + sigma_s * np.sqrt(dt) * Z
    return S0 * np.exp(np.concatenate(([0.0], np.cumsum(log_ret))))

# One hour, buckets of 1 second, mean 10 ticks per second, bursty counts (dispersion r = 4)
t, counts = tick_times(n_buckets=3600, bucket_s=1.0, mean_ticks=10, dispersion=4, seed=1)
dt = np.diff(t, prepend=0.0)                       # gaps; the first one starts at t = 0
mu_s, sigma_s = annual_to_per_second(mu_a=0.0, sigma_a=0.07)
price = gbm_from_gaps(1.08, mu_s, sigma_s, dt, seed=2)
```

Here the count of each second has mean 10 and variance $10 + 10^2/4 = 35$, so the number of ticks per second varies a lot more than with Poisson counts (variance 10). The total number of ticks in the hour is random, with expected value $3600 \times 10 = 36{,}000$.

The first implementation uses the arithmetic random walk instead of GBM. With the same tick times, the price is updated with:

```python
def arithmetic_from_gaps(P0, mu_s, sigma_s, dt, seed=None):
    """Arithmetic random walk updated with the gaps dt (seconds).
    mu_s in price units per second, sigma_s in price units per sqrt(second).
    Returns P0 followed by the price at each tick."""
    rng = np.random.default_rng(seed)
    eps = rng.standard_normal(len(dt))
    steps = mu_s * dt + sigma_s * np.sqrt(dt) * eps
    return P0 + np.concatenate(([0.0], np.cumsum(steps)))

# Same tick times as above; volatility in price units: 7% of 1.08 per year
mu_s, sigma_s = annual_to_per_second(mu_a=0.0, sigma_a=0.07 * 1.08)
price = arithmetic_from_gaps(1.08, mu_s, sigma_s, dt, seed=2)
```

`annual_to_per_second` works here too: it divides by $N_s$ and $\sqrt{N_s}$ and does not care about the units. The price-range reset rule of the domain analysis is not applied in this snippet.

## Forex

**Standard:** GBM on the log exchange rate with drift equal to the **interest-rate differential** (r\_d − r\_f) under the pricing measure, or **zero drift** for real-world null tests, upgraded to GARCH or Heston volatility plus intraday seasonality for anything below daily bars.

### Intuition

An exchange rate is a price of one currency in another, so it has no "growth" like a stock. The only systematic force is **carry**: holding the high-yield currency earns the rate gap, and covered interest parity forces the forward to drift by exactly that gap. Out of sample, major FX rates are notoriously hard to beat with a driftless random walk (Meese & Rogoff, 1983) — so the driftless walk is not just a convenient null, it is an empirically strong forecaster. FX volatility is roughly symmetric (no strong leverage effect) but strongly clustered and strongly seasonal within the day: Tokyo, London and New York sessions have very different activity.

### Theory

**Garman–Kohlhagen (1983)** — Black–Scholes adapted to FX:

$dX_t = (r_d - r_f) X_t\,dt + \sigma X_t\,dW_t$

where:

- $X_t$ is the exchange rate at time $t$, expressed as units of domestic currency per one unit of foreign currency (for EURUSD, dollars per euro, if the dollar is the domestic currency).
- $dX_t$ is its infinitesimal change over the infinitesimal time $dt$.
- $r_d$ is the domestic risk-free interest rate, per year.
- $r_f$ is the foreign risk-free interest rate, per year.
- $r_d - r_f$ is the interest-rate differential (the carry), used as the drift of the exchange rate.
- $\sigma$ is the annual volatility of the exchange rate.
- $W_t$ is a standard Brownian motion (Wiener process): increments $dW_t$ are normal with mean 0 and variance $dt$.

For real-world simulation, replace $r_d - r_f$ with 0 (random-walk null) or with a carry-plus-risk-premium estimate; uncovered interest parity typically *fails*, so the realised drift of high-yielders is often closer to zero than to r\_d − r\_f (Fama, 1984; Lustig & Verdelhan, 2007).

**Volatility layer.** GARCH(1,1) with Student-t innovations is the workhorse for daily FX (Bollerslev, 1987; Andersen & Bollerslev, 1998). For intraday bars, multiply the GARCH volatility by a deterministic **intraday seasonal factor** s(τ) estimated by averaging absolute returns per time-of-day bucket (Andersen & Bollerslev, 1997, 1998; Dacorogna et al., 2001):

$r_{t,\tau} = \sigma_t \, s(\tau) \, \varepsilon_{t,\tau}, \qquad \varepsilon \sim t_\nu / \sqrt{\nu/(\nu-2)}$

where:

- $r_{t,\tau}$ is the log return of the bar that falls in time-of-day bucket $\tau$ on day $t$.
- $t$ is the day (the time index of the GARCH volatility).
- $\tau$ is the intraday bucket, for example the UTC hour of the bar (0 to 23).
- $\sigma_t$ is the conditional volatility of day $t$ given by the GARCH(1,1) model, expressed per bar.
- $s(\tau)$ is the deterministic intraday seasonal factor of bucket $\tau$: above 1 in busy hours, below 1 in quiet ones. It is estimated from the average absolute return per bucket and normalised (in the example below, to a root mean square of 1 over the day).
- $\varepsilon_{t,\tau}$ is the random shock of the bar.
- $t_\nu$ is the Student-t distribution with $\nu$ degrees of freedom, which has fatter tails than the normal.
- $\nu$ is the number of degrees of freedom ($\nu > 2$); the smaller it is, the fatter the tails.
- $\sqrt{\nu/(\nu-2)}$ is the standard deviation of $t_\nu$. Dividing by it rescales the shock to a variance of 1, so that $\sigma_t$ keeps its meaning as the volatility.

**Option-desk standard.** For pricing exotics, FX desks use Heston or SABR calibrated to the volatility smile, often combined in a local-stochastic-volatility (LSV) model (Clark, 2011; Hagan et al., 2002).

**Multi-currency consistency.** Simulate a set of base pairs against USD with a correlation matrix and derive crosses by triangulation. Simulating each cross independently breaks no-arbitrage.

The correlation matrix of the base pairs is factorised with the Cholesky decomposition:

$\rho = L L^\top$

where:

- $\rho$ is the correlation matrix of the returns of the base pairs: square, symmetric, positive definite, with ones on the diagonal.
- $L$ is the lower-triangular Cholesky factor of $\rho$. Multiplying a vector of independent standard normal shocks by $L$ gives shocks with correlation $\rho$.
- $L^\top$ is the transpose of $L$ (rows and columns swapped).

A cross rate is derived from the base pairs by triangulation, for example:

$\ln \text{EURJPY}_t = \ln \text{EURUSD}_t + \ln \text{USDJPY}_t$

where:

- $\text{EURUSD}_t$ is the price at time $t$ of one euro in US dollars (simulated).
- $\text{USDJPY}_t$ is the price at time $t$ of one US dollar in Japanese yen (simulated).
- $\text{EURJPY}_t$ is the price at time $t$ of one euro in yen (derived, not simulated).
- $\ln$ is the natural logarithm. Prices multiply ($\text{EURJPY} = \text{EURUSD} \times \text{USDJPY}$), so log prices add.

**Calendar.** FX trades roughly Sunday 22:00 to Friday 22:00 UTC; generate no bars over the weekend and optionally a gap at the Sunday open.

### Example

EURUSD at 1.08, annual volatility 7%, simulated as 1-hour bars for one year with (a) zero drift, (b) GARCH(1,1) clustering with Student-t(5) shocks, (c) an intraday seasonal factor peaking at the London–New York overlap.

```python
import numpy as np

rng = np.random.default_rng(7)
hours_per_year = 24 * 260            # trading days only
sig_ann, nu = 0.07, 5
omega, alpha, beta = 0.0, 0.05, 0.93
h_var = (sig_ann**2) / hours_per_year
omega = h_var * (1 - alpha - beta)    # targets the unconditional variance

# Intraday seasonal factor by UTC hour (normalised to mean 1)
hour_profile = np.array([0.6,0.6,0.7,0.8,0.8,0.8,0.9,1.2,1.5,1.4,1.3,1.2,
                         1.4,1.8,1.7,1.5,1.2,1.0,0.8,0.7,0.6,0.5,0.5,0.6])
hour_profile /= np.sqrt(np.mean(hour_profile**2))

n = hours_per_year
eps = rng.standard_t(nu, n) / np.sqrt(nu / (nu - 2))
h = np.empty(n); r = np.empty(n); h[0] = h_var
for t in range(n):
    if t: h[t] = omega + alpha * r[t-1]**2 + beta * h[t-1]
    r[t] = np.sqrt(h[t]) * eps[t]
r_seasonal = r * hour_profile[np.arange(n) % 24]
price = 1.08 * np.exp(np.cumsum(r_seasonal - 0.5 * h * hour_profile[np.arange(n) % 24]**2))
```

This is the kind of generator suitable as a *structure-free* null for FX strategy tests: no drift, realistic tails, clustering and session rhythm, but no exploitable autocorrelation in returns. If a mean-reversion or trend rule shows a positive Sharpe here, the profit is coming from the backtest mechanics, not from the market.

## Equities

**Standard:** GBM with a positive drift (risk-free rate plus equity premium in the real world; r − q under pricing), extended with **jumps** (Merton) for earnings and news, and **stochastic volatility with negative price–vol correlation** (Heston, or GJR-GARCH) for the leverage effect.

### Intuition

A single stock is a claim on a growing business, so a positive bias is economically justified: on average investors are paid to hold equity risk. But single names gap: earnings releases, guidance changes, M&A. Those gaps cannot come from a continuous Brownian path — at daily resolution GBM practically never produces a −20% day, while real stocks do so a few times a decade. And when prices fall, volatility rises (leverage and fear), so the shocks are not symmetric.

### Theory

**Merton jump-diffusion (1976):**

$\frac{dS_t}{S_{t^-}} = (\mu - \lambda \kappa)\,dt + \sigma\,dW_t + (J - 1)\,dN_t, \quad \ln J \sim N(\mu_J, \sigma_J^2), \; \kappa = E[J-1]$

where:

- $S_t$ is the price at time $t$, and $dS_t$ its infinitesimal change.
- $S_{t^-}$ is the price just before time $t$, that is before a possible jump at $t$. The relative change is measured against it.
- $\mu$ is the total expected return per year, jumps included.
- $\lambda$ is the jump intensity: the average number of jumps per year.
- $\kappa = E[J-1]$ is the expected relative size of a jump (for example $-0.005$ for an average jump of $-0.5\%$). In this model only, $\kappa$ is the jump size; it is not the mean-reversion speed used in the Heston model. For a log-normal jump it equals $e^{\mu_J + \sigma_J^2/2} - 1$.
- $\sigma$ is the annual volatility of the continuous (diffusion) part.
- $W_t$ is a standard Brownian motion, and $dW_t$ its increment (normal, mean 0, variance $dt$).
- $J$ is the jump multiplier: the price after a jump divided by the price before it, so $J - 1$ is the relative jump size.
- $\ln J \sim N(\mu_J, \sigma_J^2)$ means the log of the multiplier is normal.
- $\mu_J$ is the mean of the log jump size, and $\sigma_J$ is its standard deviation.
- $N_t$ is a Poisson process with intensity $\lambda$: it counts the jumps up to time $t$. $dN_t$ is 1 if a jump happens in $dt$ and 0 otherwise.
- $E[\cdot]$ is the expected value.

The $-\lambda\kappa$ term compensates the jumps so that the total expected return stays $\mu$. For single names, jumps can be **scheduled**: put a jump with high probability on each earnings date (Dubinsky, Johannes, Kaeck & Seeger, 2019). Kou (2002) replaces the normal jump size with a double-exponential, giving separately tuned up- and down-jump tails.

**Heston stochastic volatility (1993):**

$\begin{aligned} dS_t &= \mu S_t\,dt + \sqrt{v_t}\,S_t\,dW^S_t \\ dv_t &= \kappa(\theta - v_t)\,dt + \xi\sqrt{v_t}\,dW^v_t, \qquad d\langle W^S, W^v\rangle_t = \rho\,dt \end{aligned}$

where:

- $S_t$ is the price at time $t$, and $dS_t$ its infinitesimal change.
- $v_t$ is the instantaneous variance of the price at time $t$ (so the volatility is $\sqrt{v_t}$). Unlike in GBM, it is random and changes over time.
- $\mu$ is the annual drift (expected return per year) of the price.
- $W^S_t$ is the Brownian motion that drives the price.
- $W^v_t$ is the Brownian motion that drives the variance.
- $\kappa$ is the speed of mean reversion of the variance: how fast $v_t$ is pulled back towards $\theta$.
- $\theta$ is the long-run mean of the variance, so $\sqrt{\theta}$ is the long-run volatility.
- $\xi$ is the volatility of the variance ("vol of vol"): how strongly $v_t$ fluctuates.
- $d\langle W^S, W^v\rangle_t = \rho\,dt$ states that the two Brownian motions are correlated.
- $\rho$ is the correlation between the price shocks and the variance shocks, between $-1$ and $1$.

For equities $\rho$ is typically between $-0.5$ and $-0.8$, which produces the leverage effect and the downward volatility skew. The Feller condition $2\kappa\theta > \xi^2$ keeps variance strictly positive; in simulation, use the full-truncation Euler scheme (Lord, Koekkoek & van Dijk, 2010) or Andersen's QE scheme (Andersen, 2008) rather than naive Euler.

**Discrete-time alternative.** GJR-GARCH(1,1) with skewed-t innovations, fitted per stock, is the common choice for risk and backtest simulation (Glosten, Jagannathan & Runkle, 1993; Hansen, 1994).

**Cross-section.** For a universe of stocks, simulate with a factor structure (market + sectors + idiosyncratic) rather than a full $N \times N$ correlation matrix; it is cheaper and keeps the covariance matrix well conditioned (Sharpe, 1963; Fama & French, 1993). In its simplest form, the return of stock $i$ is:

$r_i = \beta_i\, r_M + e_i$

where:

- $r_i$ is the return of stock $i$ over one step.
- $r_M$ is the return of the market factor over the same step.
- $\beta_i$ is the sensitivity (beta) of stock $i$ to the market: $\beta_i = 1$ moves one-for-one with the market.
- $e_i$ is the idiosyncratic return of stock $i$: the random part specific to that stock, independent of the market and of the other stocks.
- $N$ is the number of stocks in the universe.

**Corporate actions.** Simulated *price* paths should drop by the dividend on ex-dates if you are generating raw (unadjusted) prices; total-return series fold dividends into the drift.

### Example

A single tech stock, S₀ = 150, μ = 9%, σ = 28%, plus 4 earnings jumps a year with mean −0.5% and jump volatility 6%:

```python
import numpy as np

def merton_paths(S0, mu, sigma, lam, muJ, sigJ, T, steps, n_paths, seed=None):
    rng = np.random.default_rng(seed)
    dt = T / steps
    kappa = np.exp(muJ + 0.5 * sigJ**2) - 1
    Z = rng.standard_normal((n_paths, steps))
    N = rng.poisson(lam * dt, (n_paths, steps))
    J = muJ * N + sigJ * np.sqrt(N) * rng.standard_normal((n_paths, steps))
    drift = (mu - lam * kappa - 0.5 * sigma**2) * dt
    log_ret = drift + sigma * np.sqrt(dt) * Z + J
    return S0 * np.exp(np.cumsum(log_ret, axis=1))

paths = merton_paths(150, 0.09, 0.28, lam=4, muJ=-0.005, sigJ=0.06,
                     T=1, steps=252, n_paths=20_000, seed=3)
```

The daily return kurtosis from this generator is well above 3, unlike plain GBM; check it against the stock's own history as part of calibration.

## ETFs

**Standard:** an ETF is not simulated as a free-standing random walk. Simulate its **underlying** (index, basket, or commodity futures) with the appropriate model from the other sections, then map it to the ETF through the fund's mechanics: expense ratio, tracking error, and — for leveraged or inverse funds — **daily rebalancing**.

### Intuition

An ETF is a wrapper. A plain S&P 500 ETF is the index minus a small fee and a little noise, so its price process *is* the index process. The wrapper only matters when it does something path-dependent: a 3× leveraged ETF resets its exposure every day, so in a choppy market it loses value even if the index ends flat ("volatility decay"). A commodity ETF that holds futures earns the **roll yield**, which can differ wildly from the spot price change.

### Theory

**Plain index ETF:**

$r^{ETF}_t = r^{IDX}_t - \frac{c}{N} + \eta_t, \qquad \eta_t \sim N(0, \sigma_{TE}^2 / N)$

where:

- $r^{ETF}_t$ is the return of the ETF in period $t$.
- $r^{IDX}_t$ is the return of the underlying index in the same period.
- $c$ is the annual expense ratio of the fund (for example 0.0009 for 0.09% a year).
- $N$ is the number of periods per year (for example 252 for daily periods).
- $c/N$ is the expense charged in one period.
- $\eta_t$ is the tracking noise of period $t$: the random difference between the ETF and the index after fees.
- $N(0, \sigma_{TE}^2 / N)$ is a normal distribution with mean 0 and variance $\sigma_{TE}^2 / N$.
- $\sigma_{TE}$ is the annual tracking-error volatility (typically a few basis points for large equity ETFs).

Simulate premium/discount to NAV as a small mean-reverting OU process if you need intraday realism (Petajisto, 2017).

**Leveraged ETF with leverage L, rebalanced daily** (Cheng & Madhavan, 2009; Avellaneda & Zhang, 2010):

$r^{LETF}_t = L\, r^{IDX}_t - (L-1)\, r_f\,\Delta t - c\,\Delta t$

where:

- $r^{LETF}_t$ is the return of the leveraged ETF in period $t$.
- $r^{IDX}_t$ is the return of the underlying index in the same period.
- $L$ is the leverage factor (for example $3$ for a 3× fund, $-1$ for an inverse fund). In this section only, $L$ is the leverage, not a Cholesky factor.
- $r_f$ is the risk-free interest rate, per year. The fund borrows $(L-1)$ times its capital and pays this rate on it.
- $c$ is the annual expense ratio of the fund.
- $\Delta t$ is the length of the period, in years (the fund rebalances every day, so one period is one day).
- $(L-1)\,r_f\,\Delta t$ is the financing cost of the borrowed exposure in one period, and $c\,\Delta t$ is the fee in one period.

In continuous time with a GBM index, the LETF value satisfies

$\frac{V_T}{V_0} = \left(\frac{S_T}{S_0}\right)^{L} \exp\!\left[\left(-\tfrac{L^2 - L}{2}\sigma^2 - (L-1)r - c\right)T\right]$

where:

- $V_0$ and $V_T$ are the values of the leveraged ETF at the start and at time $T$, so $V_T / V_0$ is its total growth factor.
- $S_0$ and $S_T$ are the values of the underlying index at the start and at time $T$, so $S_T / S_0$ is the index growth factor.
- $L$ is the leverage factor (for example 3). The index growth factor is raised to the power $L$.
- $\sigma$ is the annual volatility of the index.
- $r$ is the risk-free interest rate, per year (the same quantity as $r_f$ in the previous formula).
- $c$ is the annual expense ratio of the fund.
- $T$ is the length of the period, in years.
- $\exp[\cdot]$ is the exponential function.

The term $-\tfrac{1}{2}(L^2 - L)\sigma^2$ is the volatility decay. For $L = 3$ and $\sigma = 0.20$ it is $-\tfrac{1}{2}(9 - 3)(0.04) = -0.12$, so it costs about 12% a year relative to the naive 3× index return.

**Commodity ETF holding futures.** Simulate the futures curve (see Commodities) and roll the position on the fund's schedule; the ETF return is the front-contract return, not the spot return (Gorton & Rouwenhorst, 2006).

### Example

Index at 100, flat drift, σ = 20%; compare a 1× ETF and a 3× leveraged ETF over one year:

```python
import numpy as np
rng = np.random.default_rng(11)
n_paths, steps, sig = 20_000, 252, 0.20
r_idx = -0.5*sig**2/steps + sig/np.sqrt(steps)*rng.standard_normal((n_paths, steps))
simple = np.expm1(r_idx)                      # daily simple returns
etf1 = np.prod(1 + simple - 0.0009/steps, axis=1)
etf3 = np.prod(1 + 3*simple - 0.0095/steps, axis=1)
print(np.median(etf1), np.median(etf3))       # ~0.98 vs ~0.84
```

The median 3× fund loses about 16% in a year when its index has zero expected return — the result that makes leveraged ETFs unsuitable as buy-and-hold proxies, and why they must be simulated from the daily index path, never as a 3×-volatility GBM.

## Indices

**Standard:** two accepted routes. (1) **Index-level** simulation with GBM plus stochastic volatility and jumps (Bates SVJ, Heston, or GJR-GARCH) — the standard for index options and single-series backtests. (2) **Bottom-up** simulation of constituents with a correlated GBM or factor model, aggregated with the index weights — the standard when you need dispersion, breadth or constituent-level signals.

### Intuition

An index is an average of many stocks, so idiosyncratic noise diversifies away and what is left is the common market factor. That makes indices smoother than single names, with *fewer* idiosyncratic jumps but *stronger* crash-type co-movement: when everything falls together, correlations spike. Index volatility also shows the strongest leverage effect of any asset class — the index option skew is steep.

### Theory

**Correlated constituents (bottom-up).** With $n$ assets, the covariance matrix is:

$\Sigma = D\,\rho\,D$

where:

- $\Sigma$ is the $n \times n$ covariance matrix of the annual returns of the assets.
- $D$ is the diagonal matrix with the annual volatilities $\sigma_1, \dots, \sigma_n$ of the assets on its diagonal and zeros elsewhere.
- $\rho$ is the $n \times n$ correlation matrix of the assets (ones on the diagonal).

The log returns of one step, using the Cholesky factor $L$ of $\Sigma$, are:

$\mathbf{r}_t = \left(\boldsymbol{\mu} - \tfrac{1}{2}\boldsymbol{\sigma}^2\right)\Delta t + \sqrt{\Delta t}\,L\,\mathbf{z}_t, \qquad LL^\top = \Sigma, \; \mathbf{z}_t \sim N(\mathbf{0}, I)$

where:

- $\mathbf{r}_t$ is the vector of the $n$ log returns of the assets in step $t$.
- $\boldsymbol{\mu}$ is the vector of the annual drifts of the assets.
- $\boldsymbol{\sigma}^2$ is the vector of the annual variances $\sigma_i^2$ of the assets, so $\tfrac{1}{2}\boldsymbol{\sigma}^2$ is the Itô correction of each asset.
- $\Delta t$ is the length of one step, in years.
- $L$ is the lower-triangular Cholesky factor of $\Sigma$, and $L^\top$ is its transpose. $LL^\top = \Sigma$ means that multiplying by $L$ gives shocks with covariance $\Sigma$.
- $\Sigma$ is the covariance matrix defined above.
- $\mathbf{z}_t$ is a vector of $n$ independent standard normal shocks, drawn at every step.
- $N(\mathbf{0}, I)$ is the multivariate normal distribution with mean vector $\mathbf{0}$ (all zeros) and covariance equal to the identity matrix $I$ (ones on the diagonal, zeros elsewhere), that is, uncorrelated shocks with variance 1.

Index level for a price-weighted, cap-weighted or equal-weighted rule:

$I_t = \dfrac{\sum_{i=1}^{n} w_{i,t}\, S_{i,t}}{\text{divisor}_t}$

where:

- $I_t$ is the index level at time $t$.
- $n$ is the number of constituents.
- $S_{i,t}$ is the price of constituent $i$ at time $t$.
- $w_{i,t}$ is the weight (for example the number of shares) of constituent $i$ at time $t$, according to the weighting rule.
- $\sum_{i=1}^{n}$ adds the terms for all constituents, from $i = 1$ to $i = n$.
- $\text{divisor}_t$ is the index divisor at time $t$: a scaling number that keeps the index level continuous when the constituents change.

Real index providers also rebalance and reconstitute; ignore that for short horizons, model it for multi-year studies (Glasserman, 2003, §2.3).

Correlation is not constant — it rises in sell-offs. A regime-switching correlation matrix (calm vs stress) or a DCC-GARCH model (Engle, 2002) captures this; constant-ρ simulation understates portfolio drawdowns (Longin & Solnik, 2001).

**Index-level (top-down) — Bates (1996) SVJ:**

$\frac{dS_t}{S_{t^-}} = (\mu - \lambda\kappa)\,dt + \sqrt{v_t}\,dW^S_t + (J-1)\,dN_t, \qquad dv_t = \kappa_v(\theta - v_t)\,dt + \xi\sqrt{v_t}\,dW^v_t$

where:

- $S_t$ is the index level at time $t$, and $S_{t^-}$ is the level just before a possible jump at $t$.
- $v_t$ is the instantaneous variance of the index (the volatility is $\sqrt{v_t}$), which is random.
- $\mu$ is the total expected return per year, jumps included.
- $\lambda$ is the jump intensity: the average number of jumps per year.
- $\kappa$ is the expected relative size of a jump, $\kappa = E[J-1]$, as in the Merton model. It compensates the jumps through the term $-\lambda\kappa$.
- $W^S_t$ is the Brownian motion that drives the index, and $W^v_t$ the one that drives the variance. They are correlated with correlation $\rho$.
- $J$ is the jump multiplier (price after the jump divided by price before it), so $J - 1$ is the relative jump size.
- $N_t$ is a Poisson process with intensity $\lambda$ that counts the jumps; $dN_t$ is 1 if a jump happens in $dt$ and 0 otherwise.
- $\kappa_v$ is the speed of mean reversion of the variance: how fast $v_t$ returns to $\theta$. It is written $\kappa_v$ here, to tell it apart from the jump size $\kappa$ (in the Heston model above, the same quantity is called $\kappa$).
- $\theta$ is the long-run mean of the variance, so $\sqrt{\theta}$ is the long-run volatility.
- $\xi$ is the volatility of the variance ("vol of vol").

This is the reference model for S&P 500 dynamics in the empirical option-pricing literature (Bakshi, Cao & Chen, 1997; Eraker, Johannes & Polson, 2003). Typical S&P 500 values: $\rho \approx -0.7$, long-run volatility $\sqrt{\theta} \approx 15\text{–}20\%$, rare negative jumps.

**Drift.** Real-world: the equity risk premium plus the risk-free rate (historically about 5–7% nominal total return per year for US large caps); for a price-return index subtract the dividend yield (Dimson, Marsh & Staunton, 2002).

### Example

Three-stock toy index with correlation 0.6 between all pairs:

```python
import numpy as np
rng = np.random.default_rng(5)
mu  = np.array([0.08, 0.07, 0.10])
sig = np.array([0.22, 0.18, 0.30])
rho = np.full((3, 3), 0.6); np.fill_diagonal(rho, 1.0)
L   = np.linalg.cholesky(np.diag(sig) @ rho @ np.diag(sig))
steps, dt = 252, 1/252
Z = rng.standard_normal((steps, 3))
log_r = (mu - 0.5*sig**2)*dt + np.sqrt(dt) * Z @ L.T
S = 100 * np.exp(np.cumsum(log_r, axis=0))       # constituents
w = np.array([0.5, 0.3, 0.2])
index = (S * w).sum(axis=1)                       # fixed-share, cap-weighted at t0
```

The index volatility comes out near

$\sigma_I = \sqrt{\mathbf{w}^\top \Sigma\, \mathbf{w}} \approx 19.4\%$

below the weighted average of the constituent volatilities,

$\sum_{i=1}^{3} w_i\,\sigma_i = 0.5 \times 0.22 + 0.3 \times 0.18 + 0.2 \times 0.30 = 22.4\%$

which makes diversification visible.

where:

- $\sigma_I$ is the annual volatility of the index.
- $\mathbf{w}$ is the vector of the weights of the three stocks, $(0.5, 0.3, 0.2)$, and $\mathbf{w}^\top$ is its transpose (a row instead of a column).
- $\Sigma$ is the covariance matrix of the three stocks, built from their volatilities $(0.22, 0.18, 0.30)$ and the correlation $0.6$ between every pair.
- $\mathbf{w}^\top \Sigma\, \mathbf{w}$ is the variance of the weighted portfolio, and its square root is the volatility.
- $w_i$ and $\sigma_i$ are the weight and the annual volatility of stock $i$.

## Commodities

**Standard:** commodities are **not** modelled as a plain random walk. The industry standard is a **mean-reverting log price** (Schwartz 1997, one-factor) or, more commonly, the **Schwartz–Smith (2000) two-factor model**: a mean-reverting short-term deviation plus a random-walk (biased) long-term equilibrium. Seasonality is added for agriculture and natural gas, and spikes (jumps with fast decay) for power and gas.

### Intuition

When the oil price is very high, supply responds (new wells, substitution) and demand falls, pulling the price back; when it is very low, production shuts in. So spot commodity prices are pulled towards a cost-of-production level — mean reversion — while that level itself drifts slowly with technology and long-run demand, which looks like a random walk. Physical storage links spot and futures through the **convenience yield**: when inventories are scarce, spot trades above futures (backwardation). Weather and harvest cycles add calendar seasonality; electricity cannot be stored at all, so it spikes violently and snaps back.

### Theory

**Schwartz (1997) one-factor** — Ornstein–Uhlenbeck on the log spot, X = ln S:

$dX_t = \kappa(\alpha - X_t)\,dt + \sigma\,dW_t$

where:

- $X_t = \ln S_t$ is the natural log of the spot price $S_t$ at time $t$.
- $dX_t$ is its infinitesimal change over the infinitesimal time $dt$.
- $\kappa$ is the speed of mean reversion, per year: the larger it is, the faster $X_t$ is pulled back towards $\alpha$.
- $\alpha$ is the long-run mean of the log price, so the long-run price level is $e^{\alpha}$.
- $\kappa(\alpha - X_t)$ is the pull towards the mean: positive when $X_t$ is below $\alpha$ and negative when it is above.
- $\sigma$ is the annual volatility of the log price.
- $W_t$ is a standard Brownian motion; $dW_t$ is normal with mean 0 and variance $dt$.

Exact discretisation (Vasicek, 1977; Glasserman, 2003, §3.3):

$X_{t+\Delta t} = \alpha + (X_t - \alpha)e^{-\kappa\Delta t} + \sigma\sqrt{\frac{1 - e^{-2\kappa\Delta t}}{2\kappa}}\,Z$

where:

- $X_t$ is the log price at time $t$, and $X_{t+\Delta t}$ is the log price one step later.
- $\Delta t$ is the length of one step, in years.
- $\alpha$ is the long-run mean of the log price.
- $\kappa$ is the speed of mean reversion, per year.
- $e^{-\kappa\Delta t}$ is the fraction of the current deviation $(X_t - \alpha)$ that remains after one step. So $\alpha + (X_t - \alpha)e^{-\kappa\Delta t}$ is the expected log price one step ahead.
- $\sigma$ is the annual volatility of the log price.
- $\sigma\sqrt{\dfrac{1 - e^{-2\kappa\Delta t}}{2\kappa}}$ is the exact standard deviation of the random part over one step.
- $Z$ is a random shock drawn from the standard normal distribution (mean 0, standard deviation 1), drawn independently at every step.

The half-life of a shock is

$t_{1/2} = \dfrac{\ln 2}{\kappa}$

where $\ln 2 \approx 0.693$ is the natural log of 2, $\kappa$ is the speed of mean reversion per year, and $t_{1/2}$ is the time, in years, for a deviation from $\alpha$ to shrink by half. Typical crude oil half-lives estimated from futures curves are on the order of months to about a year.

**Schwartz–Smith (2000) two-factor:**

$\ln S_t = \chi_t + \xi_t, \qquad d\chi_t = -\kappa\chi_t\,dt + \sigma_\chi\,dW^\chi_t, \qquad d\xi_t = \mu_\xi\,dt + \sigma_\xi\,dW^\xi_t$

where:

- $S_t$ is the spot price at time $t$, and $\ln S_t$ is its natural log.
- $\chi_t$ is the short-term deviation factor: it pulls the log price away from equilibrium and mean-reverts to 0.
- $\xi_t$ is the long-term equilibrium factor: the level the log price reverts to, which itself moves as a random walk. In this formula only, $\xi_t$ is a factor; it is not the vol-of-vol $\xi$ of the Heston model.
- $d\chi_t$ and $d\xi_t$ are the infinitesimal changes of the two factors over the infinitesimal time $dt$.
- $\kappa$ is the speed of mean reversion of $\chi_t$, per year.
- $\sigma_\chi$ is the annual volatility of the short-term factor.
- $\mu_\xi$ is the annual drift of the long-term factor (the bias of the random walk).
- $\sigma_\xi$ is the annual volatility of the long-term factor.
- $W^\chi_t$ and $W^\xi_t$ are the Brownian motions that drive the two factors (they can be correlated).

In words: $\chi_t$ is the short-term deviation (mean-reverting to 0) and $\xi_t$ the long-term equilibrium, a **biased random walk** with drift $\mu_\xi$. This is the cleanest example in this document of where the biased random walk lives *inside* a richer model. It is equivalent to the Gibson & Schwartz (1990) stochastic-convenience-yield model.

**Seasonality** (natural gas, grains): add a deterministic seasonal function to the log price (Sørensen, 2002):

$f(t) = \sum_{k=1}^{K} \left[ a_k \cos(2\pi k t) + b_k \sin(2\pi k t) \right]$

where:

- $f(t)$ is the seasonal component added to the log price at time $t$.
- $t$ is the time, in years, so that the seasonal pattern repeats every year.
- $k$ is the harmonic number: $k = 1$ is a cycle that repeats once a year, $k = 2$ twice a year, and so on.
- $K$ is the number of harmonics used, chosen by the modeller.
- $a_k$ and $b_k$ are the coefficients (amplitudes) of the cosine and sine of harmonic $k$, estimated from data.
- $\cos$ and $\sin$ are the cosine and sine functions, and $\pi \approx 3.14159$.
- $\sum_{k=1}^{K}$ adds the terms of all harmonics, from $k = 1$ to $k = K$.

**Spikes** (power, gas): mean-reverting jump-diffusion with large positive jumps and a high reversion speed (Geman & Roncoroni, 2006; Cartea & Figueroa, 2005).

**Futures, not spot.** Most tradable exposure is in futures. Under the two-factor model the futures price has a closed form, so simulate the factors and *derive* the whole futures curve; then build continuous series by rolling contracts on a fixed schedule (Schwartz & Smith, 2000).

### Example

WTI-like log spot with long-run level ln 70, κ = 1.5 (half-life ≈ 5.5 months), σ = 35%, monthly steps over 10 years:

```python
import numpy as np
rng = np.random.default_rng(9)
kappa, alpha, sigma = 1.5, np.log(70), 0.35
dt, n = 1/12, 120
a = np.exp(-kappa*dt)
sd = sigma * np.sqrt((1 - a**2) / (2*kappa))
X = np.empty(n+1); X[0] = np.log(90)            # start above equilibrium
for t in range(n):
    X[t+1] = alpha + (X[t] - alpha)*a + sd*rng.standard_normal()
S = np.exp(X)
```

Starting at 90, the path is pulled back towards 70 within a year. A plain GBM started at 90 would have no such pull; strategies tested on GBM-generated commodity data therefore misjudge both mean-reversion and trend-following edges.

## Cryptos

**Standard:** there is no long-established convention yet, but the research consensus is that plain GBM is clearly inadequate. Practice is GBM as the null, upgraded to **stochastic volatility with correlated jumps in returns and volatility (SVCJ)** for pricing, and to **GARCH with Student-t or skewed-t shocks** — often with **regime switching** — for risk and strategy testing. The calendar is 24/7/365.

### Intuition

Crypto behaves like a young, sentiment-driven equity with no earnings anchor: volatility is several times that of equity indices, tails are extremely fat, and there are frequent jumps from exchange failures, regulation headlines and liquidations cascading through leveraged perpetual futures. Volatility clusters hard and switches between distinct bull, bear and quiet regimes. Unlike equities, the leverage effect is weak or even inverted — volatility often rises on rallies. There is no weekend: generating bars only on weekdays is a common error.

### Theory

**SVCJ** (Duffie, Pan & Singleton, 2000; Eraker, Johannes & Polson, 2003), applied to Bitcoin by Hou, Wang, Chen & Härdle (2020):

$\begin{aligned} d\ln S_t &= \mu\,dt + \sqrt{v_t}\,dW^S_t + Z^y_t\,dN_t \\ dv_t &= \kappa(\theta - v_t)\,dt + \sigma_v\sqrt{v_t}\,dW^v_t + Z^v_t\,dN_t \end{aligned}$

where:

- $S_t$ is the price at time $t$, and $d\ln S_t$ is the infinitesimal change of its natural log.
- $v_t$ is the instantaneous variance of the price (the volatility is $\sqrt{v_t}$), which is random.
- $\mu$ is the drift of the log price, per year.
- $W^S_t$ is the Brownian motion that drives the price, and $W^v_t$ the one that drives the variance (they can be correlated).
- $\kappa$ is the speed of mean reversion of the variance, per year.
- $\theta$ is the long-run mean of the variance.
- $\sigma_v$ is the volatility of the variance ("vol of vol").
- $N_t$ is a Poisson process that counts the jumps; $dN_t$ is 1 if a jump happens in $dt$ and 0 otherwise. The same jump hits the price and the variance at the same time.
- $Z^y_t$ is the size of the jump in the log price.
- $Z^v_t$ is the size of the jump in the variance (always positive, so variance jumps up).

The distributions of the jump sizes are:

$Z^v \sim \text{Exp}(\mu_v), \qquad Z^y \mid Z^v \sim N(\mu_y + \rho_J Z^v,\ \sigma_y^2)$

where:

- $Z^v$ is the variance jump size, drawn from an exponential distribution with mean $\mu_v$.
- $\mu_v$ is the mean size of the variance jump.
- $Z^y \mid Z^v$ is the log-price jump size given the variance jump of the same event, drawn from a normal distribution.
- $\mu_y$ is the mean of the log-price jump when the variance jump is zero.
- $\rho_J$ is the jump correlation parameter: how much the mean of the price jump shifts for each unit of variance jump.
- $\sigma_y$ is the standard deviation of the log-price jump, and $\sigma_y^2$ its variance.

A jump in price comes with a simultaneous jump up in volatility. Hou et al. report that for the crypto index CRIX, jumps are frequent and the correlation between return and volatility diffusion is close to zero or slightly positive, unlike equities.

**GARCH family.** Bitcoin daily returns are well fit by GARCH-type models with heavy-tailed innovations; asymmetric terms add little (Katsiampa, 2017; Chu, Chan, Nadarajah & Osterrieder, 2017).

**Regime switching** (Hamilton, 1989): a two- or three-state Markov chain where each state has its own (μ\_k, σ\_k). This is the natural way to build a *biased* random walk for crypto — drift is positive in one regime, negative in another — and it reproduces long bull and bear cycles that a single-drift walk cannot (Ardia, Bluteau & Rüede, 2019).

**Drift.** There is no accepted risk premium estimate; Liu & Tsyvinski (2021) find crypto returns are driven by crypto-specific factors (momentum, investor attention) rather than standard equity factors. For null testing use μ = 0; for scenarios, use regime-dependent drifts rather than one sample mean.

**Cross-asset.** Simulate altcoins as β × BTC plus idiosyncratic noise; correlations to BTC are high and rise in crashes.

### Example

Two-regime biased random walk for BTC on daily bars, 365 days per year:

```python
import numpy as np
rng = np.random.default_rng(21)
P = np.array([[0.98, 0.02],      # bull -> bull, bull -> bear
              [0.03, 0.97]])     # bear -> bull, bear -> bear
mu  = np.array([ 0.80, -0.60]) / 365     # annual drifts per regime
sig = np.array([ 0.55,  0.85]) / np.sqrt(365)
nu, n = 4, 3 * 365
state = np.empty(n, int); state[0] = 0
for t in range(1, n):
    state[t] = rng.choice(2, p=P[state[t-1]])
eps = rng.standard_t(nu, n) / np.sqrt(nu / (nu - 2))
r = mu[state] - 0.5 * sig[state]**2 + sig[state] * eps
btc = 60_000 * np.exp(np.cumsum(r))
```

Expected regime durations are

$E[D_k] = \dfrac{1}{1 - p_{kk}}$

which gives $\dfrac{1}{1 - 0.98} = 50$ days for bull and $\dfrac{1}{1 - 0.97} \approx 33$ days for bear.

where:

- $D_k$ is the duration, in days, of one stay in regime $k$ (a run of consecutive days in that regime).
- $E[D_k]$ is its expected value (the average duration).
- $p_{kk}$ is the probability of staying in regime $k$ from one day to the next: the diagonal entry of the transition matrix `P` ($0.98$ for bull, $0.97$ for bear).
- $1 - p_{kk}$ is the probability of leaving the regime on any given day. All regime parameters here are illustrative, not fitted; calibrate them with an EM / Hamilton-filter fit on your own data.

## Non-parametric alternatives

When you do not trust any parametric model, the industry alternative is to **resample the real returns** instead of drawing them from a formula. This keeps the true marginal distribution (tails included) and, with blocks, part of the dependence structure.

### Intuition

A parametric generator says "returns look like this formula". A bootstrap says "returns look like the ones we actually saw, shuffled". Shuffling single returns kills all time structure — perfect for a no-pattern null. Shuffling *blocks* of consecutive returns keeps short-range structure such as volatility clusters, while still destroying the long-range ordering a strategy might exploit.

### Theory

| Method | Keeps | Destroys | Reference |
| --- | --- | --- | --- |
| iid bootstrap (resample single returns) | Marginal distribution | All serial dependence, vol clustering | Efron (1979) |
| Moving-block bootstrap | Dependence within block length $b$ | Dependence beyond $b$ | Künsch (1989) |
| Stationary bootstrap (random block lengths $\sim \text{Geometric}(1/b)$) | Dependence; resampled series is stationary | Dependence beyond $\approx b$ | Politis & Romano (1994) |
| Phase randomisation (surrogate data) | Power spectrum / autocorrelation | Non-linear structure | Theiler et al. (1992) |
| Filtered historical simulation | GARCH dynamics + empirical shocks | Nothing structural, by design | Barone-Adesi, Giannopoulos & Vosper (1999) |
| Sign randomisation of returns | Absolute returns, hence vol clustering | Direction information | Equivalent to a Rademacher null in strategy testing |

In the table:

- $b$ is the block length: the number of consecutive returns that are kept together when resampling. For the stationary bootstrap it is the mean block length.
- $\text{Geometric}(1/b)$ is the geometric distribution with success probability $1/b$. Its mean is $b$, so block lengths vary at random around $b$.
- $\sim$ means "is distributed as", and $\approx b$ means "about $b$".

Automatic block-length selection is given by Politis & White (2004), corrected in Patton, Politis & White (2009).

**To get a biased random walk from a bootstrap:** demean the historical returns, resample, then add the chosen drift back — each synthetic return equals a resampled demeaned historical return plus $\mu\,\Delta t$:

$r^{*}_t = \tilde{r}_t + \mu\,\Delta t, \qquad \tilde{r}_t \in \{\, r_s - \bar{r} \,\}_{s=1}^{T}, \qquad \bar{r} = \dfrac{1}{T}\sum_{s=1}^{T} r_s$

where:

- $r^{*}_t$ is the synthetic log return at step $t$ (the output of the generator).
- $\tilde{r}_t$ is the resampled demeaned historical return used at step $t$: one of the values $r_s - \bar{r}$, picked by the bootstrap method.
- $r_s$ is the historical log return at step $s$ of the real series.
- $T$ is the number of historical returns in the real series.
- $\bar{r}$ is the sample mean of the historical returns, so $r_s - \bar{r}$ has mean zero.
- $\mu$ is the chosen annual drift (0 for the null).
- $\Delta t$ is the length of one step, in years, so $\mu\,\Delta t$ is the chosen bias per step.

This keeps the empirical shape while controlling the bias exactly.

### Example

```python
import numpy as np

def stationary_bootstrap(returns, n_out, mean_block, rng):
    T = len(returns); out = np.empty(n_out)
    i = rng.integers(T)
    for t in range(n_out):
        out[t] = returns[i]
        i = rng.integers(T) if rng.random() < 1/mean_block else (i + 1) % T
    return out

# r_hist: real EURUSD 1H log returns; mu_dt: chosen bias per bar (0 for the null)
rng = np.random.default_rng(0)
# r_star = stationary_bootstrap(r_hist - r_hist.mean(), len(r_hist), 24*5, rng) + mu_dt
```

Prefer the bootstrap when your strategy is sensitive to the exact tail shape or intraday patterns of one instrument; prefer the parametric generators when you need to vary a single property (volatility, drift, jump rate) in a controlled way.

## Summary by asset class

GBM is the shared baseline; what differs across asset classes is the drift convention and the one or two extensions that must be added before the synthetic data is credible.

| Asset class | Baseline generator | Drift (the "bias") | Must-have extensions | Calibrate to | Calendar |
| --- | --- | --- | --- | --- | --- |
| Forex | GBM on log rate (Garman–Kohlhagen) | r\_d − r\_f (pricing); 0 for null tests | GARCH-t vol, intraday seasonality, triangulated crosses | Realised vol, kurtosis, ACF of absolute returns, session vol profile | Sun 22:00 – Fri 22:00 UTC |
| Equities | GBM (Black–Scholes) | r − q (pricing); r + equity premium (real world) | Merton/Kou jumps on earnings dates, Heston or GJR-GARCH with ρ < 0 | Vol, skew, jump frequency, beta to market | Exchange hours, holidays, overnight gaps |
| ETFs | Underlying's model, mapped through fund mechanics | Underlying's drift − expense ratio | Tracking error; daily rebalancing for leveraged/inverse; futures roll for commodity ETFs | Tracking error, premium/discount to NAV | As the listing exchange |
| Indices | Index-level SVJ (Bates) or correlated constituents (Cholesky / factor) | r + equity premium − dividend yield | Stochastic vol, crash jumps, stress-regime correlation | Implied skew, realised correlation, drawdown distribution | Exchange hours |
| Commodities | OU on log price (Schwartz) / two-factor Schwartz–Smith | Long-run factor drift μ\_ξ; short-run factor reverts to 0 | Futures curve, convenience yield, seasonality, spikes (power, gas) | Futures term structure, half-life of shocks | Exchange hours; roll schedule |
| Cryptos | GBM as null, SVCJ or GARCH-t for realism | 0 for null; regime-dependent for scenarios | Jumps in price and vol, Markov regime switching, fat tails (ν ≈ 3–5) | Kurtosis, jump rate, regime durations | 24/7/365 |

## Validation checklist and pitfalls

A synthetic generator is only useful once it has been checked against the real instrument on the statistics your strategy depends on. Run these checks before using any generated series.

**Validate the generator**

- [ ] Mean and volatility of log returns match the target at the bar frequency (and the annualisation is consistent: $\sigma_{annual} = \sigma_{bar}\sqrt{n}$, where $\sigma_{bar}$ is the volatility of the log return of one bar and $n$ is the number of bars per year: $252$ trading days, $365$ calendar days, or the actual number of bars per year).
- [ ] Kurtosis and tail quantiles (1%, 99%) are close to the real series; compare with a QQ-plot.
- [ ] Autocorrelation of returns is near zero, while autocorrelation of absolute or squared returns decays like the real data (Cont, 2001).
- [ ] Intraday volatility profile and calendar gaps match the instrument.
- [ ] For multi-asset sets: correlation matrix matches, and is positive definite before the Cholesky step.
- [ ] Planted-drift test: set μ to a known value, run the estimator over many paths, and confirm it is recovered within its standard error.

**Pitfalls**

1. **Missing Itô correction.** Drifting log returns by $\mu$ instead of $\mu - \tfrac{1}{2}\sigma^2$ inflates the median path. Here $\mu$ is the annual drift and $\sigma$ the annual volatility, so the error per year is $\tfrac{1}{2}\sigma^2$; with $\sigma = 0.80$ (crypto) it is $\tfrac{1}{2}(0.80)^2 = 0.32$, that is 32% a year.
2. **Euler on GBM or OU.** Use the exact discretisations shown above; Euler on Heston needs full truncation or QE to avoid negative variance.
3. **Annual vs per-bar units.** Most generator bugs are unit bugs; keep μ and σ annual in the API and convert once with Δt.
4. **Seed reuse.** Comparing a strategy on "null" and "biased" paths with *different* seeds adds noise; with the *same* seed you get a paired, lower-variance comparison (common random numbers, Glasserman, 2003, §4.2).
5. **Bars from closes only.** If your strategy uses highs and lows (stops, take-profits), generate a finer path (e.g. 1-minute) and aggregate to OHLC; drawing OHLC independently distorts barrier hits.
6. **Treating a good result on synthetic data as evidence.** Synthetic data validates the *absence* of artefacts and the *power* of a test; it never proves an edge exists in the real market (Bailey, Borwein, López de Prado & Zhu, 2014).

## References

Compiled from the standard literature without a live web check; details are believed accurate but verify page numbers before citing formally.

**Textbooks and surveys**

- Aronson, D. (2007). *Evidence-Based Technical Analysis*. Wiley.
- Cont, R. (2001). Empirical properties of asset returns: stylized facts and statistical issues. *Quantitative Finance*, 1(2), 223–236.
- Dacorogna, M., Gençay, R., Müller, U., Olsen, R., & Pictet, O. (2001). *An Introduction to High-Frequency Finance*. Academic Press.
- Dimson, E., Marsh, P., & Staunton, M. (2002). *Triumph of the Optimists*. Princeton University Press.
- Gatheral, J. (2006). *The Volatility Surface*. Wiley.
- Glasserman, P. (2003). *Monte Carlo Methods in Financial Engineering*. Springer.
- Hull, J. (2022). *Options, Futures, and Other Derivatives* (11th ed.). Pearson.
- Meucci, A. (2005). *Risk and Asset Allocation*. Springer.
- Shreve, S. (2004). *Stochastic Calculus for Finance II: Continuous-Time Models*. Springer.

**Random walk, GBM and drift**

- Bachelier, L. (1900). Théorie de la spéculation. *Annales scientifiques de l'École Normale Supérieure*, 17, 21–86.
- Black, F., & Scholes, M. (1973). The pricing of options and corporate liabilities. *Journal of Political Economy*, 81(3), 637–654.
- Fama, E. (1965). The behavior of stock-market prices. *Journal of Business*, 38(1), 34–105.
- Lo, A., & MacKinlay, A. C. (1988). Stock market prices do not follow random walks: evidence from a simple specification test. *Review of Financial Studies*, 1(1), 41–66.
- Mandelbrot, B. (1963). The variation of certain speculative prices. *Journal of Business*, 36(4), 394–419.
- Merton, R. (1973). Theory of rational option pricing. *Bell Journal of Economics and Management Science*, 4(1), 141–183.
- Merton, R. (1980). On estimating the expected return on the market. *Journal of Financial Economics*, 8(4), 323–361.
- Samuelson, P. (1965). Rational theory of warrant pricing. *Industrial Management Review*, 6(2), 13–39.

**Volatility, tails and jumps**

- Andersen, L. (2008). Simple and efficient simulation of the Heston stochastic volatility model. *Journal of Computational Finance*, 11(3), 1–42.
- Bakshi, G., Cao, C., & Chen, Z. (1997). Empirical performance of alternative option pricing models. *Journal of Finance*, 52(5), 2003–2049.
- Bates, D. (1996). Jumps and stochastic volatility: exchange rate processes implicit in Deutsche Mark options. *Review of Financial Studies*, 9(1), 69–107.
- Blattberg, R., & Gonedes, N. (1974). A comparison of the stable and Student distributions as statistical models for stock prices. *Journal of Business*, 47(2), 244–280.
- Bollerslev, T. (1986). Generalized autoregressive conditional heteroskedasticity. *Journal of Econometrics*, 31(3), 307–327.
- Bollerslev, T. (1987). A conditionally heteroskedastic time series model for speculative prices and rates of return. *Review of Economics and Statistics*, 69(3), 542–547.
- Duffie, D., Pan, J., & Singleton, K. (2000). Transform analysis and asset pricing for affine jump-diffusions. *Econometrica*, 68(6), 1343–1376.
- Dubinsky, A., Johannes, M., Kaeck, A., & Seeger, N. (2019). Option pricing of earnings announcement risks. *Review of Financial Studies*, 32(2), 646–687.
- Engle, R. (1982). Autoregressive conditional heteroscedasticity with estimates of the variance of United Kingdom inflation. *Econometrica*, 50(4), 987–1007.
- Engle, R. (2002). Dynamic conditional correlation. *Journal of Business & Economic Statistics*, 20(3), 339–350.
- Eraker, B., Johannes, M., & Polson, N. (2003). The impact of jumps in volatility and returns. *Journal of Finance*, 58(3), 1269–1300.
- Glosten, L., Jagannathan, R., & Runkle, D. (1993). On the relation between the expected value and the volatility of the nominal excess return on stocks. *Journal of Finance*, 48(5), 1779–1801.
- Hamilton, J. (1989). A new approach to the economic analysis of nonstationary time series and the business cycle. *Econometrica*, 57(2), 357–384.
- Hansen, B. (1994). Autoregressive conditional density estimation. *International Economic Review*, 35(3), 705–730.
- Heston, S. (1993). A closed-form solution for options with stochastic volatility with applications to bond and currency options. *Review of Financial Studies*, 6(2), 327–343.
- Kou, S. (2002). A jump-diffusion model for option pricing. *Management Science*, 48(8), 1086–1101.
- Longin, F., & Solnik, B. (2001). Extreme correlation of international equity markets. *Journal of Finance*, 56(2), 649–676.
- Lord, R., Koekkoek, R., & van Dijk, D. (2010). A comparison of biased simulation schemes for stochastic volatility models. *Quantitative Finance*, 10(2), 177–194.
- Merton, R. (1976). Option pricing when underlying stock returns are discontinuous. *Journal of Financial Economics*, 3(1–2), 125–144.
- Nelson, D. (1991). Conditional heteroskedasticity in asset returns: a new approach. *Econometrica*, 59(2), 347–370.
- Praetz, P. (1972). The distribution of share price changes. *Journal of Business*, 45(1), 49–55.
- Sharpe, W. (1963). A simplified model for portfolio analysis. *Management Science*, 9(2), 277–293.
- Fama, E., & French, K. (1993). Common risk factors in the returns on stocks and bonds. *Journal of Financial Economics*, 33(1), 3–56.

**Forex**

- Andersen, T., & Bollerslev, T. (1997). Intraday periodicity and volatility persistence in financial markets. *Journal of Empirical Finance*, 4(2–3), 115–158.
- Andersen, T., & Bollerslev, T. (1998). Deutsche Mark–Dollar volatility: intraday activity patterns, macroeconomic announcements, and longer run dependencies. *Journal of Finance*, 53(1), 219–265.
- Clark, I. (2011). *Foreign Exchange Option Pricing: A Practitioner's Guide*. Wiley.
- Fama, E. (1984). Forward and spot exchange rates. *Journal of Monetary Economics*, 14(3), 319–338.
- Garman, M., & Kohlhagen, S. (1983). Foreign currency option values. *Journal of International Money and Finance*, 2(3), 231–237.
- Hagan, P., Kumar, D., Lesniewski, A., & Woodward, D. (2002). Managing smile risk. *Wilmott Magazine*, September, 84–108.
- Lustig, H., & Verdelhan, A. (2007). The cross section of foreign currency risk premia and consumption growth risk. *American Economic Review*, 97(1), 89–117.
- Meese, R., & Rogoff, K. (1983). Empirical exchange rate models of the seventies: do they fit out of sample? *Journal of International Economics*, 14(1–2), 3–24.

**ETFs**

- Avellaneda, M., & Zhang, S. (2010). Path-dependence of leveraged ETF returns. *SIAM Journal on Financial Mathematics*, 1(1), 586–603.
- Cheng, M., & Madhavan, A. (2009). The dynamics of leveraged and inverse exchange-traded funds. *Journal of Investment Management*, 7(4), 43–62.
- Petajisto, A. (2017). Inefficiencies in the pricing of exchange-traded funds. *Financial Analysts Journal*, 73(1), 24–54.

**Commodities**

- Cartea, Á., & Figueroa, M. (2005). Pricing in electricity markets: a mean reverting jump diffusion model with seasonality. *Applied Mathematical Finance*, 12(4), 313–335.
- Geman, H., & Roncoroni, A. (2006). Understanding the fine structure of electricity prices. *Journal of Business*, 79(3), 1225–1261.
- Gibson, R., & Schwartz, E. (1990). Stochastic convenience yield and the pricing of oil contingent claims. *Journal of Finance*, 45(3), 959–976.
- Gorton, G., & Rouwenhorst, K. G. (2006). Facts and fantasies about commodity futures. *Financial Analysts Journal*, 62(2), 47–68.
- Schwartz, E. (1997). The stochastic behavior of commodity prices: implications for valuation and hedging. *Journal of Finance*, 52(3), 923–973.
- Schwartz, E., & Smith, J. (2000). Short-term variations and long-term dynamics in commodity prices. *Management Science*, 46(7), 893–911.
- Sørensen, C. (2002). Modeling seasonality in agricultural commodity futures. *Journal of Futures Markets*, 22(5), 393–426.
- Uhlenbeck, G., & Ornstein, L. (1930). On the theory of the Brownian motion. *Physical Review*, 36(5), 823–841.
- Vasicek, O. (1977). An equilibrium characterization of the term structure. *Journal of Financial Economics*, 5(2), 177–188.

**Cryptos**

- Ardia, D., Bluteau, K., & Rüede, M. (2019). Regime changes in Bitcoin GARCH volatility dynamics. *Finance Research Letters*, 29, 266–271.
- Chu, J., Chan, S., Nadarajah, S., & Osterrieder, J. (2017). GARCH modelling of cryptocurrencies. *Journal of Risk and Financial Management*, 10(4), 17.
- Hou, A. J., Wang, W., Chen, C. Y. H., & Härdle, W. K. (2020). Pricing cryptocurrency options. *Journal of Financial Econometrics*, 18(2), 250–279.
- Katsiampa, P. (2017). Volatility estimation for Bitcoin: a comparison of GARCH models. *Economics Letters*, 158, 3–6.
- Liu, Y., & Tsyvinski, A. (2021). Risks and returns of cryptocurrency. *Review of Financial Studies*, 34(6), 2689–2727.

**Resampling and backtest validity**

- Bailey, D., Borwein, J., López de Prado, M., & Zhu, Q. (2014). Pseudo-mathematics and financial charlatanism: the effects of backtest overfitting on out-of-sample performance. *Notices of the AMS*, 61(5), 458–471.
- Barone-Adesi, G., Giannopoulos, K., & Vosper, L. (1999). VaR without correlations for portfolios of derivative securities. *Journal of Futures Markets*, 19(5), 583–602.
- Efron, B. (1979). Bootstrap methods: another look at the jackknife. *Annals of Statistics*, 7(1), 1–26.
- Künsch, H. (1989). The jackknife and the bootstrap for general stationary observations. *Annals of Statistics*, 17(3), 1217–1241.
- Patton, A., Politis, D., & White, H. (2009). Correction to "Automatic block-length selection for the dependent bootstrap". *Econometric Reviews*, 28(4), 372–375.
- Politis, D., & Romano, J. (1994). The stationary bootstrap. *Journal of the American Statistical Association*, 89(428), 1303–1313.
- Politis, D., & White, H. (2004). Automatic block-length selection for the dependent bootstrap. *Econometric Reviews*, 23(1), 53–70.
- Theiler, J., Eubank, S., Longtin, A., Galdrikian, B., & Farmer, J. D. (1992). Testing for nonlinearity in time series: the method of surrogate data. *Physica D*, 58(1–4), 77–94.
