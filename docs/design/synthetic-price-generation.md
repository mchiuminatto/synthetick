# Synthetic Price Generation with Random Walks — Industry Standards by Asset Class

Oct 18, 2026 · @Marcello

## Purpose and scope

The industry baseline for synthetic prices in every asset class is the **geometric random walk** (discretised Geometric Brownian Motion, GBM) on log prices; the **biased** version adds a drift term, and each asset class then layers on the one or two extensions its data visibly demands (jumps, stochastic volatility, mean reversion, fat tails). No desk uses a pure random walk as its final model — it is the null hypothesis everything else is measured against.

Synthetic prices are used for three jobs:

1. **Null benchmarks.** Run a strategy on paths with no exploitable structure; any "edge" found there is overfitting or a backtest artefact (Bailey et al., 2014; Aronson, 2007).
2. **Stress and capacity tests.** Generate thousands of plausible futures to estimate drawdown distributions and tail risk (Glasserman, 2003).
3. **Pipeline validation.** Inject a *known* drift or pattern and check that the research pipeline recovers it — a unit test for the statistics.

**Random walk (RW) vs biased random walk (BRW).** An unbiased RW has zero expected log return per step. A BRW has a non-zero expected step, μΔt, which can be (a) a risk-neutral drift for pricing, (b) a real-world drift calibrated from history or from carry, or (c) a deliberately planted drift to test signal detection. Which one you choose depends on the job, not on the asset class.

Each asset section below is layered: **Intuition → Theory → Example**, followed by a single References section.

## Common foundation: random walk, GBM and drift

Every generator in this document is the same recipe — **simulate log returns, then exponentiate and cumulate** — with a different rule for what the return distribution looks like at each step.

### Intuition

Prices are multiplicative: a 1% move on 100 and on 200 is the same "size" of news. So you random-walk the *logarithm* of price, which guarantees positive prices and makes returns scale-free. Adding a constant to each log step (the bias) tilts the walk upward or downward — that is all a "biased random walk" is.

### Theory

**Arithmetic random walk** (Bachelier, 1900) — only for spreads, rates or prices that can go negative:

$P_{t+1} = P_t + \mu\,\Delta t + \sigma\sqrt{\Delta t}\,\varepsilon_{t+1}, \qquad \varepsilon_{t+1} \sim \text{iid } N(0,1)$

**Geometric Brownian Motion** (Samuelson, 1965; Black & Scholes, 1973; Merton, 1973):

$dS_t = \mu S_t\,dt + \sigma S_t\,dW_t$

Its **exact** discretisation (no Euler error, because log S is Gaussian):

$S_{t+\Delta t} = S_t \exp\!\left[\left(\mu - \tfrac{1}{2}\sigma^2\right)\Delta t + \sigma\sqrt{\Delta t}\,Z\right], \qquad Z \sim N(0,1)$

The −½σ² term is the Itô correction. It makes E\[S\_T\] = S\_0·e^{μT} while the median path grows only at μ − ½σ². Forgetting it is the most common bug in home-made generators (Glasserman, 2003, ch. 3; Shreve, 2004, ch. 4).

**Choosing the drift μ (the "bias")**

| Use case | Drift convention | Source |
| --- | --- | --- |
| Option pricing / risk-neutral | μ = r − q (rate minus dividend or foreign rate) | Black & Scholes (1973); Hull (2022) |
| Real-world scenario / risk | μ = historical mean, usually shrunk towards a prior (equity premium, carry) | Meucci (2005) |
| Null benchmark for strategy testing | μ = 0, or μ such that the median path is flat (μ = ½σ²) | Aronson (2007) |
| Signal-recovery test | μ planted at a known value, then estimated back | Lo & MacKinlay (1988) |

Note that the sample mean of returns is estimated very imprecisely: its standard error is σ/√T in annual units, so ten years of a 15%-vol asset pins μ down only to ±4.7% (Merton, 1980). This is why industry practice prefers economically motivated drifts over historical ones.

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

Minimal, vectorised GBM / BRW generator in Python (NumPy). Setting `mu=0` gives the drift-free null; any other `mu` gives the biased walk.

```python
import numpy as np

def gbm_paths(S0, mu, sigma, T, steps, n_paths, seed=None):
    """Exact GBM: mu, sigma annualised; T in years."""
    rng = np.random.default_rng(seed)
    dt = T / steps
    Z = rng.standard_normal((n_paths, steps))
    log_ret = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z
    log_path = np.cumsum(log_ret, axis=1)
    return S0 * np.exp(np.hstack([np.zeros((n_paths, 1)), log_path]))

# Unbiased null vs biased walk, 1 year of daily bars
null  = gbm_paths(100, mu=0.00, sigma=0.20, T=1, steps=252, n_paths=10_000, seed=1)
biased = gbm_paths(100, mu=0.08, sigma=0.20, T=1, steps=252, n_paths=10_000, seed=1)
print(null[:, -1].mean(), np.median(null[:, -1]))   # ~100.0, ~98.0 (Ito drag)
```

The printout illustrates the Itô correction: with μ = 0 the *mean* terminal price stays at 100, but the *median* drifts down to about 100·e^{−0.02} ≈ 98.

## Forex

**Standard:** GBM on the log exchange rate with drift equal to the **interest-rate differential** (r\_d − r\_f) under the pricing measure, or **zero drift** for real-world null tests, upgraded to GARCH or Heston volatility plus intraday seasonality for anything below daily bars.

### Intuition

An exchange rate is a price of one currency in another, so it has no "growth" like a stock. The only systematic force is **carry**: holding the high-yield currency earns the rate gap, and covered interest parity forces the forward to drift by exactly that gap. Out of sample, major FX rates are notoriously hard to beat with a driftless random walk (Meese & Rogoff, 1983) — so the driftless walk is not just a convenient null, it is an empirically strong forecaster. FX volatility is roughly symmetric (no strong leverage effect) but strongly clustered and strongly seasonal within the day: Tokyo, London and New York sessions have very different activity.

### Theory

**Garman–Kohlhagen (1983)** — Black–Scholes adapted to FX:

$dX_t = (r_d - r_f) X_t\,dt + \sigma X_t\,dW_t$

where X is domestic per unit of foreign. For real-world simulation, replace r\_d − r\_f with 0 (random-walk null) or with a carry-plus-risk-premium estimate; uncovered interest parity typically *fails*, so the realised drift of high-yielders is often closer to zero than to r\_d − r\_f (Fama, 1984; Lustig & Verdelhan, 2007).

**Volatility layer.** GARCH(1,1) with Student-t innovations is the workhorse for daily FX (Bollerslev, 1987; Andersen & Bollerslev, 1998). For intraday bars, multiply the GARCH volatility by a deterministic **intraday seasonal factor** s(τ) estimated by averaging absolute returns per time-of-day bucket (Andersen & Bollerslev, 1997, 1998; Dacorogna et al., 2001):

$r_{t,\tau} = \sigma_t \, s(\tau) \, \varepsilon_{t,\tau}, \qquad \varepsilon \sim t_\nu / \sqrt{\nu/(\nu-2)}$

**Option-desk standard.** For pricing exotics, FX desks use Heston or SABR calibrated to the volatility smile, often combined in a local-stochastic-volatility (LSV) model (Clark, 2011; Hagan et al., 2002).

**Multi-currency consistency.** Simulate a set of base pairs against USD with a correlation matrix (Cholesky factor L, ρ = LLᵀ) and derive crosses by triangulation, e.g. log EURJPY = log EURUSD + log USDJPY. Simulating each cross independently breaks no-arbitrage.

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

N\_t is a Poisson process with intensity λ (jumps per year). The −λκ term compensates the jumps so the total expected return stays μ. For single names, jumps can be **scheduled**: put a jump with high probability on each earnings date (Dubinsky, Johannes, Kaeck & Seeger, 2019). Kou (2002) replaces the normal jump size with a double-exponential, giving separately tuned up- and down-jump tails.

**Heston stochastic volatility (1993):**

$\begin{aligned} dS_t &= \mu S_t\,dt + \sqrt{v_t}\,S_t\,dW^S_t \\ dv_t &= \kappa(\theta - v_t)\,dt + \xi\sqrt{v_t}\,dW^v_t, \qquad d\langle W^S, W^v\rangle_t = \rho\,dt \end{aligned}$

For equities ρ is typically −0.5 to −0.8, which produces the leverage effect and the downward volatility skew. The Feller condition 2κθ > ξ² keeps variance strictly positive; in simulation, use the full-truncation Euler scheme (Lord, Koekkoek & van Dijk, 2010) or Andersen's QE scheme (Andersen, 2008) rather than naive Euler.

**Discrete-time alternative.** GJR-GARCH(1,1) with skewed-t innovations, fitted per stock, is the common choice for risk and backtest simulation (Glosten, Jagannathan & Runkle, 1993; Hansen, 1994).

**Cross-section.** For a universe of stocks, simulate with a factor structure (market + sectors + idiosyncratic), r\_i = β\_i r\_M + e\_i, rather than a full N×N correlation matrix; it is cheaper and keeps the covariance matrix well conditioned (Sharpe, 1963; Fama & French, 1993).

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

with c the annual expense ratio, N periods per year, and σ\_TE the annual tracking-error volatility (typically a few basis points for large equity ETFs). Simulate premium/discount to NAV as a small mean-reverting OU process if you need intraday realism (Petajisto, 2017).

**Leveraged ETF with leverage L, rebalanced daily** (Cheng & Madhavan, 2009; Avellaneda & Zhang, 2010):

$r^{LETF}_t = L\, r^{IDX}_t - (L-1)\, r_f\,\Delta t - c\,\Delta t$

In continuous time with a GBM index, the LETF value satisfies

$\frac{V_T}{V_0} = \left(\frac{S_T}{S_0}\right)^{L} \exp\!\left[\left(-\tfrac{L^2 - L}{2}\sigma^2 - (L-1)r - c\right)T\right]$

The term −½(L² − L)σ² is the volatility decay: for L = 3 and σ = 20%, it costs about 12% a year relative to the naive 3× index return.

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

**Correlated constituents (bottom-up).** With n assets, covariance matrix Σ = D ρ D (D = diagonal of volatilities) and Cholesky factor L:

$\mathbf{r}_t = \left(\boldsymbol{\mu} - \tfrac{1}{2}\boldsymbol{\sigma}^2\right)\Delta t + \sqrt{\Delta t}\,L\,\mathbf{z}_t, \qquad LL^\top = \Sigma, \; \mathbf{z}_t \sim N(\mathbf{0}, I)$

Index level for a price-weighted, cap-weighted or equal-weighted rule: I\_t = Σ\_i w\_{i,t} S\_{i,t} / divisor\_t. Real index providers also rebalance and reconstitute; ignore that for short horizons, model it for multi-year studies (Glasserman, 2003, §2.3).

Correlation is not constant — it rises in sell-offs. A regime-switching correlation matrix (calm vs stress) or a DCC-GARCH model (Engle, 2002) captures this; constant-ρ simulation understates portfolio drawdowns (Longin & Solnik, 2001).

**Index-level (top-down) — Bates (1996) SVJ:**

$\frac{dS_t}{S_{t^-}} = (\mu - \lambda\kappa)\,dt + \sqrt{v_t}\,dW^S_t + (J-1)\,dN_t, \qquad dv_t = \kappa_v(\theta - v_t)\,dt + \xi\sqrt{v_t}\,dW^v_t$

This is the reference model for S&P 500 dynamics in the empirical option-pricing literature (Bakshi, Cao & Chen, 1997; Eraker, Johannes & Polson, 2003). Typical S&P 500 values: ρ ≈ −0.7, long-run vol √θ ≈ 15–20%, rare negative jumps.

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

The index volatility comes out near √(wᵀΣw) ≈ 19.4%, below the weighted average of the constituent vols (22.4%) — diversification made visible.

## Commodities

**Standard:** commodities are **not** modelled as a plain random walk. The industry standard is a **mean-reverting log price** (Schwartz 1997, one-factor) or, more commonly, the **Schwartz–Smith (2000) two-factor model**: a mean-reverting short-term deviation plus a random-walk (biased) long-term equilibrium. Seasonality is added for agriculture and natural gas, and spikes (jumps with fast decay) for power and gas.

### Intuition

When the oil price is very high, supply responds (new wells, substitution) and demand falls, pulling the price back; when it is very low, production shuts in. So spot commodity prices are pulled towards a cost-of-production level — mean reversion — while that level itself drifts slowly with technology and long-run demand, which looks like a random walk. Physical storage links spot and futures through the **convenience yield**: when inventories are scarce, spot trades above futures (backwardation). Weather and harvest cycles add calendar seasonality; electricity cannot be stored at all, so it spikes violently and snaps back.

### Theory

**Schwartz (1997) one-factor** — Ornstein–Uhlenbeck on the log spot, X = ln S:

$dX_t = \kappa(\alpha - X_t)\,dt + \sigma\,dW_t$

Exact discretisation (Vasicek, 1977; Glasserman, 2003, §3.3):

$X_{t+\Delta t} = \alpha + (X_t - \alpha)e^{-\kappa\Delta t} + \sigma\sqrt{\frac{1 - e^{-2\kappa\Delta t}}{2\kappa}}\,Z$

The half-life of a shock is ln 2 / κ. Typical crude oil half-lives estimated from futures curves are on the order of months to about a year.

**Schwartz–Smith (2000) two-factor:**

$\ln S_t = \chi_t + \xi_t, \qquad d\chi_t = -\kappa\chi_t\,dt + \sigma_\chi\,dW^\chi_t, \qquad d\xi_t = \mu_\xi\,dt + \sigma_\xi\,dW^\xi_t$

χ is the short-term deviation (mean-reverting to 0) and ξ the long-term equilibrium — a **biased random walk** with drift μ\_ξ. This is the cleanest example in this document of where the biased random walk lives *inside* a richer model. It is equivalent to the Gibson & Schwartz (1990) stochastic-convenience-yield model.

**Seasonality** (natural gas, grains): add a deterministic f(t) = Σ\_k \[a\_k cos(2πkt) + b\_k sin(2πkt)\] to the log price (Sørensen, 2002).

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

with Z^v \~ Exp(μ\_v) and Z^y | Z^v \~ N(μ\_y + ρ\_J Z^v, σ\_y²): a jump in price comes with a simultaneous jump up in volatility. Hou et al. report that for the crypto index CRIX, jumps are frequent and the correlation between return and volatility diffusion is close to zero or slightly positive, unlike equities.

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

Expected regime durations are 1/(1 − 0.98) = 50 days for bull and 1/(1 − 0.97) ≈ 33 days for bear. All regime parameters here are illustrative, not fitted; calibrate them with an EM / Hamilton-filter fit on your own data.

## Non-parametric alternatives

When you do not trust any parametric model, the industry alternative is to **resample the real returns** instead of drawing them from a formula. This keeps the true marginal distribution (tails included) and, with blocks, part of the dependence structure.

### Intuition

A parametric generator says "returns look like this formula". A bootstrap says "returns look like the ones we actually saw, shuffled". Shuffling single returns kills all time structure — perfect for a no-pattern null. Shuffling *blocks* of consecutive returns keeps short-range structure such as volatility clusters, while still destroying the long-range ordering a strategy might exploit.

### Theory

| Method | Keeps | Destroys | Reference |
| --- | --- | --- | --- |
| iid bootstrap (resample single returns) | Marginal distribution | All serial dependence, vol clustering | Efron (1979) |
| Moving-block bootstrap | Dependence within block length b | Dependence beyond b | Künsch (1989) |
| Stationary bootstrap (random block lengths \~ Geometric(1/b)) | Dependence; resampled series is stationary | Dependence beyond \~b | Politis & Romano (1994) |
| Phase randomisation (surrogate data) | Power spectrum / autocorrelation | Non-linear structure | Theiler et al. (1992) |
| Filtered historical simulation | GARCH dynamics + empirical shocks | Nothing structural, by design | Barone-Adesi, Giannopoulos & Vosper (1999) |
| Sign randomisation of returns | Absolute returns, hence vol clustering | Direction information | Equivalent to a Rademacher null in strategy testing |

Automatic block-length selection is given by Politis & White (2004), corrected in Patton, Politis & White (2009).

**To get a biased random walk from a bootstrap:** demean the historical returns, resample, then add the chosen drift back — each synthetic return equals a resampled demeaned historical return plus μΔt. This keeps the empirical shape while controlling the bias exactly.

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

- [ ] Mean and volatility of log returns match the target at the bar frequency (and the annualisation is consistent: √252, √365 or √(bars per year)).
- [ ] Kurtosis and tail quantiles (1%, 99%) are close to the real series; compare with a QQ-plot.
- [ ] Autocorrelation of returns is near zero, while autocorrelation of absolute or squared returns decays like the real data (Cont, 2001).
- [ ] Intraday volatility profile and calendar gaps match the instrument.
- [ ] For multi-asset sets: correlation matrix matches, and is positive definite before the Cholesky step.
- [ ] Planted-drift test: set μ to a known value, run the estimator over many paths, and confirm it is recovered within its standard error.

**Pitfalls**

1. **Missing Itô correction.** Drifting log returns by μ instead of μ − ½σ² inflates the median path; with σ = 80% (crypto) the error is 32% a year.
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
