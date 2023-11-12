# Synthetick Library

This is a Work In progress for a library to generate synthetic price time series at different levels of abstraction: tick, OHLC, etc.

At the bottom level the library generates tick data, on top of which it calculates price aggregations like OHLC or others.

So essentially tick price is at the core so the model how tick price is calculated is presented in the next section.

## Tick Data Model

### Core Model

Let $p_0$ be the initial price value for the time series $P$, with $n$ elements, then the next price elements of the series are calculated as follows:

$p_1 = p_0 + \Delta p_1$ <br>
$p_2 = p_1 + \Delta p_2$ <br>
... <br>
$p_{n-2} = p_{n-3} + \Delta p_{n-2}$ (1) <br>
$p_{n-1} = p_{n-2} + \Delta p_{n-1}$ (2) <br>
$p_{n} = p_{n-1} + \Delta p_{n}$ (3)

Where:

$\Delta p_i$ Is the return or price change in for period $i$

The general term is:

$p_{i} = p_{i-1} + \Delta p{i}, i \in [1, 2, ... n]$

Replacing (2) in (3)

$p_n = p_{n-2} + \Delta p_{n-1} + \Delta p_{n} (4)$

If we now repeat the process replace g (1) in (4)

$p_n = p_{n-3} + \Delta p_{n-2} + \Delta p_{n-1} + \Delta p_{n} (4)$

Repeating the process until $p_1$ is replaced in the resultant formula:

$p_n = p_{0} + \sum\limits_{i=1}^n \Delta p_i$

If $\Delta p_{i}$ is produced by an stochastic process, then the series has the characteristics of a Random Walk.

We make $\Delta p_{i} \approx N(\mu, \sigma)$ is a normal distribution with mean $\mu$ and standard deviation $\sigma$

If $\mu$ is 0, then the price generation process is an unbiased random walk, but as will be shown later, using $\mu \neq 0$ (biased random walk) it is possible to control the price trend

With $\sigma$ it is possible to control price volatility.



To wrap up this section, the tick price generation process has three parameters so far:

- $p_0$: First price in the series, necessary to calculate the remaining $n-1$ elements, with $n$ being the number of elements in the series.

- $\mu$: Mean for the distribution of returns or price change.

- $\sigma$: Standard deviation for the returns distribution.

### Bid, Ask, Spread

The price of a financial asset comes in pairs: the price at wich you buy or Ask price, and the price at wich you sell or Bid. So for each new tick price, you need two values: Bid anbd Ask.

The difference beteen both is the Spread:

$spread_i = Ask_i - Bid_i$

So to generate tick price it is needed to generate two time series.

The library generates Bid parice first (As described in Core Model), then calculates Ask as a function of Bid and Spread:

$Ask_i = Bid_i + Spread_i$

Where:

$Spread \in (SPREAD_{min}, SPREAD_{max})$ is calculated as a random value with unifoirm dsitribution between the rnge$SPREAD_{min}$ and $SPREAD_{max}$



This calculation adds two new parameters to the model:

$spread_{min}$: Minimum value for the spread

$spread_{max}$ Maximum value for the spread



# TODO's

1. Improve spread calculation: Current version calculates a spread skewed to the lower an upper limits
   of the spread range.
2. Produce ticks at random intervals.
