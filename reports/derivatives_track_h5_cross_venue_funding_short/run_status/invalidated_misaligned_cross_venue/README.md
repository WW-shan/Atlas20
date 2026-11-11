# Invalidated LS24 run

This run used the first `conservative_cross_venue_funding` implementation, which aligned Binance
and Bybit timestamps by exact index union. Binance funding rows carry millisecond jitter, so most
rows became NaN and the conservative minimum was sparse.

The implementation was changed to floor both settlement grids to the minute. The official run is
the one directly under `reports/derivatives_track_h5_cross_venue_funding_short/`. This directory is
kept only as an audit trail and is not counted as the trial result.
