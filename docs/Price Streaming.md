# Price Streaming

## Overview

The price streaming feature generates tick data at random intervals defined under a set of constraints, following
random walk process or eventually a biased random walk process.


## Constraints

The set of constraints under which the tick price is emitted are the following:

- average frequency [ticks/second]: The average amount of ticks to emit per second, considering a normal distribution.
- frequency deviation [ticks/second]: Standard deviation for the ticks per second (given the normal distribution)
+
Since the tick price generation uses the core model for generating ticks, also includes the following constraints.

- initial value: Initial price on top of which calculates the second one (random walk).
- $\mu$: mean of price change distribution. If [\mu \neq 0\] then the process is a biased random walk
- $\sigma$: standard deviation of the price change distribution

## Calculations

The algorithm to generate ticks frequency normally distributed with mean frequency $\mu[ticks/sec]$ and standrd deviation $\sigma[ticks/sec]$ is like so:

1. Get the a frequency from the normal distribution $~N(\mu, \sigma)$

$freq_t[ticks/sec] = N(\mu, \sigma)$


2. Transform the frequency to time interval per tick:

$T=\frac{1}{freq_t}[sec/tick]$


3. Generate a tick value and then sleep $T[sec]$











