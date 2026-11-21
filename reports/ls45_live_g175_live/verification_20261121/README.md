# LS104 2026-11-21 consistent pre-execution snapshot

This directory is an immutable copy of the coherent non-trading snapshot produced
after the 2026-11-21 incident. It was captured before another data refresh could
change the live files.

## Snapshot facts

- frozen signal date: `2026-11-20`
- latest completed Bitget mark in the snapshot: `2026-11-21 17:00 UTC`
- data fingerprint: `sha256:d9913acc237269e4db4a2b0da1fd535b65cee4721f11b02bd726d3d669c1ab2a`
- manifest SHA-256: `7f4e93d7677890e6e937cd9197ef321b2387d3dd23e868b06a2f7cc96bb71a52`
- receipt check at capture time: valid
- data audit: 0 hard failures, 0 warnings
- signal equivalence: 78 frozen rows / 78 replay rows, 0 differences
- venue symbol audit: passed
- contract-spec audit: 18 snapshots, 0 material changes

`SHA256SUMS` commits to every copied byte. The copy is for audit/reproduction
only; it is not execution state and must not be used to bypass the live gates.

## What this snapshot does **not** prove

It does not prove that the 2026-11-20 target event was applied to the live
account. The execution state still has:

- active event: `2026-11-13`
- active target hash: `2ef4e701...`
- current frozen target hash: `e04b17f3...`
- missing live event: `2026-11-20`

The resulting live discrepancies are visible in the live audit:

- HYPERLIQUID and NEAR remain open although the frozen 2026-11-20 book closes them
- the journal's latest signal date is still `2026-11-13`
- the current frozen book asks for ETHEREUM and UNISWAP shorts that are not open,
  and asks to increase ZCASH

Those are trading/application decisions, not data-repair decisions. This snapshot
must not be used to hand-edit `data/ls45_g175_execution_state.json` or the journal.

## Safe next steps

1. Preserve this snapshot as evidence.
2. Review the current position and pending event manually.
3. If the owner authorizes a catch-up, use the documented normal execution path
   inside its allowed window; otherwise wait for the next normal event/window.
4. Re-run `audit-live-ls104` after the pending event is actually applied.

No order was placed while producing this snapshot.
