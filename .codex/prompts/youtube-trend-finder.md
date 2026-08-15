# YouTube Trend Finder

Use `$youtube-trend-finder` to find YouTube trends for `<NICHE>` in the US over the last `<N>` days.

Choose relevant English keywords, scan 2 pages per keyword unless the user asks otherwise, run `collector.collect(...)`, read the raw API output, create a curated top-20 trends CSV in the timestamped directory under `outputs/`, and create a second CSV with 30 original video suggestions based on those trends.

