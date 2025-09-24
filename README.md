# Synthetick Library

This is a Work In progress for a library to generate synthetic price time series at different levels of abstraction: tick, OHLC, etc.

At the bottom level the library generates tick data, on top of which it calculates price aggregations like OHLC or others.

So, essentially, tick price is at the core so the model how tick price is calculated is presented in the next section.

## Tick Data Model

### Core Model

Let $p_0$ be the initial price value for the time series $P$, with $n$ elements, then the next price elements of the series are calculated as follows:

$p_1 = p_0 + \Delta p_1$

$p_2 = p_1 + \Delta p_2$

...

$p_{n-2} = p_{n-3} + \Delta p_{n-2}$ (1)

$p_{n-1} = p_{n-2} + \Delta p_{n-1}$ (2)

$p_{n} = p_{n-1} + \Delta p_{n}$ (3)

Where:

$\Delta p_i$ Is the return or price change for period $i$

The general term is:

$p_{i} = p_{i-1} + \Delta p{i}, i \in [1, 2, ... n]$

Replacing (2) in (3)

$p_n = p_{n-2} + \Delta p_{n-1} + \Delta p_{n} (4)$

If we now repeat the process to replace (1) in (4)

$p_n = p_{n-3} + \Delta p_{n-2} + \Delta p_{n-1} + \Delta p_{n} (4)$

Repeating the process until $p_1$ is replaced in the resultant formula:

$p_n = p_{0} + \sum\limits_{i=1}^n \Delta p_i$

If $\Delta p_{i}$ is produced by an stochastic process, then the series has the characteristics of a Random Walk.

Making $\Delta p_{i} \approx N(\mu, \sigma)$ a normal distribution with mean $\mu$ and standard deviation $\sigma$

If $\mu$ is 0, then the price generation process is an unbiased random walk, but as will be shown later, using $\mu \neq 0$ (biased random walk) it is possible to control the price trend: up (long), range or down (short)

With $\sigma$ it is possible to control price volatility.

To wrap up this section, the tick price generation process has three parameters:

- $p_0$: First price in the series, necessary to calculate the remaining $n-1$ elements, with $n$ being the number of elements in the series.
- $\mu$: Mean for the distribution of returns or price change.
- $\sigma$: Standard deviation for the returns distribution.

### Bid, Ask, Spread

The price of a financial asset comes in pairs: the price at wich you buy or Ask price, and the price at wich you sell or Bid price. So for each new tick price, you need two values: Bid and Ask.

The difference between both is the Spread:

$spread_i = Ask_i - Bid_i$

So to generate tick price it is needed to generate two time series: bid and ask

The library generates Bid parice first (As described in Core Model), then calculates Ask as a function of Bid and Spread:

$Ask_i = Bid_i + Spread_i$

Where:

$Spread \in (SPREAD_{min}, SPREAD_{max})$ is calculated as a random value with unifoirm dsitribution between  $SPREAD_{min}$ and $SPREAD_{max}$

This calculation adds two new parameters to the model:

$spread_{min}$: Minimum value for the spread

$spread_{max}$ Maximum value for the spread

## Price Aggregations

Price aggregations are data reductions calaculated as a result of  applying functions on tick data sampled as follows:

 - Fix period of time (candles bars or price bars), 
 - Fix number of ticks (tick bars)
 - Fix price change (renko bars, pip bars).

So far only aggregatoions for fix periods of time are supported.



All the aggregation produce a structure named OHLC, which stands for Open, High, Low, Close. These aggregations can be represented as vectors:

$[open{-}time_i, close{-}time_i, open_i, high_i, low_i, close_i]$







```python
tick.price_time_series["bid"].resample(<tick-data-time-series>).ohlc()
```

For more datails read [here](https://pandas.pydata.org/docs/reference/api/pandas.core.resample.Resampler.ohlc.html)

TODO: add Renko and Tick Bars

## How to Use

### Install

```shell
pip install synthetick
```

### How to use

##### Generating tick data.

This example generates a time series of tick data with a frequency of 1 socond, uptrending, with a volatility range of 10 pips, a spread range from 0.5 to 3 pips, with the pip position at the 4th decimal place.

```python


from datetime import datetime
import pandas as pd
from synthetick.synthetick import Ticks

DATE_FROM: datetime = pd.to_datetime("2023-01-01 00:00:00")
DATE_TO: datetime = pd.to_datetime("2023-02-01 00:00:00")

tick_data_generator = Ticks(trend=0.01,
                            volatility_range=10,
                            spread_min=0.5,
                            spread_max=3,
                            pip_position=-4,
                            remove_weekend=True)

tick_data_generator._compute_date_range(date_from=DATE_FROM,
                                        date_to=DATE_TO,
                                        frequency="1s",
                                        init_value=1.1300)

tick_data_generator.price_time_series.to_csv("test_tick_happy_path.csv", index_label="date-time")

tick_data_generator.price_time_series[300:350][["bid", "ask"]].plot(figsize=(10, 3), marker=".", cmap="PiYG")
```

![](./tick-data.png)

##### Generating OHLC Data

```python
from datetime import datetime
import pandas as pd
from synthetick.synthetick import OHLC
import mplfinance as mpf

DATE_FROM: datetime = pd.to_datetime("2023-01-01 00:00:00")
DATE_TO: datetime = pd.to_datetime("2023-02-01 00:00:00")

ohlc: OHLC = OHLC(trend=0.0001,
                  volatility_range=10,
                  spread_min=0.5,
                  spread_max=3,
                  pip_position=-4,
                  remove_weekend=True,
                  tick_frequency="1s",
                  time_frame="H")

ohlc.produce(date_from=DATE_FROM, date_to=DATE_TO, init_value=1.300)
ohlc.ohlc_time_series["bid"].to_csv("ohlc_bid_1h.csv", index_label="date-time")

mc2 = mpf.make_marketcolors(up='blue', down='r')
s2 = mpf.make_mpf_style(marketcolors=mc2)
mpf.plot(ohlc.ohlc_time_series["bid"][200:400], type="candle", figsize=(15, 4), style=s2)
```

![](./ohlc_data.png)

## TODO's

1. Improve documentation
2. Produce ticks at random intervals.
3. Change trend when price reaches zero level
